# -*- coding: utf-8 -*-

import sys
import os
import ujson as json

from concurrent.futures import ThreadPoolExecutor
from functools import partial, wraps

import tornado.web
from tornado import gen

from libs import utils as utils_common
from libs import asset_utils
from libs import ldapauth, redisoj
from web.const import REDIS_DB_VM
from vmmaster.libs import instance, wmi, utils


redis_client_vm = redisoj.RedisClient().get(REDIS_DB_VM)

EXECUTOR = ThreadPoolExecutor(max_workers=500)


def unblock(f):
    @tornado.web.asynchronous
    @wraps(f)
    def wrapper(*args, **kwargs):
        self = args[0]

        def callback(future):
            self.write(future.result())
            self.finish()

        EXECUTOR.submit(
            partial(f, *args, **kwargs)
        ).add_done_callback(
            lambda future: tornado.ioloop.IOLoop.instance().add_callback(
                partial(callback, future)))
    return wrapper


class InstancesHandler(tornado.web.RequestHandler):
    def post(self):
        """ 创建一个 instance.

        创建 instance 有两种方式:
        1. 通过 wmi 创建, 当 type 是 wmi 时是此种方式, 此时
           需要指定 wmi_id 参数;
        2. 通过 原始方式创建, 也就是用 virt-install 命令创建,
           当 type 是 origin 时是这种方式, 默认是这种方式.

        另外, 支持自动选取宿主机或是手动指定宿主机, 用变量 auto_vmhs 
        指定, 如果 auto_vmhs 为 False(默认为 True), 表示手动选择宿主机, 
        否则是自动选择宿主机, 当 auto_vmhs 是 False 时, 需要指定 vmhs
        参数, 它是一个 list, vmhs 的长度就是 创建 instance 的个数, 
        所以这时候 num 参数无效了.

        user_data 用于装机之后执行自定义脚本.

        """
        data = json.loads(self.request.body)

        area = data["area"]

        # 通过哪种方式创建, 为 wmi 表示通过 wmi 创建, 需要指定 
        # wmi_id 参数; 当为 origin 表示通过传统方式创建.
        _type = data.get("type", "origin")

        # 当 type 为 wmi 时, 有效.
        wmi_id = data.get("wmi_id", None)

        # 如果 auto_vmhs 为 False 表示手动选取宿主机, 需要指定
        # vmhs 参数, 否则自动选取宿主机.
        auto_vmhs = data.get("auto_vmhs", True)

        # auto_vmhs 为 False 时, 需要此参数.
        vmhs = data.get("vmhs", None)

        # auto_vmhs 不为 False 时, 需要此参数.
        num = data.get("num", None)

        idc = data["idc"]
        vcpu = data["vcpu"]
        mem = data["mem"]
        data_size = data["data_size"]

        # type 为 origin 参数时, 才需要此参数.
        version = data.get("version", None)

        usage = data["usage"]
        user_data = data.get("user_data", None)
        email = data.get("email", None)
        
        instance_create = instance.Create(area, _type, wmi_id, auto_vmhs, 
                            vmhs, num, version, vcpu, mem, data_size, idc, 
                            usage, user_data, email)
        self.write(json.dumps(instance_create.run()))


class InstanceHandler(tornado.web.RequestHandler):

    @utils_common.authenticate_decorator
    def post(self):
        """ 操作一个 Instance, 包括删除, 关闭, 重启等.

        oper 表示是操作类型, 包括 delete, shutdown 和 reboot 等.
        
        _list 应该是一个 list, list 里的元素是 dict.
    
        type 可以为 hostname 或者 vmh, 分别表示根据 主机名 
        还是根据 宿主机来操作.
    
        如果 type 是 hostname, dict 类似:
            {
                "hostname": "test200.hy01"
            }
        如果 type 是 vmh, dict 类似:
            {
                "vmh": "vmh1000.hy01",
                "vmname": "vm10"
            }

        这里删除一个 Instance 会删除它所有的资源, 包括 Volume, 
        虽然 AWS 还会保留 Volume, 我们暂时没必要保存.

        """
        data = json.loads(self.request.body)

        oper = data["oper"]
        _type = data["type"]
        _list = data["list"]
        email = data.get("email", None)

        instance_oper = instance.Oper(oper, _type, _list, email)
        self.write(json.dumps(instance_oper.run()))


