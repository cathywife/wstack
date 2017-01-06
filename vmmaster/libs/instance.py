#-*- coding: utf-8 -*-

""" instance 的操作.

"""

import copy
import traceback
from multiprocessing.dummy import Pool as ThreadPool

import ujson as json

from libs import asset_utils, dns_utils, log, mail, redisoj, user_data, node, puppet
from libs import utils as utils_common
from vmmaster.libs import utils, wmi
from settings import (LOCATIONS, NETMASK_DEFAULT, KSS, BRIDGE_DEFAULT,
                       OS_SIZE, REDIS_DB_VM, VM_AREAS)


class Create(object):
    """ 创建 instance.

    创建 instance 有两种方式:
    1. 通过 wmi 创建, 当 type 是 wmi 时是此种方式, 此时
       需要指定 wmi_id 参数;

    这里要注意两点:
    1). 使用 wmi 创建虚拟机, 也需要指定 meal 和 data_size, 这点和 aws 一样;
    2). 如果 os_size 或 data_size 小于 wmi 中的数据盘空间, 以 wmi 中的为准.

    2. 通过 原始方式创建, 也就是用 virt-install 命令创建,
       当 type 是 origin 时是这种方式, 默认是这种方式.

    另外, 支持自动选取宿主机或是手动指定宿主机, 用变量 auto_vmhs
    指定, 如果 auto_vmhs 为 False(默认为 True), 表示手动选择宿主机,
    否则是自动选择宿主机, 当 auto_vmhs 是 False 时, 需要指定 vmhs
    参数, 它是一个 list, vmhs 的长度就是 创建 instance 的个数,
    所以这时候 num 参数无效了.

    """
    def __init__(self, area, _type, wmi_id, auto_vmhs, vmhs,
                 num, version, vcpu, mem, data_size, idc,
                 usage, user_data, node_id, email):

        """
        common_data 任务的公共数据;
        unique_data 每个宿主机任务的数据;
        code 装机任务返回值, 0 表示任务执行并成功, -1 表示任务未执行, 1表示任务执行但失败;
        error_message 表示失败信息.

        对于每个宿主机上的任务, 也有 code 和 error_message, 0 表示成功, 1 表示失败.

        """
        self.area = area
        self.type = _type
        self.wmi_id = wmi_id
        self.auto_vmhs = auto_vmhs
        self.vmhs = vmhs
        self.num = num
        self.version = version
        self.vcpu = vcpu
        self.mem = mem * 1024   # 这里以 M 计算.
        self.data_size = data_size
        self.idc = idc
        self.usage = usage
        self.user_data = user_data
        self.node_id = node_id
        self.email = email

        self.vm_areas = VM_AREAS
        self.os_size = OS_SIZE
        self.locations = LOCATIONS
        self.kss = KSS
        self.network = NETMASK_DEFAULT
        self.bridge = BRIDGE_DEFAULT

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
            self.get_common_data()
            self.get_vmhs()
            self.get_unique_data()
            self.logger.info(self.unique_data)
        except Exception, e:
            self.logger.warning(traceback.format_exc())
            self.code = -1
            self.error_message = traceback.format_exc()

            return_data = {
                "code": self.code,
                "error_message": self.error_message
            }
            if hasattr(self, "common_data"):
                return_data["common_data"] = self.common_data
            mail.send(self.email, u"|wdstack 虚拟机| 您提交的安装请求已经执行完毕", str(return_data))
            return return_data

        pool = ThreadPool()
        result_data = pool.map(self.one, self.unique_data)
        pool.close()
        pool.join()

        for x in result_data:
            if x["code"] != 0:
                self.code = 1
                break

        return_data = {
            "code": self.code,
            "error_message": self.error_message,
            "common_data": self.common_data,
            "result_data": result_data
        }
        mail.send(self.email, u"|wdstack 虚拟机| 您提交的安装请求已经执行完毕", self.unique_data)
        return return_data

    def one(self, data):
        """ 单个虚拟机创建函数.

        """
        rpc_client = data["rpc_client"]
        try:
            rpc_client.instance_create(data)
            utils.wait_status(data["sn"])
            asset_utils.bind_server_to_node(data["node_id"], [data["hostname"]])
        except Exception, e:
            # 装失败了, 清理工作.
            asset_utils.delete_from_sn(data["sn"])
            dns_utils.record_delete(data["hostname"])

            error_message = traceback.format_exc()
            self.logger.warning(error_message)
            data["code"] = 1
            data["error_message"] = error_message
            return data

        data["code"] = 0
        data["error_message"] = None
        return data

    def get_unique_data(self):
        """ 获取每个装机任务需要的信息.

        """
        self.unique_data = list()
        for vmh in self.vmhs:
            # 拷贝一份 common data.
            data = copy.deepcopy(self.common_data)

            # 保存宿主机.
            data["vmh"] = vmh

            # 保存 rpc_client.
            data["rpc_client"] = utils.get_rpc_client(data["vmh"])

            # 更新宿主机资源.
            for item in ("vcpu", "mem", "space"):
                x = utils.get_info(data["vmh"], item)
                if item == "space":
                    x["free"] = x["free"] - self.os_size - self.data_size
                else:
                    x["free"] = x["free"] - getattr(self, item)
                utils.update_info(data["vmh"], item, x)

            # 获取 vmname 并更新 vmname.
            data["vmname"] = utils.get_vmname(data["vmh"])
            utils.update_vmname(data["vmh"], data["vmname"])

            # 生成虚拟机的 uuid, 并且当做虚拟机的 sn.
            data["sn"] = data["uuid"] = utils_common.random_uuid()

            # 获取 hostname, ip, network 和 gateway 信息.
            # 获取 hostname, ip 成功后, 会自动在资产系统中创建记录, status 为
            # creating, 等待 agent 上报资产后, 变成 online.
            network = utils.get_network(data["vmh"])
            hostname, ip = asset_utils.apply_hostname_ip(data["sn"], "vm",
                data["usage"], data["idc"], network)
            gateway = utils.get_gateway_from_ip(ip)
            data["hostname"] = hostname
            data["ip"] = ip
            data["network"] = network
            data["gateway"] = gateway

            # 清除 puppet 证书.
            puppet.check_puppet_cert(hostname)

            # 增加 DNS.
            if dns_utils.record_exist(data["hostname"]):
                dns_utils.record_delete(data["hostname"])
            dns_utils.record_add(hostname, ip)

            # 不同的 type 要有不同的处理.
            if self.type == "wmi":
                # 当 type 等于 wmi 时, agent 会修改镜像的 ip 和 hostname.
                pass
            else:
                # 如果不是 wmi, 装机 post 脚本会来请求拿到 hostname.
                self.client.set(data["ip"], data["hostname"])

            # 记录 hostname 和 ip.
            self.logger.info("hostname:{hostname}, ip:{ip}".format(
                hostname=data["hostname"], ip=data["ip"]))

            # 设置 user data, 机器装好之后会取数据.
            self.set_user_data(data["hostname"])

            # 设置 node_id.
            self.set_node_id(data["hostname"])

            # 保存 data.
            self.unique_data.append(data)

    def check(self):
        """ 参数检查.

        """
        if self.area not in self.vm_areas:
            message = "{area} not exists".format(area=self.area)
            raise Exception(message)
        if self.type not in ["origin", "wmi"]:
            message = "type {type} not correct".format(type=self.type)
            raise Exception(message)
        if self.type == "wmi" and self.wmi_id is None:
            message = "wmi_id not assigned"
            raise Exception(message)
        if self.auto_vmhs == False and self.vmhs is None:
            message = "vmhs not assigned"
            raise Exception(message)
        if self.auto_vmhs != False and self.num is None:
            message = "num not assigned"
            raise Exception(message)
        if self.idc not in utils.get_idcs():
            message = "idc not exists"
            raise Exception(message)

    def get_vmhs(self):
        """ 拿到宿主机列表.

        如果采用 wmi, os_size 小于 wmi 的数据盘大小, 则重设 os_size;
        data 盘采用用户定义的值.

        """
        if self.type == "wmi":
            wmi_data = wmi.get(self.wmi_id)
            if self.os_size < int(wmi_data["os"]["size"].strip("G")):
                self.os_size = int(wmi_data["os"]["size"].strip("G"))
            #if self.data_size < int(wmi_data["data"]["size"].strip("G")):
            #    self.data_size = int(wmi_data["data"]["size"].strip("G"))

        if self.auto_vmhs == False:   # 如果手动指定宿主机.
            self.num = len(self.vmhs)   # 创建虚拟机数量.
            # 如果是手动指定宿主机, 我们忽略 CPU 和 内存的检查, 只检查硬盘.
            for vmh in self.vmhs:
                space = utils.get_info(vmh, "space")
                if space["free"] - int(self.data_size) - self.os_size < 0:
                    message = "{0} space not enough, there is only {1}G left while requried {2}G".format(vmh, space["free"], int(self.data_size) + self.os_size)
                    raise Exception(message)
        else:   # 如果自动指定宿主机.
            if self.area == "test":
                vmhs = utils.get_vmhs_on_demand(self.area, self.idc, self.num, self.vcpu,
                                                self.mem, self.data_size, True)
            else:
                if self.vcpu <= 4:   # 如果 vcpu 不大于4, 从小到大的顺序选取宿主机.
                    vmhs = utils.get_vmhs_on_demand(self.area, self.idc, self.num, self.vcpu,
                                                    self.mem, self.data_size, False)
                else:
                    vmhs = utils.get_vmhs_on_demand(self.area, self.idc, self.num, self.vcpu,
                                                    self.mem, self.data_size, True)
            if not vmhs:
                message = "resource not enough"
                raise Exception(message)
            self.vmhs = vmhs
        self.logger.info(self.vmhs)

    def get_common_data(self):
        """ 获取公共数据.

        """
        data = dict()
        data["vcpu"] = self.vcpu
        data["mem"] = self.mem
        data["netmask"] = self.network
        data["bridge"] = self.bridge
        data["os_size"] = "{os_size}G".format(os_size=self.os_size)
        data["data_size"] = "{data_size}G".format(data_size=self.data_size)
        data["type"] = self.type
        data["area"] = self.area
        if self.type == "wmi":
            data["wmi_id"] = self.wmi_id
        else:
            data["location"] = self.locations[self.version]
            data["version"] = self.version
            data["ks"] = self.kss[self.version]
        data["auto_vmhs"] = self.auto_vmhs
        data["vmhs"] = self.vmhs
        data["version"] = self.version
        data["num"] = self.num
        data["idc"] = self.idc
        data["usage"] = self.usage
        data["user_data"] = self.user_data
        data["node_id"] = self.node_id
        data["email"] = self.email
        self.common_data = data
        self.logger.info(self.common_data)

    def set_user_data(self, hostname):
        """ 设置 user data.

        装机之后机器会获取并执行 user_data 中的内容.

        """
        user_data.set_user_data(hostname, self.user_data)

    def set_node_id(self, hostname):
        """ 设置 node_id.

        用于配置机器.

        """
        node.set_node_id(hostname, self.node_id)


