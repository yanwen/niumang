#!/usr/bin/env python
# -*- coding:utf-8 -*-

from __future__ import division
import os
import logging
import time
import hashlib
import urlparse
import socket
import re
import random
from datetime import datetime, timedelta
from urllib import unquote, quote_plus
import urllib

import cgi
from urlparse import urlparse

import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'lib'))

import tornado.auth
import tornado.escape
import tornado.httpserver
import tornado.ioloop
import tornado.web
import tornado.autoreload
from tornado.options import define, options
import sqlite3
import json

try:
    import daemon
except:
    daemon = None
    
from ext import dict_factory
import config
import asynctasks

socket.setdefaulttimeout(30)

define("port", default=8800, help="The port to be listened", type=int)
define("daemon", default=False, help="daemon mode", type=bool)
define("debug", default=False, help="debug mode", type=bool)

youtube_dl = os.path.join(os.path.dirname(__file__), 'lib', 'youtube-dl')
video_dir  = config.VIDEO_DIR
data_file  = os.path.join(os.path.dirname(__file__), 'data.sqlite')

class Application(tornado.web.Application):
    def __init__(self):
        urls = [
            (r"/", HomeHandler),
            (r"/upload", UploadHandler),
            (r"/status/(.*)", StatusHandler),
            (r"/status", StatusHandler),
            (r"/setup", InitHandler)
        ]
        settings = dict(
            template_path = os.path.join(os.path.dirname(__file__), "views"),
            static_path = os.path.join(os.path.dirname(__file__), "static"),
            xsrf_cookies = False,
            cookie_secret = "kL5gEmGeJJFuYh711oETzKXQAGaYdEQnp2XdTP1o/Vo=",
            debug = options.debug,
            login_url = "/login",
        )
        tornado.web.Application.__init__(self, urls, **settings)

        self.db = sqlite3.connect(data_file)
        self.db.row_factory = dict_factory
        
