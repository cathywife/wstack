#-*- coding: utf-8 -*-

from libs import redisoj
from settings import REDIS_DB_COMMON

import ujson as json


client_common = redisoj.RedisClient().get(REDIS_DB_COMMON)


def get_node_id(hostname):
    """ 基于 hostname 获取 node id.

    """
    key = get_key(hostname)
    if client_common.exists(key):
        return json.loads(client_common.get(key))
    else:
        return 0


def set_node_id(hostname, node_id):
    """ 设置 node id.

    """
    key = get_key(hostname)    
    client_common.setex(key, json.dumps(node_id), 3600)


def get_key(hostname):
    return "node_id:{0}".format(hostname)
