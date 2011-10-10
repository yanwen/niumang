#!/usr/bin/env python
# -*- coding:utf-8 -*-

import os

# Youtube login detail(optional)
YOUTUBE_USER = ''
YOUTUBE_PASS = ''

# Your tudou login details
TUDOU_USER      = ''
TUDOU_PASS      = ''

# Your tudou API key
TUDOU_APPKEY    = ''
TUDOU_APPSECRET = ''
TUDOU_API = "http://api.tudou.com/v3/gw"

# Youtube download quality
MAX_QUALITY = 35 # 5 240p, 34 360p, 35 480p, 22 720p, 37 1080p

# Automatic delete setup and videos path
AUTO_DELETE_TMP_VIDEO = True
VIDEO_DIR = os.path.join(os.path.dirname(__file__), 'videos')