class BaseHandler(tornado.web.RequestHandler):
    
    statuses = {
        -1:'待审核',
        0:'等待下载',
        1:'正在下载',
        2:'下载出错',
        3:'下载完成，等待上传',
        4:'正在上传',
        5:'上传出错',
        6:'上传完成',
        7:'审核中',
        8:'转码中',
        9:'不存在（可能未能过审核）',
        10:'土豆已删除',
        11:'等待获取信息',
        12:'正在获取信息',
        13:'获取信息出错',
        99:'完成',
    }

    channels = [
        (1,"娱乐"),
        (3,"乐活"),
        (5,"搞笑"),
        (9,"动画"),
        (10,"游戏"),
        (14,"音乐"),
        (15,"体育"),
        (21,"科技"),
        (22,"电影"),
        (24,"财富"),
        (25,"教育"),
        (26,"汽车"),
        (27,"女性"),
        (29,"热点"),
        (30,"电视剧"),
        (31,"综艺"),
        (32,"风尚"),
        (99,"原创"),
    ]
    
    @property
    def db(self):
        return self.application.db
    
    def get_current_user(self):
        user_json = self.get_secure_cookie("user")
        if not user_json: return None
        return tornado.escape.json_decode(user_json)
        
    def render_string(self, template_name, **kwargs):

        channel_names = {}

        for channel in self.channels:
            channel_names[channel[0]] = channel[1]
        
        args = dict(
            channels      = self.channels,
            channel_names = channel_names,
            statuses      = self.statuses,
            tudou_appkey  = config.TUDOU_APPKEY,
        )

        args.update(kwargs)
        return super(BaseHandler, self).render_string(template_name, **args)
        
    def get_error_html(self, status_code, exception=None, **kwargs):
        """docstring for get_error_html(self, status_code, exception=None, **kwargs)"""
        
        if status_code == 404:
            return self.render_string("404.html")
        else:
            return super(BaseHandler, self).get_error_html(status_code, exception=None, **kwargs)

    def is_url(self, text):
        """docstring for is_url"""
        return text.partition("://")[0] in ('http', 'https')
       
    def get_play_code(self, via_site, via_id):

        if via_site in self.support_sites:
            return self.support_sites[via_site]['code_template'] % {'id':via_id}
        else:
            return None
            
    def get_tudou_id(self, url):
        """docstring for get_tudou_id"""
        return url.split("/")[5]
    
    def strip_tags(self, tags):
        """docstring for strip_tags"""
        
        if not tags:
            return []
        else:
            tags = tags.split(',')
            
            tags_striped = []
            for tag in tags:
                tags_striped.append(tag.strip())
            
            return ','.join(tags_striped[:6])
            
    def clean_channel_id(self, channel_id):
        """docstring for clean_channel_id"""
            
        try:
            channel_id = int(channel_id)
        except:
            channel_id = 0
        
        for channel in self.channels:
            if channel_id == channel[0]:
                return channel_id
        
        return 0

    def random_str(self, str_len=5, t=1):
        """docstring for random_str"""

        letters = "abcdefghigklmnoporstuvwxyz"
        numbers = "0123456789-_"
        upper_case = "ABCDEFGHIGKLMNOPORSTUVWXYZ"

        if t is 1:
            feed = letters+numbers
        else:
            feed = letters+upper_case+numbers

        return "".join(random.sample(feed, str_len))

    def new_id(self):
        """docstring for new_pad_name"""

        video_id = self.random_str(4, 2)
        video = self.get_video(video_id=video_id)
        
        if video_id.lower() in self.block_ids:
            return self.new_id()
        if video:
            return self.new_id()
        else:
            return video_id
            
    def count_videos(self, where=None):
        """docstring for count_videos"""

        cur = self.db.cursor()

        if where is None:
            cur.execute("SELECT count(*) as t FROM videos")
        else:
            cur.execute("SELECT count(*) as t FROM videos WHERE %s" % where)

        result = cur.fetchone()

        return result['t']
        
    def get_videos(self, start=0, limit=20):
        """docstring for get_videos"""
        
        cur = self.db.cursor()
        cur.execute("SELECT * FROM videos ORDER BY id DESC LIMIT %s,%s" % (start, limit))
        videos = cur.fetchall()
            
        return videos
    
    def get_video(self, video_id=None, source=None):
        """docstring for get_video"""

        sql = None
        if video_id is not None:
            sql = "SELECT * FROM videos WHERE id='%s'" % video_id
        elif source is not None:
            sql = "SELECT * FROM videos WHERE source_hash='%s'" % hashlib.sha1(source).hexdigest()
        else:
            return None
        
        cur = self.db.cursor()
        cur.execute(sql)
        row = cur.fetchone()

        return row

    def add_video(self, video):

        
        sql = "INSERT INTO videos (title, `desc`, tags, source, source_hash, format, channel, status, tudou_state, tudou_id, \
                                uploader, create_at) \
                    VALUES ('%(title)s', '%(desc)s','%(tags)s', '%(source)s', '%(source_hash)s', '%(format)s', '%(channel)s', \
                    0, 0, '', '%(uploader)s', '%(create_at)s')" % video

        cur = self.db.cursor()
        cur.execute(sql)
        self.db.commit()

        return cur.lastrowid
            
class HomeHandler(BaseHandler):
    
    def get(self):
        """docstring for get"""
        videos = self.get_videos(limit=10000)
        total_videos = len(videos)
        self.render("home.html",
                    videos = videos,
                    total_videos = total_videos
                )

class UploadHandler(BaseHandler):
    """docstring for HomeHandler"""
    
    # @tornado.web.authenticated
    def post(self):
        """docstring for post"""

        url = self.get_argument("url", None)
        title = self.get_argument("title", None)
        desc = self.get_argument("desc", "")
        tags = self.get_argument("tags", None)
        channel_id = self.get_argument("channel_id", 0)
        
        if not url:
            self.write(json.dumps({'error':"没有填写视频地址"}))
        elif not self.is_url(url):
            self.write(json.dumps({'error':"填写的视频地址有问题"}))
        elif not title:
            self.write(json.dumps({'error':"标题不能为空"}))
        else:

            tags = self.strip_tags(tags)
            channel_id = self.clean_channel_id(channel_id)

            video = self.get_video(source=url)

            # if video:
                # return self.write("视频已存在")
            
            if not self.current_user:
                uploader = ""
            else:
                uploader = ""
            
            video_info = os.popen("python %s --max-quality 35 -e --get-filename %s" % (youtube_dl, url))
            video_info = video_info.read().split("\n")

            if len(video_info) < 2:
                return self.write('链接有误或不支持的视频网站')
            
            video = {
                'source':url,
                'source_hash':hashlib.sha1(url).hexdigest(),
                'format':video_info[1].split('.')[-1],
                'title':title[:255],
                'channel':channel_id,
                'desc':desc[:2000],
                'tags':tags,
                'status': 1,
                'uploader':uploader,
                'create_at':time.time()
            }

            vid = self.add_video(video)

            if vid:
                asynctasks.download.delay(vid)
                video['id'] = vid
                video = json.dumps(video)
                self.write(video)
            else:
                self.write('未知错误')
    
