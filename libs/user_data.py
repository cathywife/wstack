#-*- coding: utf-8 -*-

from libs import redisoj
from settings import REDIS_DB_COMMON

import ujson as json


client_common = redisoj.RedisClient().get(REDIS_DB_COMMON)


def get_user_data(hostname):
    """ 获取 user data.

    """
    key = get_key(hostname)
    if client_common.exists(key):
        return json.loads(client_common.get(key))
    else:
        return ""


def set_user_data(hostname, user_data):
    """ 设置 user data.

    """
    key = get_key(hostname)    
    client_common.setex(key, json.dumps(user_data), 3600)


def get_key(hostname):
    return "user_data:{0}".format(hostname)
