# -*- coding: utf-8 -*-

import os
import sys
import time
import re
import traceback

import ujson as json
import pexpect

from libs import (log, redisoj, utils, mail, 
                  user_data, node, puppet,
                  asset_utils, dns_utils)

from settings import ILO_PASSWDS, REDIS_DB_PM, PXELINUX_DIR, PXELINUX_CFGS


logger = log.LogHandler().logger
client = redisoj.RedisClient().get(REDIS_DB_PM)


def get_ip(idc, sn):
    """ 获取 ilo ip.

    """
    cmd = "nslookup idrac-{sn}.ilo.DOMAIN.COM. ddns0.{idc}.DOMAIN.COM".format(
        sn=sn, idc=idc)
    return utils.shell(cmd, logger=logger, strip=True).splitlines()[-1].split(":")[-1].strip()


def get_passwd(ip, sn):
    """ 获取 ilo passwd.

    """
    for passwd in ILO_PASSWDS:
        cmd = '''ssh -oStrictHostKeyChecking=no root@{ip} '''\
              '''"racadm getsvctag" '''.format(ip=ip)
        logger.info(cmd)
        ssh = pexpect.spawn(cmd)
        try:
            i = ssh.expect(
                ["password:"], timeout=180)
            if i == 0:
                ssh.sendline(passwd)
                ret = ssh.read()
                if sn in ret:
                    return passwd
        except pexpect.EOF:
            logger.warning("sn:{0}, cmd:{1}, error:pexpect.EOF".format(sn, cmd))
            ssh.close()
            pass
        except pexpect.TIMEOUT:
            logger.warning("sn:{0}, cmd:{1}, error:pexpect.TIMEOUT".format(sn, cmd))
            ssh.close()
            pass
    raise Exception("sn:{0}, cmd:{1}, error:get ilo passwd fail".format(sn, cmd))


def exception(func):
    def _decorator(*args, **kwargs):
        oj = args[0]
        try:
            # 执行安装.
            func(*args, **kwargs)
        except Exception, e:
            oj.code = 1
            oj.error_message = traceback.format_exc()
            logger.error("{0} install fail, error:{1}".format(oj.sn, oj.error_message))
            return oj.__dict__

        logger.info("{0} install success, info:{1}".format(oj.sn, oj.__dict__))

        oj.code = 0
        oj.error_message = None
        return oj.__dict__

    return _decorator


