#!/usr/bin/env python
# -*- coding:utf-8 -*-

import os

YOUTUBE_USER = ''
YOUTUBE_PASS = ''

# tudou info
TUDOU_USER      = ''
TUDOU_PASS      = ''
TUDOU_APPKEY    = ''
TUDOU_APPSECRET = ''
TUDOU_API = "http://api.tudou.com/v3/gw"

MAX_QUALITY = 35 # 5 240p, 34 360p, 35 480p, 22 720p, 37 1080p
AUTO_DELETE_TMP_VIDEO = True
VIDEO_DIR = os.path.join(os.path.dirname(__file__), 'videos')
