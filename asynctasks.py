#!/usr/bin/env python
# -*- coding:utf-8 -*-

import os
import time
import datetime
import logging
import base64
import json
import StringIO
import pycurl
import urllib2
import urllib
from datetime import datetime, timedelta
import sqlite3

import cgi
from urlparse import urlparse

from celery.task import task

import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'lib'))

from BeautifulSoup import BeautifulSoup

import encodings
encodings.aliases.aliases['gb2312'] = 'gb18030'
encodings.aliases.aliases['gbk']    = 'gb18030'

from ext import dict_factory
import config
from tudou import Tudou

youtube_dl_sh = os.path.join(os.path.dirname(__file__), 'lib', 'youtube-dl')
video_dir     = config.VIDEO_DIR
data_file     = os.path.join(os.path.dirname(__file__), 'data.sqlite')

db = None
def get_db():
    """docstring for db"""
    global db

    if db is None:
        db = sqlite3.connect(data_file)
        db.row_factory = dict_factory
        
    return db

def get_video(id):

    cur = get_db().cursor()
    cur.execute("select * from videos where id='%s'" % id)
    row = cur.fetchone()

    if row:
        return row
    else:
        return None

def update_video(id, data):

    cur = get_db().cursor()
    cur.execute("update videos set %s where id=%s" % (data, id))

    get_db().commit()
    return True
        
@task(max_retries=2, default_retry_delay=5*60)
def download(id, max_quality=35):
    """docstring for downloader"""
    
    if os.path.isdir(video_dir) is False:
        os.makedirs(video_dir, 0777)
    
    video = get_video(id)

    if not video:
        logging.error("no video: %s" % id)
        return True

    if video['status'] > 0:
        logging.error("video %s downloaded" % id)
        return True
        
    if video['source'].startswith('http://www.youtube.com') and config.YOUTUBE_USER and config.YOUTUBE_PASS:
        auth = '-u %s -p %s' % (config.YOUTUBE_USER, config.YOUTUBE_PASS)
    else:
        auth = ''
    
    logging.info("downloading: %s" % video['source'])

    video_file = "%s/%s.%s" % (video_dir, video['id'], video['format'])
    
    update_video(id, {'status':1})
    result = os.popen('python %s %s --max-quality %s -o %s %s' % (youtube_dl_sh, auth, max_quality, video_file, video['source']))
    
    result = result.read()
    logging.info(result)
    
    if result.find('HTTP Error 404') > -1:
        logging.error("video not found: %s" % id)
        update_video(id, 'status=2')
        return False
    
    #update_video(id, 'status=3')

    update_video(id, 'status=4')
    res = upload(video['title'], video_file, video['desc'], video['channel'], video['tags'])

    if res:
        update_video(id, "status=6,tudou_id='%s'" % res)
        get_state.delay(id)
    else:
        update_video(id, 'status=5')

		
	if config.AUTO_DELETE_TMP_VIDEO:
		try:
			os.remove(video_file)
		except:
			pass
    
    return True

def upload(title, filename, content="", channel_id=1, tags="", retries = 0):
    """docstring for upload"""

    #content = content + u" 想看更多cool视频请访问: http://www.niumang.com"
    data = {
        'method': 'item.upload',
        'format': 'json',
        'appKey': config.TUDOU_APPKEY,
        'title': title.encode("utf-8"),
        'content': content.encode("utf-8"),
        'tags': tags.encode("utf-8"),
        'channelId': channel_id
    }

    try:
        query_str = urllib.urlencode(data, True)
        auth_header = "Basic %s" % base64.encodestring('%s:%s' % (config.TUDOU_USER, config.TUDOU_PASS))[:-1]

        req = urllib2.Request(config.TUDOU_API + '?' + query_str)
        req.add_header("Authorization", auth_header)
        result = urllib2.urlopen(req).read()
        result = json.loads(result)

        item_code = result['itemUploadInfo']['itemCode']
        upload_url = result['itemUploadInfo']['uploadUrl'] or None

        if not upload_url or not item_code:
            logging.error("init upload failed: %s" % filename)
            return False

        logging.info("Upload to %s" % upload_url)

        out = StringIO.StringIO()
        c = pycurl.Curl()
        c.setopt(pycurl.WRITEFUNCTION, out.write)
        c.setopt(pycurl.POST, 1)
        # c.setopt(pycurl.CONNECTTIMEOUT, 30)
        c.setopt(pycurl.TIMEOUT, 3600)

        c.setopt(pycurl.URL, upload_url.encode('utf-8'))

        c.setopt(pycurl.HTTPPOST, [("file", (c.FORM_FILE, str(filename)))])
        c.setopt(pycurl.HTTPHEADER, ['Authorization: %s' % auth_header])
        # c.setopt(pycurl.VERBOSE, 1)
        c.perform()

        http_code = c.getinfo(pycurl.HTTP_CODE)
        result = out.getvalue()

        c.close()

        if http_code != 200:
            logging.error("upload failed: %s %s" % (filename, http_code))
            return False

        result = json.loads(result)

        if 'result' not in result or result['result'] != 'ok':
            logging.error("upload failed: %s" % filename)
            return False

        return item_code
    except Exception, e:
        logging.info("upload error: %s" % e)
        if retries < 2:
            retries += 1
            logging.info("retry %s time: %s" % (retries, filename))
            return upload(title=title, filename=filename, content=content, tags=tags, retries=retries)
        else:
            return False

@task(max_retries=5, default_retry_delay=5*60)
def get_state(vid):
    """docstring for tudou_state_async"""
    
    video = get_video(vid)
    
    if not video:
        logging.debug('no video %' % vid)
        return False
        
    result = Tudou(config.TUDOU_USER, config.TUDOU_PASS, config.TUDOU_APPKEY).get_state(video['tudou_id'])
    
    if result and 'itemCode' in result and video['tudou_id'] == result['itemCode']:
        if result['state'] == 1:
            # update_video(vid, 'status=11')
            update_video(vid, 'status=99')
            get_picurl.delay(video['id'])
        elif result['state'] == 2:
            update_video(vid, 'status=7')
            get_state.retry(countdown=5*60)
        elif result['state'] == 3:
            update_video(vid, 'status=8')
            get_state.retry(countdown=5*60)
        elif result['state'] == 4:
            update_video(vid, 'status=9')
    
    return True

@task(max_retries=3, default_retry_delay=5*60)
def get_picurl(vid):
    """docstring for get_picurl"""
    video = get_video(vid)
    
    if not video:
        logging.debug("no video %s" % vid)
        return True
        
    if 'picurl' in video and video['picurl']:
        logging.debug("picurl is exists")
        return True
    
    picurl = None
    info = Tudou(config.TUDOU_USER, config.TUDOU_PASS, config.TUDOU_APPKEY).get_info(video['tudou_id'])
    if info and 'picUrl' in info and info['picUrl']:
        picurl = info['picUrl']
        
    if picurl:
        update_video(vid, "status=99,picurl='%s'" % picurl)
    else:
        get_picurl.retry(countdown=5*60)

    return True
    
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s:%(msecs)03d %(levelname)-8s %(message)s',
        datefmt='%m-%d %H:%M')
    print Tudou(config.TUDOU_USER, config.TUDOU_PASS, config.TUDOU_APPKEY).get_state('DlRnXwgOl6U')
