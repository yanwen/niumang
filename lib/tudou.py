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
import json
from datetime import datetime, timedelta

class Tudou(object):
    """docstring for Tudou"""
    
    tudou_api = 'http://api.tudou.com/v3/gw'
    format = 'json'
    auth_token = ''
    appkey = ''
    
    def __init__(self, user, passwd, appkey):
        self.auth_token = base64.encodestring('%s:%s' % (user, passwd))[:-1]
        self.appkey = appkey
    
    def get_state(self, item_codes):
        """docstring for get_state"""
        return self.get_data(item_codes, method='item.state.get')
        
    def get_info(self, item_codes):
        """docstring for get_info"""
        return self.get_data(item_codes, method='item.info.get')
        
    def get_playtimes(self, item_codes):
        """docstring for get_playtimes"""
        return self.get_data(item_codes, method='item.playtimes.get')
        
    def get_data(self, item_codes, method='item.info.get'):
        """docstring for info_get"""
        
        data = {
            'method': method,
            'itemCodes': item_codes,
        }
        
        results = self.get(data)

        results = json.loads(results)
        if results and 'multiResult' in results and 'results' in results['multiResult']:
            results = results['multiResult']['results']

            if type(item_codes) is list:
                return results
            else:
                
                for item in results:
                    if item and item['itemCode'] == item_codes:
                        return item
        
        return False
        
    def getParameters(self, extraargs=None):
        #ck is a timecode to help google with caching
        
        parameters = {'format': self.format, 'appKey': self.appkey}
        if extraargs:
            parameters.update(extraargs)
        
        return urllib.urlencode(parameters, True)
    
    def get(self, parameters=None, need_auth=False):
        
        getString = self.getParameters(parameters)
        
        req = urllib2.Request(self.tudou_api + "?" + getString)
        
        if need_auth:
            req.add_header('Authorization','Basic %s' % self.auth_token)
        
        r = urllib2.urlopen(req)
        data = r.read()
        r.close()
        return data
        
    def post(self, postParameters=None, urlParameters=None, need_auth=False):
        
        if urlParameters:
            getString = self.getParameters(urlParameters)
            req = urllib2.Request(self.tudou_api + "?" + getString)
        else:
            req = urllib2.Request(self.tudou_api)
            
        req.add_header('Authorization','Basic %s' % self.auth_token)
        
        postString = self.getParameters(postParameters)
        r = urllib2.urlopen(req, data=postString)
        data = r.read()
        r.close()
        return data
        
if __name__ == "__main__":
    
    import config
    tudou = Tudou(config.TUDOU_USER, config.TUDOU_PASS, config.TUDOU_APPKEY)
    print tudou.get_state(['-9EQTl59zHU', 'DlRnXwgOl6U'])
