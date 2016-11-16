# -*- coding: utf-8 -*-

""" 把设置网卡支持PXE启动 放在 设置系统启动顺序 前面,
    是为了避免 网卡是None的时候 无法设置 启动顺序的奇葩问题.
    (因为网卡是None的时候,启动顺序里面可能看不到 这个网卡,也就无法设置!!!)

"""

import time
from multiprocessing.dummy import Pool as ThreadPool

import ujson as json

from web.const import MAX_THREAD_NUM
from libs import log, mail
from pm.libs import ilo, utils


logger = log.LogHandler().logger


def multi(common_data, email):
    pool = ThreadPool(MAX_THREAD_NUM)

    result_data = pool.map(one, common_data)
    pool.close()
    pool.join()

    mail.send(email, u"|wdstack 物理机| 您提交的检查请求已经执行完毕", result_data)
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
    """ 检查是否能够正常安装.

    """
    idc = data["idc"]
    sn = data["sn"]
    device = data["device"]

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