class StatusHandler(BaseHandler):
    """docstring for StatusHandler"""
    
    def get(self, vid):
        """docstring for get"""
        video = self.get_video(video_id=vid)

        if video:
            video['status_desc'] = self.statuses[video['status']]
        else:
            viedo = {
                'status': -1,
                'status_desc': '视频不存在'
            }
        
        self.write(json.dumps(video))

    def post(self):
        """docstring for post"""
    
        ids = self.get_argument('ids', None)

        if ids:
            cur = self.db.cursor()
            cur.execute("SELECT id,status,tudou_id,picurl FROM videos WHERE id IN (%s)" % ids)
            videos = cur.fetchall()

            video_list = []

            for video in videos:
                video['status_desc'] = self.statuses[video['status']]
                video_list.append(video)

            self.write(json.dumps(video_list))
        else:
            self.write('error')
            
class AuthHandler(BaseHandler, tornado.auth.GoogleMixin):

    @tornado.web.asynchronous
    def get(self, action='login'):

        if action == 'login':
            if self.get_argument("openid.mode", None):
                self.get_authenticated_user(self.async_callback(self._on_auth))
                return
            self.authenticate_redirect()
        elif action == 'logout':
            self.clear_cookie('user')
            self.redirect("/")
        else:
            self.redirect("/")

    def _on_auth(self, user):
        
        if not user:
            raise tornado.web.HTTPError(500, "Google auth failed")
            
        current_user = {
            'email': user['email'],
            'locale': user['locale'],
        }

        self.set_secure_cookie("user", tornado.escape.json_encode(current_user), expires_days=30)
        
        if 'Host' in self.request.headers and self.request.headers['Host'] == 'dev.niumang.com':
            self.redirect("/")
        else:
            self.redirect("/admin")

class DevHandler(BaseHandler):
    """docstring for DevHandler"""
    
    def get(self):
        """docstring for get"""
        self.write(self.request.headers['Host'])

class Error404Handler(BaseHandler):
    """docstring for Error404Handler"""
    
    def get(self):
        """docstring for get"""
        self.render('404.html')

class InitHandler(BaseHandler):
    """docstring for InitHandler"""

    def get(self):
        """docstring for get"""

        init_sql = """
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY  AUTOINCREMENT  NOT NULL, 
            title VARCHAR(255),
            desc TEXT,
            tags TEXT,
            source TEXT,
            source_hash VARCHAR(128),
            format VARCHAR(5),
            channel INTEGER,
            status INTEGER,
            tudou_state INTEGER,
            tudou_id VARCHAR(255),
            picurl TEXT,
            uploader VARCHAR(255),
            create_at INTEGER
        )"""
        
        cu = self.db.cursor()
        cu.execute(init_sql)
        self.write('setup success!')
        
def runserver():
    tornado.options.parse_command_line()
    
    if options.daemon and daemon:
        log = open(os.path.join(os.path.dirname(__file__), 'logs', 'website%s.log' % options.port), 'a+')
        ctx = daemon.DaemonContext(stdout=log, stderr=log,  working_directory='.')
        ctx.open()
    
    http_server = tornado.httpserver.HTTPServer(Application())
    
    if options.debug:
        http_server.listen(options.port)
    else:
        http_server.bind(options.port)
        http_server.start(4)

    tornado.ioloop.IOLoop.instance().start()
    
if __name__ == "__main__":
    runserver()
