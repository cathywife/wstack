# -*- coding: utf-8 -*-

""" 手动装机, 需要部分手动操作.
    
"""

import time
import sys
import os
from multiprocessing.dummy import Pool as ThreadPool

import ujson as json

from web.const import (MAX_THREAD_NUM, PXELINUX_CFGS, 
                      REDIS_DB_PM, REDIS_DB_COMMON)
from libs import redisoj, log, mail, asset_utils, dns_utils
from libs import utils as common_utils
from pm.libs import utils 


logger = log.LogHandler().logger
client = redisoj.RedisClient().get(REDIS_DB_PM)
client_user_data = redisoj.RedisClient().get(REDIS_DB_COMMON)


def multi(common_data, email):
    # 取一个列表的 type 和 version, 一批机器的 type 和 version 相同.
    _type = common_data[0]["type"]
    version = common_data[0]["version"]

    # 因为手动安装是使用一个默认的配置文件, 如果多组机器同时安装, 配置文件需要在
    # 所有的机器都安装完成之后删除, 所以用一个队列来保存正在安装的任务.
    default_key = "default:{type}:{version}".format(type=type, version=version)
    client.lpush(default_key, "")

    # 拷贝默认配置文件.
    # 不能同时安装两种类型的机器;
    # 而且还只能是一个版本.
    cmd = "sudo /bin/cp -f {path} /var/lib/tftpboot/pxelinux.cfg/default".format(
        path=PXELINUX_CFGS[_type][version])
    common_utils.shell(cmd)

    # 执行安装任务.
    pool = ThreadPool(MAX_THREAD_NUM)
    result_data = pool.map(one, common_data)
    pool.close()
    pool.join()

    # 安装完成出队列.
    client.rpop(default_key)

    # 队列为空时, 说明没有任务要执行了, 删除配置文件.
    if len(client.lrange(default_key, 0, -1)) == 0:
        cmd = r"sudo /bin/rm -f /var/lib/tftpboot/pxelinux.cfg/default"
        common_utils.shell(cmd)

    mail.send(email, u"|wdstack 物理机| 您提交的安装请求已经执行完毕", result_data)
    logger.info(result_data)

    code = 0
    for data in result_data:
        if data["code"] == 1:
            code = 1
            break
    return_data = {
        "code": code,
        "error_message": None,
        "common_data": common_data,
        "result_data": result_data
    }
    return return_data


@utils.exception
def one(data):
    """ 单台机器安装.

    """
    idc = data["idc"]
    sn = data["sn"]
    _type = data["type"]
    version = data["version"]
    usage = data["usage"]
    user_data = data["user_data"]

    # 如果机器在资产系统中, 删掉机器(post 阶段脚本会向资产系统申请 
    # hostname 和 ip, 并且进行初始化机器, 初始化之后  status 是
    # creating).
    # 有一个问题:
    # 此种安装方式是手动安装, 为了防止删除之后 agent 继续上报, 
    # 应该在安装前手动把机器关机.
    if asset_utils.is_exist_for_sn(sn):
        asset_utils.delete_from_sn(sn)

    # 安装系统进入 redis.
    client.hset(sn, "idc", json.dumps(idc))
    client.hset(sn, "usage", json.dumps(usage))

    client.hset(sn, "hostname", json.dumps(""))
    client.hset(sn, "ip", json.dumps(""))

    # 设置 user_data, 装机之后机器会获取并执行 user_data 中的内容.
    if user_data is None:
        client_user_data.exists(sn) and client_user_data.delete(sn) 
    else:
        client_user_data.set(sn, json.dumps(user_data))

    # 循环等待安装完成.
    installed, in_asset, hostname, ip = utils.wait(sn)

    # 检查安装完成情况.
    if not installed:
        raise Exception("install timeout")
    elif installed and not in_asset:
        raise Exception("install success,but not uploaded to asset sys")
    else:    
        # 检查 hostname 是否已经成功添加 DNS.
        recordred = dns_utils.record_exist(hostname)
        if not recordred:
            raise Exception("dns add fail")

    data["hostname"] = hostname
    data["ip"] = ip
    return data
