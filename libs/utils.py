#-*- coding: utf-8 -*-

import subprocess
import re
import random
import os
import time
import logging
from logging.handlers import TimedRotatingFileHandler
import uuid


def shell(cmd, exception=True, logger=None, strip=False):
    process = subprocess.Popen(args = cmd, 
        stdout = subprocess.PIPE, stderr = subprocess.PIPE, 
        shell = True)
    std_out, std_err = process.communicate()
    return_code = process.poll()

    if return_code == 0:
        if logger is not None:
            logger.info("cmd:{cmd}".format(cmd=cmd))
    else:
        message = "cmd:{cmd}, std_err:{std_err}".format(cmd=cmd, std_err=std_err)
        if logger is not None:
            logger.warning(message)
        if exception:
            raise Exception(message)
        else:
            return
    if strip:
        return std_out.strip()
    else:
        return std_out


def is_valid_ip(ip):
    """Returns true if the given string is a well-formed IP address.

    Supports IPv4 and IPv6.

    """
    import socket
    if not ip or '\x00' in ip:
        return False
    try:
        res = socket.getaddrinfo(ip, 0, socket.AF_UNSPEC,
                                 socket.SOCK_STREAM,
                                 0, socket.AI_NUMERICHOST)
        return bool(res)
    except socket.gaierror as e:
        if e.args[0] == socket.EAI_NONAME:
            return False
        raise
    return True


# def dns_resolv(hostname):
#     import sys, socket
#     result = socket.getaddrinfo(sys.argv[1], None)
#     return result[0][4]


def random_id():
    total_len = 10
    base_str1 = [str(i) for i in range(0, 10)]
    base_str2 = [chr(i)
                 for i in range(ord('a'), ord('z') + 1)]
    random.seed()
    total_sample = []
    total_sample += random.sample(base_str1, random.randint(1, len(base_str1)))
    total_sample += random.sample(base_str2, total_len - len(total_sample))
    random.shuffle(total_sample)
    return ''.join(total_sample)


def random_uuid():
    return str(uuid.uuid4())


def singleton(cls):
    """ 单例 decorator.

    """
    instances = {}
    def _singleton(*args, **kw):
        if cls not in instances:
            instances[cls] = cls(*args, **kw)
        return instances[cls]
    return _singleton


def authenticate_decorator(func):
    def __authenticate_decorator(*args, **kwargs):
        self = args[0]
        user_email = self.get_secure_cookie("user")
        if user_email:
            fs = user_email.split("@")
            if fs[1] != "nosa.me":
                self.clear_cookie("user")
                self.write(
                    "You have to login with your nosa.me account...")
                return
            else:
                apply(func, args, kwargs)
        else:
            self.redirect("/login")

    return __authenticate_decorator


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


# class SingleLevelFilter(logging.Filter):
#     def __init__(self, passlevel, reject):
#         self.passlevel = passlevel
#         self.reject = reject

#     def filter(self, record):
#         if self.reject:
#             return (record.levelno != self.passlevel)
#         else:
#             return (record.levelno == self.passlevel)
