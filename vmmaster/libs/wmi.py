#-*- coding: utf-8 -*-

""" wmi 的操作.

"""

import time
import traceback

import ujson as json

from libs import asset_utils, log, mail, redisoj
from libs import utils as common_utils
from web.const import VM_AREAS, REDIS_DB_VM
from vmmaster.libs import utils


class Create(object):
    """ 创建 wmi.

    """
    def __init__(self, _type, wmi_name, hostname, vmh, vmname, excludes, email):
        """
        data 任务的公共数据;
        unique_data 每个宿主机任务的数据;
        code 装机任务返回值, 0 表示任务执行并成功, -1 表示任务未执行, 1表示任务执行但失败;
        error_message 表示失败信息.

        """
        self.type = _type
        self.wmi_name =  wmi_name
        self.hostname =  hostname
        self.vmh =  vmh
        self.vmname =  vmname
        self.excludes =  excludes
        self.email =  email

        self.logger = log.LogHandler().logger
        self.client = redisoj.RedisClient().get(REDIS_DB_VM)

        # 初始化任务的 code 和 error_message.
        self.code = 0
        self.error_message = None

    def run(self):
        """ 启动函数.

        """
        try:
            self.check()
            self.get_data()
        except Exception, e:
            self.logger.warning(traceback.format_exc())
            self.code = -1
            self.error_message = traceback.format_exc()

            return_data = {
                "code": self.code,
                "error_message": self.error_message
            }
            if hasattr(self, "data"):
                return_data["data"] = self.data
            mail.send(self.email, u"|wdstack 镜像| 您提交的创建请求已经执行完毕", str(return_data))                
            return return_data

        try:
            _os, _data, _partition = self.data["rpc_client"].wmi_create(
                self.data["wmi_id"], self.data["wmi_name"], 
                self.data["vmname"], self.data["excludes"])
        except Exception, e:
            self.logger.warning(traceback.format_exc())
            self.code = 1
            self.error_message = traceback.format_exc()

            return_data = {
                "code": self.code,
                "error_message": self.error_message,
                "data": self.data
            }
            mail.send(self.email, u"|wdstack 镜像| 您提交的创建请求已经执行完毕", str(return_data))
            return return_data

        ctime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        wmi_data = {
            "name": self.wmi_name,
            "ctime": ctime,
            "os": _os,
            "data": _data,
            "partition": _partition   # 仅在 raw 格式的宿主机上基于镜像创建虚拟机的时候才用到.
        }
        self.client.set("wmi:"+self.data["wmi_id"], json.dumps(wmi_data))   # key 以 wmi: 为前缀.

        self.logger.info(str(wmi_data))
        self.code = 0

        return_data = {
            "code": self.code,
            "error_message": self.error_message,
            "data": self.data,
            "result_data": wmi_data
        }
        mail.send(self.email, u"|wdstack 镜像| 您提交的创建请求已经执行完毕", [self.data])        
        return return_data

    def check(self):
        """ 参数检查.

        """    
        if self.type == "hostname":
            if self.hostname is None:
                raise Exception("hostname is missing")
        elif self.type == "vmh":
            if self.vmh is None or self.vmname is None:
                raise Exception("vmh or vmname is missing")
        else:
            raise Exception("type not exists")

    def get_data(self):
        """ 当 type 是 hostname, 生成 vmh 和 vmname.

        """
        data = {
            "type": self.type,
            "hostname": self.hostname,
            "vmh": self.vmh,
            "vmname": self.vmname,
            "wmi_name": self.wmi_name,
            "excludes": self.excludes,
            "email": self.email
        }
        if self.type == "hostname":
            x = utils.get_vmname_from_hostname(self.hostname)
            data["vmh"] = x["vmh"]
            data["vmname"] = x["vmname"]
        # 生成 wmi id, 作为 wmi 的资源标识.
        # 随机生成的10位字符串是有几率重复, 只
        # 不过几率很小, 此是一坑.
        data["wmi_id"] = common_utils.random_id()        
        data["rpc_client"] = utils.get_rpc_client(data["vmh"])
        self.data = data


def get(_id):
    """ 查看某个 wmi 的信息.

    """
    key = "wmi:" + _id
    client = redisoj.RedisClient().get(REDIS_DB_VM)
    return json.loads(client.get(key))


def gets():
    """ 查看全部 wmi 的信息.

    """
    client = redisoj.RedisClient().get(REDIS_DB_VM)
    def _get(key):
        import re
        _id = re.sub("^wmi:", "", key)
        return {
            "id": _id,
            "data": get(_id)
        }
    return map(_get, client.keys("wmi:*"))


def delete(_id):
    """ 删除一个 wmi.

    """    
    client = redisoj.RedisClient().get(REDIS_DB_VM)
    client.delete("wmi:"+_id)