class Ilo(object):
    """ ilo 操作.

    """
    def __init__(self, idc, sn):
        self.idc = idc
        self.sn = sn

    def get_ip(self):
        self.ip = get_ip(self.idc, self.sn)    

    def get_passwd(self):
        self.passwd = get_passwd(self.ip, self.sn)

    def ssh_cmd(self, cmd):
        new_cmd = '''ssh -o StrictHostKeyChecking=no -o ConnectTimeout=60 root@{0} "{1}" '''.format(
                        self.ip, cmd)
        logger.info(new_cmd)
        ssh = pexpect.spawn(new_cmd, timeout=600)
        ssh.expect([pexpect.TIMEOUT, 'password: '])
        ssh.sendline(self.passwd)
        time.sleep(1)
        return ssh.read()

    def get_nic_name(self, device):
        cmd = r"racadm get NIC.NICConfig"
        ret = self.ssh_cmd(cmd)

        if "NIC.Integrated" in ret:
            if device == "em1":
                return "NIC.Integrated.1-1-1"
            return "NIC.Integrated.1-2-1"
        else:
            if "NIC.Embedded" in ret:
                if device == "em1":
                    return "NIC.Embedded.1-1-1"
                return "NIC.Embedded.2-1-1"

        return "NIC.Integrated.1-2-1"   # 默认

    def get_nic_config(self, nic):
        cmd = r"racadm get NIC.NICConfig"
        ret = self.ssh_cmd(cmd)
        for i in ret.splitlines():
            if nic in i:
                NicConfig = i.split()[0]
                break
        if "NicConfig" not in locals():
            raise Exception("no nic config, cmd:{0}, error:{1}".format(cmd, ret))
        return NicConfig

    def check_boot_order(self, nic_seq):
        cmd = r"racadm get BIOS.BiosBootSettings.BootSeq"
        ret = self.ssh_cmd(cmd)
        if "BootSeq={0}".format(nic_seq) not in ret:
            raise Exception("boot order error, cmd:{0}, error:{1}".format(cmd, ret))

    def get_boot_order(self, nic):
        return "HardDisk.List.1-1,{0}".format(nic)

    def setup_boot_order(self, nic_seq):
        cmd = r"racadm set BIOS.BiosBootSettings.BootSeq {0}".format(nic_seq)
        ret = self.ssh_cmd(cmd)
        if "Successfully" not in ret:
            raise Exception("cmd:{0} ,error:{1}".format(cmd, ret))

        cmd = r"racadm jobqueue delete --all"
        self.ssh_cmd(cmd)

        cmd = r"racadm jobqueue create BIOS.Setup.1-1 -r pwrcycle -s TIME_NOW"
        ret = self.ssh_cmd(cmd)
        if "Successfully" not in ret:
            raise Exception("cmd:{0} ,error:{1}".format(cmd, ret))

        jid_pattern = re.compile("(JID_\d+)", re.M)
        jid = jid_pattern.search(ret).groups()[0]
        self.wait_job(jid)

    def get_nic_pxeboot(self, nic):
        if nic not in ["NIC.Embedded.2-1-1", "NIC.Embedded.1-1-1", "NIC.Integrated.1-2-1", "NIC.Integrated.1-1-1"]:
            raise Exception("nic not support:{0}".format(nic))

        NicConfig = self.get_nic_config(nic)
        cmd = r"racadm get {0}.LegacyBootProto".format(NicConfig)
        ret = self.ssh_cmd(cmd)
        if "LegacyBootProto=PXE" not in ret:
            raise Exception("not support pxe boot, error:{0}".format(ret))

    def setup_nic_pxeboot(self, nic):
        cmd0 = r"racadm jobqueue delete --all"

        NicConfig = self.get_nic_config(nic)
        cmd1 = r"racadm set {0}.LegacyBootProto PXE".format(NicConfig)

        if nic == "NIC.Embedded.2-1-1":
            cmd2 = r"racadm jobqueue create NIC.Embedded.2-1-1 -r pwrcycle -s TIME_NOW"
        elif nic == "NIC.Embedded.1-1-1":
            cmd2 = r"racadm jobqueue create NIC.Embedded.1-1-1 -r pwrcycle -s TIME_NOW"
        elif nic == "NIC.Integrated.1-2-1":
            cmd2 = r"racadm jobqueue create NIC.Integrated.1-2-1 -r pwrcycle -s TIME_NOW"
        elif nic == "NIC.Integrated.1-1-1":
            cmd2 = r"racadm jobqueue create NIC.Integrated.1-1-1 -r pwrcycle -s TIME_NOW"
        else:
            raise Exception("{0} not support".format(nic))

        self.ssh_cmd(cmd0)

        ret = self.ssh_cmd(cmd1)
        if "Successfully" not in ret:
            raise Exception("cmd:{0}, error:{1}".format(cmd1, ret))

        ret = self.ssh_cmd(cmd2)
        if "Successfully" not in ret:
            raise Exception("cmd:{0}, error:{1}".format(cmd2, ret))

        jid_pattern = re.compile("(JID_\d+)", re.M)
        jid = jid_pattern.search(ret).groups()[0]
        self.wait_job(jid)

    def setup_pxeboot_once(self):
        cmd = r"racadm config -g cfgServerInfo -o cfgServerBootOnce 1"
        ret = self.ssh_cmd(cmd)
        if "Object value modified successfully" not in ret:
            raise Exception("setup pxeboot once fail, cmd:{0}, error:{1}".format(cmd, ret))
        cmd = r"racadm config -g cfgServerInfo -o cfgServerFirstBootDevice PXE"
        ret = self.ssh_cmd(cmd)
        if "Object value modified successfully" not in ret:
            raise Exception("setup pxeboot once fail, cmd:{0}, error:{1}".format(cmd, ret))

    def get_sn(self):
        cmd = r"racadm getsvctag"
        ret = self.ssh_cmd(cmd)
        return ret.splitlines()[1].strip()

    def get_mac(self, nic):
        cmd = "racadm getsysinfo -s"
        ret = self.ssh_cmd(cmd)
        mac_pattern = re.compile("^{0}.*\s+(\S+)$".format(nic))
        for line in ret.strip().splitlines():
            g = mac_pattern.match(line)
            if g is not None:
                mac = g.groups()[0]
                break
        format_mac = "01-{0}".format(mac.replace(":", "-").lower())
        return format_mac

    def constract_tftp(self, _type, version, mac):
        cmd = "sudo wget {url} -O {pxelinux_dir}/{mac}".format(
                url=PXELINUX_CFGS[_type][version], 
                pxelinux_dir=PXELINUX_DIR, 
                mac=mac)
        utils.shell(cmd, logger=logger)

    def del_tftp(self, mac):
        cmd = r"sudo /bin/rm -f {pxelinux_dir}/{mac}".format(
            pxelinux_dir=PXELINUX_DIR, mac=mac)
        utils.shell(cmd, logger=logger)

    def reboot(self):
        cmd = r"racadm serveraction powercycle"
        ret = self.ssh_cmd(cmd)
        if "Server power operation successful" not in ret:
            raise Exception("reboot fail, cmd:{0}, error:{1}".format(cmd, ret))

    def wait_job(self, jid):
        status_pattern = re.compile("Status.*Completed", re.M | re.I)
        cmd = "racadm jobqueue view -i {0}".format(jid)

        timeout = 600
        interval = 30
        timetotal = 0
        while timetotal < timeout:
            ret = self.ssh_cmd(cmd)
            if status_pattern.search(ret):
                return
            else:
                timetotal += interval
        raise Exception("wait for job {0} timeout, cmd:{1}".format(jid, cmd))