class Oper(object):
    """ 操作 instance.

    操作类型包括 删除, 重启, 关机.

    """
    def __init__(self, oper_type, _type, unique_data, email):
        """
        common_data 任务的公共数据;
        unique_data 每个宿主机任务的数据;
        code 装机任务返回值, 0 表示任务执行并成功, -1 表示任务未执行, 1表示任务执行但失败;
        error_message 表示失败信息.

        对于每个宿主机上的任务, 也有 code 和 error_message, 0 表示成功, 1 表示失败.

        """
        self.oper_type = oper_type
        self.type = _type
        self.unique_data = unique_data
        self.email =  email

        self.logger = log.LogHandler().logger

        # 初始化任务的 code 和 error_message.
        self.code = 0
        self.error_message = None

        # 对操作类型定义中文, 为了发邮件.
        if self.oper_type == "delete":
            self.oper_type_cn = u"删除"
        elif self.oper_type == "reboot":
            self.oper_type_cn = u"重启"
        elif self.oper_type == "shutdown":
            self.oper_type_cn = u"关机"
        else:
            raise Exception("oper_type not correct")

    def run(self):
        """ 启动函数.

        """
        try:
            self.check()
            self.get_common_data()   # unique_data 不依赖 common_data.
            self.get_unique_data()
            self.logger.info(self.unique_data)
        except Exception, e:
            self.logger.warning(str(e))
            self.code = -1
            self.error_message = str(e)

            return_data = {
                "code": self.code,
                "error_message": self.error_message
            }
            if hasattr(self, "common_data"):
                return_data["common_data"] = self.common_data
            mail.send(self.email, u"|wdstack 虚拟机| 您提交的{oper_type_cn}请求已经执行完毕".format(
                oper_type_cn=self.oper_type_cn), str(return_data))
            return return_data

        pool = ThreadPool()
        result_data = pool.map(self.one, self.unique_data)
        pool.close()
        pool.join()

        for x in result_data:
            if x["code"] != 0:
                self.code = 1
                break

        return_data = {
            "code": self.code,
            "error_message": self.error_message,
            "common_data": self.common_data,
            "result_data": result_data
        }
        mail.send(self.email, u"|wdstack 虚拟机| 您提交的{oper_type_cn}请求已经执行完毕".format(
            oper_type_cn=self.oper_type_cn), self.unique_data)
        return return_data

    def one(self, data):
        """ 单个虚拟机操作函数.

        """
        rpc_client = data["rpc_client"]
        try:
            instance_key = "instance_{oper_type}".format(oper_type=self.oper_type)
            getattr(rpc_client, instance_key)(data["vmname"])
        except Exception, e:
            error_message = traceback.format_exc()
            self.logger.warning(error_message)
            data["code"] = 1
            data["error_message"] = error_message
            return data

        data["code"] = 0
        data["error_message"] = None
        utils.update_info_from_rpc(data["vmh"])
        return data

    def check(self):
        """ 参数检查.

        """
        if self.type == "hostname":
            for d in self.unique_data:
                if "hostname" not in d:
                    raise Exception("hostname is missing")
        elif self.type == "vmh":
            for d in self.unique_data:
                if "vmh" not in d or "vmname" not in d:
                    raise Exception("vmh or vmname is missing")
        else:
            raise Exception("type not exists")

    def get_common_data(self):
        """ 获取公共数据.

        """
        common_data = {
            "oper_type": self.oper_type,
            "type": self.type,
            "email": self.email
        }
        self.common_data = common_data

    def get_unique_data(self):
        """ 当 type 是 hostname, 重新生成 data.

        data 中每个元素是个 dict, 每个 dict
        有一个字段: hostname.

        本函数输出新的 data, 每个 dict 加入 hostname 所在的
        vmh 和 vmname.

        """
        unique_data = list()
        if self.type == "hostname":
            for d in self.unique_data:
                hostname = d["hostname"]

                data = utils.get_vmname_from_hostname(hostname)
                data["sn"] = asset_utils.get_sn_from_hostname(hostname)
                data["rpc_client"] = utils.get_rpc_client(data["vmh"])
                unique_data.append(data)
        else:
            for d in self.unique_data:
                data = copy.deepcopy(d)
                data["rpc_client"] = utils.get_rpc_client(data["vmh"])
                unique_data.append(data)
        self.unique_data = unique_data
