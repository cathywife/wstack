# -*- coding: utf-8 -*-

""" 把设置网卡支持PXE启动 放在 设置系统启动顺序 前面,
    是为了避免 网卡是None的时候 无法设置 启动顺序的奇葩问题.
    (因为网卡是 None 的时候,启动顺序里面可能看不到 这个网卡,也就无法设置!!!)

"""

import time
import sys
import os
from multiprocessing.dummy import Pool as ThreadPool

import ujson as json

from web.const import MAX_THREAD_NUM
from web.const import REDIS_DB_PM, REDIS_DB_COMMON
from libs import redisoj, log, mail, asset_utils, dns_utils
from pm.libs import ilo, utils


logger = log.LogHandler().logger
client = redisoj.RedisClient().get(REDIS_DB_PM)
client_user_data = redisoj.RedisClient().get(REDIS_DB_COMMON)


def multi(common_data, email):
    pool = ThreadPool(MAX_THREAD_NUM)

    result_data = pool.map(one, common_data)
    pool.close()
    pool.join()

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
    device = data["device"]
    user_data = data["user_data"]

    # 获取 ilo 对象.
    ilo_oj = ilo.Generate(idc, sn)

    # 查询网卡名称.
    nic = ilo_oj.get_nic_name(device)

    # 设置网卡支持 PXE 启动.
    try:
        ilo_oj.get_nic_pxeboot(nic)
    except Exception, e:
        ilo_oj.setup_nic_pxeboot(nic)

    # 设置启动顺序.
    nic_seq = ilo_oj.get_boot_order(nic)
    try:
        ilo_oj.check_boot_order(nic_seq)
    except Exception, e:
        ilo_oj.setup_boot_order(nic_seq)

    # 设置机器从 PXE 启动一次.
    ilo_oj.setup_pxeboot_once()

    # 拷贝 pxelinux 配置文件.
    mac = ilo_oj.get_mac(nic)
    ilo_oj.constract_tftp(_type, version, mac)

    # 重启.
    ilo_oj.reboot()

    # 如果机器在资产系统中, 删掉机器(post 阶段脚本会向资产系统申请 
    # hostname 和 ip, 并且进行初始化机器, 初始化之后  status 是
    # creating).
    # 放在 reboot 之后的原因是防止删除之后 agent 继续上报.
    if asset_utils.is_exist_for_sn(sn):
        asset_utils.delete_from_sn(sn)
        logger.info("{sn} deleted in asset".format(sn=sn))

    # 安装信息进 redis.
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

    # 删除 pxelinux 配置文件.
    ilo_oj.del_tftp(mac)

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
