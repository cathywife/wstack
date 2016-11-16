#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import logging
import time
import datetime
import traceback
from multiprocessing.dummy import Pool as ThreadPool

from libs import utils as utils_common, asset_utils
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
    for vmh in utils.get_vmhs():
        try:
            ip = asset_utils.get_ip_from_hostname(vmh)
            network = utils.get_network_from_ip(ip)
            utils.add_network(vmh, network)

            utils.update_info_from_rpc(vmh)

            logger.info("sync vmh info succ, vmh:{vmh}".format(vmh=vmh))
        except Exception, e:
            logger.warning("sync vmh info fail, vmh:{vmh}, exception:{exception}".format(
                vmh=vmh, exception=traceback.format_exc()))


def main():
    while 1:
        sync()

        tomorrow_now = datetime.datetime.now() + datetime.timedelta(days=1)
        string = tomorrow_now.strftime("%Y-%m-%d")
        tomorrow_zero = datetime.datetime.strptime(string, "%Y-%m-%d")
        tomorrow_zero.strftime("%s")
        tomorrow_zero_seconds = int(tomorrow_zero.strftime("%s"))
        time.sleep(tomorrow_zero_seconds + 3600 - time.time())


if __name__ == '__main__':
    main()