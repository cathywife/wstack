#-*- coding: utf-8 -*-

""" 虚拟机实例函数.

"""

import os

import redis

from libs import (log, utils, volume, interface, 
                  wmi, template, storage)
from settings import DOMAIN, ISO_URLS, NAMESERVER


logger = log.LogHandler().logger


def create_origin(name, uuid, version, vcpu, mem, os_size, data_size, 
                  ip, location, netmask, gateway, ks, bridge):
    """ 用传统方法创建 instance.

    """
    # 确认 IP 是否合法.
    if not utils.is_valid_ip(ip):
        message = "ip:{ip} is illegal".format(ip=ip)
        logger.warning(message)
        raise Exception(message)

    # 如果没有 location, 则下载.
    if not os.path.isfile(location):
        cmd = ''' wget {url} -O {location}'''.format(
            url=ISO_URLS[version], location=location)
        utils.shell(cmd)

    # 创建系统盘.
    os_volume_path = volume.create(name, os_size)

    # 执行安装操作.
    cmd = """virt-install --name {name} --uuid {uuid} --vcpus={vcpu} --ram {mem} """\
        """--disk path={os_volume_path} -localtime --accelerate """\
        """--location={location} -x "ip={ip} netmask={netmask} gateway={gateway} """\
        """dns={dns} dnsdomain={dnsdomain} ks={ks} console=tty0 console=ttyS0,115200n8" """\
        """--nographics --network bridge={bridge} --noautoconsole &>/dev/null""".format(
        name=name, uuid=uuid, vcpu=vcpu, mem=mem, os_volume_path=os_volume_path, 
        location=location, ip=ip, netmask=netmask, gateway=gateway, dns=NAMESERVER, 
        dnsdomain=DOMAIN, ks=ks, bridge=bridge)
    utils.shell(cmd)

    # 设置自动启动.
    cmd = "virsh autostart {name}".format(name=name)
    utils.shell(cmd)

    # 创建数据盘, 盘的标识是 ${name}_data.
    data_volume = name + "_data"    
    data_volume_path = volume.create(data_volume, data_size)

    # 默认也会自动增加第二块网卡.
    interface.add(name, "br1")

    # 删除一些无用配置, 不删的话起不来(第二种存储结构有问题, 第一种没问题).
    cmd = """sed -i '/<kernel>/d' /etc/libvirt/qemu/{name}.xml;
             sed -i '/<initrd>/d' /etc/libvirt/qemu/{name}.xml;
             sed -i '/<cmdline>/d' /etc/libvirt/qemu/{name}.xml;
             virsh define /etc/libvirt/qemu/{name}.xml
            """.format(name=name)
    utils.shell(cmd)

    # 这里是安装完成之后自动重启.
    check_cmd = "virsh list | grep -q {name} ".format(name=name)
    start_cmd = "sleep 1 && sh libs/guestfish_origin.sh {name} {uuid} && virsh start {name} && sleep 1 ".format(
        name=name, uuid=uuid)
    if utils.check_wait(check_cmd, start_cmd):
        logger.info("post start {name} success".format(name=name))
    else:
        message = "post start {name} timeout".format(name=name)
        logger.warning(message)
        raise Exception(message)

    # 关联成 instance 的 vdb, 在装机完成之后 attach 的原因是:
    # 我发现在装机开始就 attach 的话, vdb 会被搞成 swap, 
    # pvcreate 的时候就会失败.
    volume.attach(name, data_volume_path, "vdb")