class WmisHandler(tornado.web.RequestHandler):

    def get(self):
        """ 查看所有 Wmi.

        """
        self.write(json.dumps(wmi.gets()))

    @unblock
    def post(self):
        """ 创建一个 Wmi.

        把一个 虚拟机做成 Wmi.

        有两种方式:
        一种是根据 主机名, 系统会自动查找 虚拟机所在的宿主机和 vmname;
        另一种是直接指定宿主机和 vmname.

        用 type 来指定创建方式.

        excludes 表示排除的目录, 只支持 /home 下面的目录, 
        多个目录以逗号分隔, 默认自动排除 log 或 logs 目录.
        写法类似:
        work/asset_agent_v2/logs/*,work/tomcat/logs/*

        """
        data = json.loads(self.request.body)

        _type = data["type"]
        wmi_name = data["wmi_name"]
        hostname = data.get("hostname", None)
        vmh = data.get("vmh", None)
        vmname = data.get("vmname", None)
        excludes = data.get("excludes", None)
        email = data.get("email", None)

        wmi_create = wmi.Create(_type, wmi_name, hostname, 
                                vmh, vmname, excludes, email)
        return json.dumps(wmi_create.run())


class WmiHandler(tornado.web.RequestHandler):

    def get(self, wmi_id):
        """ 查看 一个 Wmi 的信息.

        """
        self.write(json.dumps(wmi.get(wmi_id)))

    def delete(self, wmi_id):
        """ 删除 一个 Wmi.

        """
        wmi.delete(wmi_id)
        ret = {
            "code": 0, 
            "message": "deleted"
        }
        self.write(json.dumps(ret))


class QueryHandler(tornado.web.RequestHandler): 
    @unblock
    def get(self):
        """ 用传统方式装机时, 在装机 post 阶段机器根据 ip 来请求
            主机名,掩码和网关.            

        """
        ip = self.get_argument("ip")
        ret = utils.get_vminfo_from_ip(ip)        
        return json.dumps(ret)


class IgnoresHandler(tornado.web.RequestHandler):
    def get(self):
        """ 查看被忽略的宿主机列表.

        """
        self.write(json.dumps(utils.get_ignores()))

    def post(self):
        """ 增加被忽略的宿主机列表.

        """
        data = json.loads(self.request.body)

        sns = data["sns"]
        utils.add_ignore(sns)


class IgnoreHandler(tornado.web.RequestHandler):
    def delete(self, sns):
        """ 删除被忽略的宿主机列表.

        """
        data = json.loads(self.request.body)

        sns = data["sns"]
        utils.del_ignore(sns)


class VmhsHandler(tornado.web.RequestHandler):
    def get(self):
        """ 查看宿主机列表(不包含忽略的宿主机).

        """
        area = self.get_argument("area", None)
        idc = self.get_argument("idc", None)
        self.write(json.dumps(utils.get_vmhs(area, idc)))


class ResourcesHandler(tornado.web.RequestHandler):
    @unblock
    def get(self):
        """ 查看资源状况.

        """
        area = self.get_argument("area", None)
        idc = self.get_argument("idc", None)
        sort = self.get_argument("sort", 1)
        show_ignores = self.get_argument("show_ignores", 0)
        show_vms = self.get_argument("show_vms", 0)

        vmhs = utils.get_vmhs(area, idc)

        return_list = list()
        for vmh in vmhs:
            _dict = {
                "vmh": vmh,
                "data": {
                    "vcpu": utils.get_info(vmh, "vcpu"),
                    "mem": utils.get_info(vmh, "mem"),
                    "space": utils.get_info(vmh, "space"),
                    "vmlist": utils.get_info(vmh, "vmlist"),
                    "type": utils.get_info(vmh, "type"),
                }
            }
            return_list.append(_dict)

        if show_ignores != 0 and show_ignores != "0":
            ignore_vmhs = utils.get_ignore_vmhs()
            for i in xrange(len(return_list)):
                if return_list[i]["vmh"] in ignore_vmhs:
                    return_list[i]["ignored"] = True
                else:
                    return_list[i]["ignored"] = False

        if show_vms != 0 and show_vms != "0":
            for i in xrange(len(return_list)):

                if return_list[i]["data"]["vmlist"] == []:
                    return_list[i]["vms"] = []
                else:             
                    sn = asset_utils.get_sn_from_hostname(return_list[i]["vmh"])
                    try:
                        return_list[i]["vms"] = [x["hostname"] for x in 
                            asset_utils.query_from_sn(sn)["vms"]]
                    except Exception, e:
                        return_list[i]["vms"] = []

        def _key(d):
            return d["data"]["vcpu"]["free"], \
                d["data"]["mem"]["free"], \
                d["data"]["space"]["free"]
        if sort == 1 or sort == "1":
            return_list.sort(key=_key, reverse=True)
        return json.dumps(return_list)
