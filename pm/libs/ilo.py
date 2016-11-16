# -*- coding: utf-8 -*-

import os
import sys
import time

import pexpect

from libs import log, utils
from web.const import ILO_PASSWDS, PXELINUX_CFGS


logger = log.LogHandler().logger


def get_ip(idc, sn):
    """ 获取 ilo ip.

    """
    cmd = "nslookup idrac-{sn}.ilo.nosa.me. ddns0.{idc}.nosa.me ".format(
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
            logger.warning("sn:{sn}, {cmd} pexpect.EOF".format(sn=sn, cmd=cmd))
            ssh.close()
            pass
        except pexpect.TIMEOUT:
            logger.warning("sn:{sn}, {cmd} pexpect.TIMEOUT".format(sn=sn, cmd=cmd))
            ssh.close()
            pass
    raise Exception("sn:{sn}, exec {cmd}".format(sn=sn, cmd=cmd))


class Generate(object):
    """ ilo 操作.

    """
    def __init__(self, idc, sn):
        self.idc = idc
        self.sn = sn

        self.ip = get_ip(self.idc, self.sn)    
        self.passwd = get_passwd(self.ip, self.sn)

    def ssh_cmd(self, cmd):
        new_cmd = '''ssh -o StrictHostKeyChecking=no '''\
                  '''-o ConnectTimeout=600 root@{ip} "{cmd}" '''.format(
                        ip=self.ip, cmd=cmd)
        logger.info(new_cmd)
        ssh = pexpect.spawn(new_cmd, timeout=600)
        ssh.expect([pexpect.TIMEOUT, 'password: '])
        ssh.sendline(self.passwd)
        time.sleep(1)
        return ssh.read()

    def get_nic_name(self, device):
        cmd = r"racadm get NIC.NICConfig"
        r = self.ssh_cmd(cmd)
        ret = r.find("NIC.Integrated")

        if ret != -1:
            if device == "em1":
                return "NIC.Integrated.1-1-1"
            return "NIC.Integrated.1-2-1"
        else:
            ret1 = r.find("NIC.Embedded")
            if ret1 != -1:
                if device == "em1":
                    return "NIC.Embedded.1-1-1"
                return "NIC.Embedded.2-1-1"

        return "NIC.Integrated.1-2-1"   # 默认

    def get_nic_config(self, nic):
        cmd = r"racadm get NIC.NICConfig"
        tmp = self.ssh_cmd(cmd)
        for i in tmp.splitlines():
            if nic in i:
                NicConfig = i.split()[0]
                break
        if "NicConfig" not in locals():
            raise Exception("no nic config, %s output is %s" % (cmd, tmp))
        return NicConfig

    def check_boot_order(self, nic_seq):
        cmd = r"racadm get BIOS.BiosBootSettings.BootSeq"
        lines = self.ssh_cmd(cmd)
        ret = lines.find("BootSeq={nic_seq}".format(nic_seq=nic_seq))
        if ret == -1:
            raise Exception("boot order error, %s output is %s" % (cmd, lines))

    def get_boot_order(self, nic):
        return "HardDisk.List.1-1,{nic}".format(nic=nic)

    def setup_boot_order(self, nic_seq):
        cmd = r"racadm set BIOS.BiosBootSettings.BootSeq {nic_seq}".format(nic_seq=nic_seq)
        r = self.ssh_cmd(cmd)
        index = r.find("Successfully", 0)
        if index == -1:
            raise Exception("setup boot order error, %s output is %s" % (cmd, r))

        cmd = r"racadm jobqueue delete --all"
        self.ssh_cmd(cmd)

        cmd = r"racadm jobqueue create BIOS.Setup.1-1 -r pwrcycle -s TIME_NOW"
        r = self.ssh_cmd(cmd)
        index = r.find("Successfully", 0)
        if index == -1:
            raise Exception("setup boot order error, %s output is %s" % (cmd, r))

        # 这个时间是为了让机器重启使配置生效,不设置的話这个 jobqueue 
        # 可能会后面的代码清掉,导致安装失败。
        time.sleep(600)

    def get_nic_pxeboot(self, nic):
        NicConfig = self.get_nic_config(nic)

        if nic not in ["NIC.Embedded.2-1-1", "NIC.Embedded.1-1-1", 
            "NIC.Integrated.1-2-1", "NIC.Integrated.1-1-1"]:
            raise Exception("nic not support:%s" % nic)
        cmd = r"racadm get {NicConfig}.LegacyBootProto".format(NicConfig=NicConfig)

        r = self.ssh_cmd(cmd)
        index = r.find("LegacyBootProto=PXE", 0)
        if index == -1:
            raise Exception("not support pxe boot:%s" % r)

    def setup_nic_pxeboot(self, nic):
        NicConfig = self.get_nic_config(nic)

        cmd0 = r"racadm jobqueue delete --all"

        cmd1 = r"racadm set %s.LegacyBootProto PXE" % NicConfig

        if nic == "NIC.Embedded.2-1-1":
            cmd2 = r"racadm jobqueue create NIC.Embedded.2-1-1 -r pwrcycle -s TIME_NOW"
        elif nic == "NIC.Embedded.1-1-1":
            cmd2 = r"racadm jobqueue create NIC.Embedded.1-1-1 -r pwrcycle -s TIME_NOW"
        elif nic == "NIC.Integrated.1-2-1":
            cmd2 = r"racadm jobqueue create NIC.Integrated.1-2-1 -r pwrcycle -s TIME_NOW"
        elif nic == "NIC.Integrated.1-1-1":
            cmd2 = r"racadm jobqueue create NIC.Integrated.1-1-1 -r pwrcycle -s TIME_NOW"
        else:
            raise Exception("nic not support:%s" % nic)

        self.ssh_cmd(cmd0)

        r = self.ssh_cmd(cmd1)
        index = r.find("Successfully", 0)
        if index == -1:
            raise Exception(cmd1)

        r = self.ssh_cmd(cmd2)
        index = r.find("Successfully", 0)
        if index == -1:
            raise Exception(cmd2)

        # 这个时间是为了让机器重启使配置生效, 不设置的話这个
        #  jobqueue 可能会后面的代码清掉, 导致安装失败.
        time.sleep(600)

    def setup_pxeboot_once(self):
        cmd = r"racadm config -g cfgServerInfo -o cfgServerBootOnce 1"
        r = self.ssh_cmd(cmd)
        ret = r.find("Object value modified successfully")
        if ret == -1:
            raise Exception("setup pxeboot once fail, %s output is %s" % (cmd, r))
        cmd = r"racadm config -g cfgServerInfo -o cfgServerFirstBootDevice PXE"
        r = self.ssh_cmd(cmd)
        ret = r.find("Object value modified successfully")
        if ret == -1:
            raise Exception("setup pxeboot once fail, %s output is %s" % (cmd, r))

    def get_sn(self):
        cmd = r"racadm getsvctag"
        r = self.ssh_cmd(cmd)
        second_line = r.splitlines()[1]
        return second_line.strip()

    def get_mac(self, nic):
        cmd = "racadm getsysinfo -s"
        r = self.ssh_cmd(cmd)
        mac_cmd = '''echo "%s" | grep "%s" | awk '{print $4}' ''' % (r, nic)
        format_mac = utils.shell(mac_cmd, logger=logger).replace(":", "-").lower()
        constract_mac = "01-%s" % format_mac
        return constract_mac.strip()

    def constract_tftp(self, _type, version, mac):
        cmd = r"sudo /bin/cp -f {path} /var/lib/tftpboot/pxelinux.cfg/{mac}".format(
                path=PXELINUX_CFGS[_type][version], mac=mac)
        utils.shell(cmd, logger=logger)

    def del_tftp(self, mac):
        cmd = r"sudo /bin/rm -f /var/lib/tftpboot/pxelinux.cfg/{mac}".format(mac=mac)
        utils.shell(cmd, logger=logger)

    def reboot(self):
        cmd = r"racadm serveraction powercycle"
        r = self.ssh_cmd(cmd)
        ret = r.find("Server power operation successful")
        if ret == -1:
            raise Exception("reboot fail, %s output is %s" % (cmd, r))