def create_wmi(name, uuid, vcpu, mem, os_size, data_size, ip, 
               hostname, wmi_id, netmask, gateway, bridge):
    """ 根据 wmi 创建 instance.

    大概步骤是这样:
    1. 根据 wmi_id 获取到 wmi 的信息, 数据结构类似.
    2. 创建相应的系统盘和数据盘.
    3. 下载对应的镜像, 覆盖掉上一步创建的盘.
    4. 如果要求的 size 比 镜像中的大, 则增大空间.
    5. 根据模板文件生成虚拟机配置文件, 需修改:
       1). 硬盘信息;   # 最麻烦
       2). 网卡信息;
       3). name;
       4). uuid;
       5). vcpu;
       6). mem;
    6. 定义配置文件, 修改系统镜像.
    7. 启动系统.
    8. 增加虚拟机机器的 DNS 记录.

    """
    # 确认 IP 是否合法.
    if not utils.is_valid_ip(ip):
        message = "ip:{ip} is illegal".format(ip=ip)
        logger.warning(message)
        raise Exception(message)

    # 获取 wmi 数据.
    wmi_data = wmi.get(wmi_id)

    os_name = name
    os_volume_path = volume.create(os_name, os_size)

    data_name = name + "_data"
    data_volume_path = volume.create(data_name, data_size)

    os_url = wmi_data["os"]["url"]
    # 对于 qcow2 格式的系统盘, 直接 wget, 并重置大小.
    if volume.path_type(os_volume_path) == "qcow2":
        utils.wget(os_url, os_volume_path)
        if int(os_size.strip("G")) > int(wmi_data["os"]["size"].strip("G")):
            volume.resize(os_name, os_size)
        if int(data_size.strip("G")) > int(wmi_data["data"]["size"].strip("G")):
            volume.resize(data_name, data_size)

    # 对于 raw 格式的系统盘, 不能使用 wget.
    # 一种选择是使用 qemu-img convert -O raw 命令, 
    # 但是会有系统盘大小的数据写入, 给 IO 造成很大压力.
    # 这里我使用 分区表 的方式来减少 IO.
    if volume.path_type(os_volume_path) == "raw":
        storage.restore_rawos_from_qcow2_image(os_volume_path, wmi_data)
    
    # 数据盘初始化.
    init_data_volume_cmd = """virt-format -a {data_volume_path} --lvm=/dev/datavg/home --filesystem=ext4""".format(
        data_volume_path=data_volume_path)
    try:
        utils.shell(init_data_volume_cmd)
    except Exception, e:
        utils.shell("yum -y update qemu-kvm")
        utils.shell(init_data_volume_cmd)

    # tar-in 数据到数据盘.
    tar_in_cmd = """curl {data_url} | guestfish add {data_volume_path} : run : mount /dev/datavg/home / : tar-in - / compress:gzip""".format(
        data_url=wmi_data["data"]["url"], data_volume_path=data_volume_path)
    utils.shell(tar_in_cmd)

    # volumes 用于创建配置文件.
    if volume.path_type(os_volume_path) == "qcow2":
        disk_type = "file"
        driver_type = "qcow2"
        source_type = "file"
    else:
        disk_type = "block"
        driver_type = "raw"
        source_type = "dev"    
    volumes = [
        {
            "file": os_volume_path, 
            "dev": "vda",
            "disk_type": disk_type,
            "driver_type": driver_type,
            "source_type": source_type

        },
        {
            "file": data_volume_path, 
            "dev": wmi_data["data"]["device"],
            "disk_type": disk_type,
            "driver_type": driver_type,
            "source_type": source_type
        }
    ]

    # 生成网卡 MAC 地址.
    interface_br1 = utils.random_mac()
    interface_br2 = utils.random_mac()

    # 生成配置文件.
    _dict = {
        "name": name,
        "uuid": uuid,
        "vcpu": vcpu,
        "memory": int(mem) * 1024,
        "currentmemory": int(mem) * 1024,
        "volumes": volumes,
        "interface_br1": interface_br1,
        "interface_br2": interface_br2
    }
    template.gen(_dict)

    # 对镜像进行修改.
    cmd = """ sh libs/guestfish_wmi.sh {name} {uuid} {ip} {netmask} {gateway} {hostname} {hwaddr_em2} {hwaddr_em1} """.format(
            name=name, uuid=uuid, ip=ip, netmask=netmask, gateway=gateway, 
            hostname=hostname, hwaddr_em2=interface_br2, 
            hwaddr_em1=interface_br1)
    utils.shell(cmd)


def create(data):
    """ 创建一个 instance.

    """
    _type = data["type"]

    area = data["area"]
    uuid = data["uuid"]
    name = data["vmname"]
    vcpu = data["vcpu"]
    mem = data["mem"]
    os_size = data["os_size"]
    data_size = data["data_size"]
    ip = data["ip"]
    netmask = data["netmask"]
    gateway = data["gateway"]
    bridge = data["bridge"]

    if _type == "wmi":
        wmi_id = data["wmi_id"]   
        hostname = data["hostname"]    
        ret = create_wmi(name, uuid, vcpu, mem, os_size, data_size, ip, 
                         hostname, wmi_id, netmask, gateway, bridge)    
        return ret
    elif _type == "origin":
        version = data["version"]
        location = data["location"]   
        ks = data["ks"]
        ret = create_origin(name, uuid, version, vcpu, mem, os_size, data_size, 
                            ip, location, netmask, gateway, ks, bridge)
        return ret
        

def delete(name):
    """ 删除一个 instance.

    这个函数对两种存储是通用的.

    """
    # 获取虚拟机的所有 volume.
    # 如果写在 virsh destroy 前面, 可能会造成 volume 丢失
    #(我遇见是少第二块盘往后的), 很奇怪.
    cmd = """ virsh domblklist %s |awk 'NR>2' |egrep -v '\.iso|hd' """\
            """|awk '{print $2}' """ % name
    return_out = utils.shell(cmd)
    devices = return_out.strip().splitlines()

    # 停止 instance, 可能已经关机.
    cmd = ''' virsh destroy {name} '''.format(name=name)
    utils.shell(cmd, exception=False)

    # 删除 instance 的所有 volume.
    for device in devices:
        volume.delete(device)

    # 删除配置文件.
    cmd = ''' virsh undefine {name} '''.format(name=name)
    utils.shell(cmd)


def shutdown(name):
    """ 把一台 instance 停掉.

    """
    cmd = ''' virsh destroy {name} '''.format(name=name)
    utils.shell(cmd)


def reboot(name):
    """ 把一台 instance 重启.

    """

    cmd = ''' virsh destroy {name} && '''\
        ''' virsh start {name}'''.format(name=name)
    utils.shell(cmd)
