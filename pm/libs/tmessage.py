# -*- coding: utf-8 -*-

""" 查询和设置 hostname 和 ip.

"""

import ujson as json

from libs import redisoj
from web.const import REDIS_DB_PM


client = redisoj.RedisClient().get(REDIS_DB_PM)


def query(sn):
    idc = json.loads(client.hget(sn, "idc"))
    usage = json.loads(client.hget(sn, "usage"))

    return {
        "idc": idc, 
        "usage": usage
    }


def setup(sn, hostname, ip):
    client.hset(sn, "hostname", json.dumps(hostname))
    client.hset(sn, "ip", json.dumps(ip))