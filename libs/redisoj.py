#-*- coding: utf-8 -*-

import redis

from libs import utils
from settings import (REDIS_HOST, REDIS_PORT, REDIS_DB_PM, 
                       REDIS_DB_VM, REDIS_DB_COMMON) 


@utils.singleton
class RedisClient(object):
    conn_pool = dict()
    for redis_db in (REDIS_DB_PM, REDIS_DB_VM, REDIS_DB_COMMON):
        conn_pool[redis_db] = redis.connection.BlockingConnectionPool(
                                host=REDIS_HOST, port=REDIS_PORT, 
                                db=redis_db, timeout=60)

    @classmethod
    def get(cls, db):
        return redis.client.Redis(connection_pool=cls.conn_pool[db])
