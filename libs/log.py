#-*- coding: utf-8 -*-

import os
import logging

from libs import utils

from settings import LOG_DIR
from settings import LOG_NAME


if not os.path.isdir(LOG_DIR):
    os.makedirs(LOG_DIR)


@utils.singleton
class LogHandler(object):
    WHEN = "midnight"
    # WHEN = "S"
    BACKUPCOUNT = 7

    logger = logging.getLogger("wdstack")
    logger.setLevel(logging.DEBUG)    

    # 格式.
    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)-8s] [%(name)-16s] [%(filename)s] [%(funcName)s] [%(lineno)d] %(message)s',
        '%Y-%m-%d %H:%M:%S',)

    # info 日志.
    info_handler = utils.ParallelTimedRotatingHandler(LOG_DIR + "/" + LOG_NAME + "-info.log",
                                                      WHEN, backupCount=BACKUPCOUNT)
    info_handler.propagate = 0
    info_handler.setFormatter(formatter)
    info_handler.setLevel(logging.INFO)
    logger.addHandler(info_handler)

    # warning 日志.
    warning_handler = utils.ParallelTimedRotatingHandler(LOG_DIR + "/" + LOG_NAME + "-warning.log",
                                                         WHEN, backupCount=BACKUPCOUNT)
    warning_handler.propagate = 0
    warning_handler.setFormatter(formatter)
    warning_handler.setLevel(logging.WARNING)
    logger.addHandler(warning_handler)
