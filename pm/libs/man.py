# -*- coding: utf-8 -*-

import time
import sys
import os
from multiprocessing.dummy import Pool as ThreadPool

from settings import MAX_THREAD_NUM, REDIS_DB_PM, PXELINUX_DIR, PXELINUX_CFGS
from libs import redisoj, mail, utils
from pm.libs import core 


client = redisoj.RedisClient().get(REDIS_DB_PM)


def multi(common_data, email):
    # 取一个列表的 type 和 version, 一批机器的 type 和 version 相同.
    _type = common_data[0]["type"]
    version = common_data[0]["version"]

    # 因为手动安装是使用一个默认的配置文件, 如果多组机器同时安装, 配置文件需要在
    # 所有的机器都安装完成之后删除, 所以用一个队列来保存正在安装的任务.
    default_key = "default:{type}:{version}".format(type=_type, version=version)
    client.lpush(default_key, "")

    # 拷贝默认配置文件.
    # 不能同时安装两种类型的机器;
    # 而且还只能是一个版本.
    cmd = "sudo wget {url} -O {pxelinux_dir}/default".format(
            url=PXELINUX_CFGS[_type][version], pxelinux_dir=PXELINUX_DIR)
    utils.shell(cmd)

    # 执行安装任务.
    pool = ThreadPool(MAX_THREAD_NUM)
    result_item = pool.map(one, common_data)
    pool.close()
    pool.join()

    # 安装完成出队列.
    client.rpop(default_key)

    # 队列为空时, 说明没有任务要执行了, 删除配置文件.
    if len(client.lrange(default_key, 0, -1)) == 0:
        cmd = r"sudo /bin/rm -f /var/lib/tftpboot/pxelinux.cfg/default"
        utils.shell(cmd)

    mail.send(email, u"|wdstack 物理机| 您提交的安装请求已经执行完毕", result_item)

    code = 0
    for item in result_item:
        if item["code"] == 1:
            code = 1
            break
    return_data = {
        "code": code,
        "error_message": None,
        "common_data": common_data,
        "result_item": result_item
    }
    return return_data


def one(item):
    """ 单台机器安装.

    """
    idc = item["idc"]
    sn = item["sn"]
    _type = item["type"]
    version = item["version"]
    usage = item["usage"]
    user_data = item["user_data"]
    node_id = item["node_id"]

    man_oj = core.Man(idc, sn, _type, version, usage, user_data, node_id)
    return man_oj.run(core.wait_result)
