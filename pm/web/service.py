# -*- coding: utf-8 -*-

import sys
import os
import ujson as json

import tornado.web

from libs import ldapauth, redisoj, utils
from web.const import REDIS_DB_PM
from pm.libs import check, create, create_man, tmessage


client_pm = redisoj.RedisClient().get(REDIS_DB_PM)


class CheckHandler(tornado.web.RequestHandler):
    @utils.authenticate_decorator
    def post(self):
        """ 检查物理机是否可以正常装机.

        检查项包括:
        1). 是否可以根据 SN 获取到 ILO IP.
        2). 是否能够 获取到 ILO 的密码.
        3). 是否能够设置第二块网卡支持 PXE 启动.
        4). 是否能够设置启动顺序.

        """
        data = json.loads(self.request.body)
        idc = data["idc"]
        device = data["device"]
        sns = data["sns"]
        email = data.get("email", None)

        common_data = list()
        for sn in sns:
            item = {
                "idc": idc, 
                "device": device, 
                "sn": sn
            }
            common_data.append(item)

        return_data = check.multi(common_data, email)
        self.write(json.dumps(return_data))


class CreateHandler(tornado.web.RequestHandler):
    @utils.authenticate_decorator
    def post(self):
        """ 安装物理机.

        步骤包括:
        1). 如果机器在资产系统中, 删掉机器(post 阶段脚本会向资产系统申请 
            hostname 和 ip, 并且进行初始化机器, 初始化之后  status 是
            creating).
        2). 根据 SN 获取到 ILO IP.
        3). 获取到 ILO 的密码.
        4). 设置第二块网卡支持 PXE 启动.
        5). 设置系统启动顺序.
        6). 设置系统 PXE 启动一次.
        7). 拷贝 pxelinux 配置文件.
        8). 重启.
        9). 等待安装完成.
        10). 删除 pxelinux 配置文件.
        11). 在资产系统中把 status 修改成 online.
    
        如果发现资产中没有此机器, 安装失败.

        type 表示支持安装的物理机类型, 目前支持三种, 分别是:
        raw, kvm, docker;

        version 表示支持的操作系统版本, 目前有:
        centos6, centos7

        """
        data = json.loads(self.request.body)
        idc = data["idc"]
        _type = data["type"]
        version = data.get("version", "centos6")
        usage = data["usage"]
        device = data["device"]
        sns = data["sns"]
        user_data = data.get("user_data", None)
        email = data.get("email", None)

        common_data = list()
        for sn in sns:
            item = {
                "idc": idc, 
                "type": _type,
                "version": version,                    
                "usage": usage, 
                "device": device, 
                "sn": sn, 
                "user_data": user_data
            }
            common_data.append(item)

        return_data = create.multi(common_data, email)
        self.write(json.dumps(return_data))


class CreateManHandler(tornado.web.RequestHandler):
    @utils.authenticate_decorator
    def post(self):
        """ 手动安装物理机, 需要部分手动操作.

        步骤包括:
        1). 如果机器在资产系统中, 删掉机器(post 阶段脚本会向资产系统申请 
            hostname 和 ip, 并且进行初始化机器, 初始化之后  status 是
            creating).
        2). 拷贝默认 pxelinux 配置文件.
        3). 手动重启机器, 按 F12 进入 PXE 模式, 
            并选择第二块网卡, 看到 boot 界面直接回车.
        4). 等待安装完成.
        5). 删除默认 pxelinux 配置文件.
        6). 在资产系统中把 status 修改成 online.
    
        如果发现资产中没有此机器, 安装失败.

        """ 
        data = json.loads(self.request.body)
        idc = data["idc"]
        _type = data["type"]
        version = data.get("version", "centos6")
        usage = data["usage"]
        sns = data["sns"]
        user_data = data.get("user_data", None)
        email = data.get("email", None)

        common_data = list()
        for sn in sns:
            item = {
                "idc": idc, 
                "type": _type, 
                "version": version,
                "usage": usage, 
                "sn": sn, 
                "user_data": user_data
            }
            common_data.append(item)

        # 首先检查是否有其他 type 和 version 的机器正在安装, 
        # 如果有, 退出; 如果没有, 才继续.
        running_tasks = client_pm.keys("default*")
        if len(running_tasks) > 1:
            error_message = "other different task is running:{running_tasks}".format(
                running_tasks=running_tasks)
            return_data = {
                "code": -1, 
                "error_message": error_message
            }
            self.write(json.dumps(return_data))
            self.finish()

        return_data = create_man.multi(common_data, email)
        self.write(json.dumps(return_data))


class MessageHandler(tornado.web.RequestHandler):
    @utils.authenticate_decorator
    def get(self):
        sn = self.get_argument("sn")
        self.write(json.dumps(tmessage.query(sn)))

    @utils.authenticate_decorator
    def post(self):
        sn = self.get_argument("sn")
        hostname = self.get_argument("hostname")
        ip = self.get_argument("ip")
        tmessage.setup(sn, hostname, ip)