class Auto(Ilo):
    """ 自动装机.

    注意:
        把设置网卡支持PXE启动 放在 设置系统启动顺序 前面,
        是为了避免 网卡是None的时候 无法设置 启动顺序的奇葩问题.
        (因为网卡是 None 的时候,启动顺序里面可能看不到 这个网卡,也就无法设置!!!
    """
    def __init__(self, idc, sn, _type, version, usage, device, user_data, node_id):
        Ilo.__init__(self, idc, sn)
        self.type = _type
        self.version = version
        self.usage = usage
        self.device = device
        self.user_data = user_data
        self.node_id = node_id

    @exception
    def run(self, wait_func):
        # 获取 ip 和 passwd.
        self.get_ip()
        self.get_passwd()

        # 查询网卡名称.
        nic = self.get_nic_name(self.device)
    
        # 设置网卡支持 PXE 启动.
        try:
            self.get_nic_pxeboot(nic)
        except Exception, e:
            self.setup_nic_pxeboot(nic)
    
        # 设置启动顺序.
        nic_seq = self.get_boot_order(nic)
        try:
            self.check_boot_order(nic_seq)
        except Exception, e:
            self.setup_boot_order(nic_seq)
    
        # 设置机器从 PXE 启动一次.
        self.setup_pxeboot_once()
    
        # 拷贝 pxelinux 配置文件.
        mac = self.get_mac(nic)
        self.constract_tftp(self.type, self.version, mac)

        # 重启.
        self.reboot()
    
        # 等待安装, 并获取 hostname 和 ip.
        wait_func(self)

        # 删除 pxelinux 配置文件.
        self.del_tftp(mac)

        return self.__dict__


class Man(Ilo):
    """ 手动装机, 需要部分手动操作.
    
    """
    def __init__(self, idc, sn, _type, version, usage, user_data, node_id):
        Ilo.__init__(self, idc, sn)
        self.type = _type
        self.version = version
        self.usage = usage
        self.user_data = user_data
        self.node_id = node_id

    @exception
    def run(self, wait_func):    
        # 等待安装, 并获取 hostname 和 ip.
        wait_func(self)

        return self.__dict__


def wait_result(oj):
    """ 等待安装, 并获取结果.

    """
    # 如果机器在资产系统中, 删掉机器(post 阶段脚本会向资产系统申请 
    # hostname 和 ip, 并且进行初始化机器, 初始化之后  status 是
    # creating).
    # 放在 reboot 之后的原因是防止删除之后 agent 继续上报.
    if asset_utils.is_exist_for_sn(oj.sn):
        asset_utils.delete_from_sn(oj.sn)

    # 安装信息进 redis.
    client.hset(oj.sn, "idc", json.dumps(oj.idc))
    client.hset(oj.sn, "usage", json.dumps(oj.usage))

    client.hset(oj.sn, "hostname", json.dumps(""))
    client.hset(oj.sn, "ip", json.dumps(""))

    # 循环等待安装完成.
    timeout = 1500
    interval = 15
    timetotal = 0

    installed = False
    in_asset = False

    while timetotal < timeout:
        if not installed:
            hostname = json.loads(client.hget(oj.sn, "hostname"))
            ip = json.loads(client.hget(oj.sn, "ip"))

            if "" in [hostname, ip]:
                time.sleep(interval)
                timetotal += interval
            else:
                installed = True
                # 设置 hostname, ip
                oj.hostname = hostname
                oj.ip = ip

                # 清除 puppet 证书.
                puppet.check_puppet_cert(oj.hostname)
                # 设置 user_data, 装机之后机器会获取并执行 user_data 中的内容.
                user_data.set_user_data(oj.hostname, oj.user_data)
                # 设置 node id, 配置机器会使用.
                node.set_node_id(oj.hostname, oj.node_id)

                # 增加 DNS.
                if dns_utils.record_exist(oj.hostname):
                    dns_utils.record_delete(oj.hostname)
                dns_utils.record_add(oj.hostname, oj.ip)
        elif installed and not in_asset:
            try:
                status = asset_utils.get_value_from_sn(oj.sn, "status")
                if status == "online":
                    in_asset = True
                    break
            except Exception, e:
                pass
            finally:
                time.sleep(interval)
                timetotal += interval

    # 检查安装完成情况.
    if not installed:
        raise Exception("install timeout")
    elif installed and not in_asset:
        raise Exception("install success, but not uploaded to asset sys")
    else:
        # 绑定节点.
        asset_utils.bind_server_to_node(oj.node_id, [oj.hostname])
