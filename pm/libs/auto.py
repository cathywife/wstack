# -*- coding: utf-8 -*-

import time
import sys
import os
from multiprocessing.dummy import Pool as ThreadPool

from settings import MAX_THREAD_NUM
from libs import mail
from pm.libs import core 


def multi(common_data, email):
    pool = ThreadPool(MAX_THREAD_NUM)

    result_data = pool.map(one, common_data)
    pool.close()
    pool.join()

    mail.send(email, u"|wdstack 物理机| 您提交的安装请求已经执行完毕", result_data)

    code = 0
    for item in result_data:
        if item["code"] == 1:
            code = 1
            break
    return_data = {
        "code": code,
        "error_message": None,
        "common_data": common_data,
        "result_data": result_data
    }
    return return_data


def one(item):
    idc = item["idc"]
    sn = item["sn"]
    _type = item["type"]
    version = item["version"]
    usage = item["usage"]
    device = item["device"]
    user_data = item["user_data"]
    node_id = item["node_id"]

    auto_oj = core.Auto(idc, sn, _type, version, usage, device, user_data, node_id)
    return auto_oj.run(core.wait_result)
