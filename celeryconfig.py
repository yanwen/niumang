#!/usr/bin/env python
# -*- coding:utf-8 -*-

BROKER_BACKEND = "mongodb"
BROKER_HOST = "127.0.0.1"
BROKER_PORT = 7680

CELERY_RESULT_BACKEND = "mongodb"
CELERY_MONGODB_BACKEND_SETTINGS = {
    "host": "localhost",
    "port": 7680,
    "database": "niumang",
    "taskmeta_collection": "celerytasks",
}

CELERYD_CONCURRENCY = 5

CELERYD_LOG_LEVEL = "INFO"
# CELERYD_LOG_FILE = "logs/celery.log"

CELERY_IMPORTS = ("asynctasks", )
