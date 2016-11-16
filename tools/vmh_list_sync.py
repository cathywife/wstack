#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import logging
import time
import datetime
import traceback
from multiprocessing.dummy import Pool as ThreadPool

from libs import utils as utils_common
from vmmaster.libs import utils
from web.const import LOG_DIR


if not os.path.isdir(LOG_DIR):
    os.makedirs(LOG_DIR)


WHEN = "midnight"
BACKUPCOUNT = 7
logger = logging.getLogger("wdstack-sync")
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter(
    '[%(asctime)s] [%(levelname)-8s] [%(name)-16s] [%(filename)s] [%(funcName)s] [%(lineno)d] %(message)s',
    '%Y-%m-%d %H:%M:%S',)

# info 日志.
info_handler = utils_common.ParallelTimedRotatingHandler("logs/wdstack-sync-info.log",
                                                         WHEN, backupCount=BACKUPCOUNT)
info_handler.propagate = 0
info_handler.setFormatter(formatter)
info_handler.setLevel(logging.INFO)
logger.addHandler(info_handler)

# warning 日志.
warning_handler = utils_common.ParallelTimedRotatingHandler("logs/wdstack-sync-warning.log",
                                                            WHEN, backupCount=BACKUPCOUNT)
warning_handler.propagate = 0
warning_handler.setFormatter(formatter)
warning_handler.setLevel(logging.WARNING)
logger.addHandler(warning_handler)


def sync():
    utils.update_idcs()

    try:
        utils.update_vmhs()
        logger.info("sync vmh list succ")
    except Exception, e:
        logger.warning("sync vmh list fail, exception:{exception}".format(
            exception=traceback.format_exc()))


def main():
    while 1:
        sync()

        time.sleep(600)


if __name__ == '__main__':
    main()