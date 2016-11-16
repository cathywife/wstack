#-*- coding: utf-8 -*-

import os
import time
import logging
from logging.handlers import TimedRotatingFileHandler

from const import LOG_DIR
from const import LOG_NAME


if not os.path.isdir(LOG_DIR):
    os.makedirs(LOG_DIR)


class ParallelTimedRotatingHandler(TimedRotatingFileHandler):
    def doRollover(self):
        """ 
        do a rollover; in this case, a date/time stamp is appended to the 
        filename when the rollover happens.  However, you want the file to
        be named for the start of the interval, not the current time.  
        If there is a backup count, then we have to get a list of matching 
        filenames, sort them and remove the one with the oldest suffix.
        """
        if self.stream:
            self.stream.close()
        # get the time that this sequence started at and make it a TimeTuple
        t = self.rolloverAt - self.interval
        if self.utc:
            timeTuple = time.gmtime(t)
        else:
            timeTuple = time.localtime(t)
        dfn = self.baseFilename + "." + time.strftime(self.suffix, timeTuple)
        if not os.path.exists(dfn):
            os.rename(self.baseFilename, dfn)
        if self.backupCount > 0:
            # find the oldest log file and delete it
            for s in self.getFilesToDelete():
                os.remove(s)
        self.mode = 'a'
        self.stream = self._open()
        currentTime = int(time.time())
        newRolloverAt = self.computeRollover(currentTime)
        while newRolloverAt <= currentTime:
            newRolloverAt = newRolloverAt + self.interval
        #If DST changes and midnight or weekly rollover, adjust for this.
        if (self.when == 'MIDNIGHT' or self.when.startswith('W'))\
                and not self.utc:
            dstNow = time.localtime(currentTime)[-1]
            dstAtRollover = time.localtime(newRolloverAt)[-1]
            if dstNow != dstAtRollover:
             # DST kicks in before next rollover, so we need to deduct an hour
                if not dstNow:  
                    newRolloverAt = newRolloverAt - 3600
             # DST bows out before next rollover, so we need to add an hour
                else:           
                    newRolloverAt = newRolloverAt + 3600
        self.rolloverAt = newRolloverAt


def singleton(cls):
    """ 单例 decorator.

    """
    instances = {}
    def _singleton(*args, **kw):
        if cls not in instances:
            instances[cls] = cls(*args, **kw)
        return instances[cls]
    return _singleton    


@singleton
class LogHandler(object):
    WHEN = "midnight"
    # WHEN = "S"
    BACKUPCOUNT = 7

    logger = logging.getLogger("wdstack_vmagent")
    logger.setLevel(logging.DEBUG)        
    
    # 格式.
    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)-8s] [%(name)-16s] [%(filename)s] [%(funcName)s] [%(lineno)d] %(message)s',
        '%Y-%m-%d %H:%M:%S',)

    # info 日志.
    info_handler = ParallelTimedRotatingHandler(LOG_DIR + "/" + LOG_NAME + "-info.log",
                                                      WHEN, backupCount=BACKUPCOUNT)
    info_handler.propagate = 0
    info_handler.setFormatter(formatter)
    info_handler.setLevel(logging.INFO)
    logger.addHandler(info_handler)

    # warning 日志.
    warning_handler = ParallelTimedRotatingHandler(LOG_DIR + "/" + LOG_NAME + "-warning.log",
                                                         WHEN, backupCount=BACKUPCOUNT)
    warning_handler.propagate = 0
    warning_handler.setFormatter(formatter)
    warning_handler.setLevel(logging.WARNING)
    logger.addHandler(warning_handler)