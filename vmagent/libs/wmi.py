#-*- coding: utf-8 -*- 

""" 创建 wmi 函数.

"""

import json

import redis

from libs import log, utils, storage 
from libs import volume   # 这里用到 volume 里面的 path_size 函数.
from const import REDIS_HOST, REDIS_PORT, REDIS_DB


logger = log.LogHandler().logger


def create(wmi_id, wmi_name, name, excludes):
    """ 根据一个虚拟机实例创建一个 wmi.

    查看虚拟机实例的 blklist, 用下面命令:
        virsh domblklist --domain vm1 |awk 'NR>2'
    第一列是 device, 第二列是 volume_path
    然后根据 volume_path 查看其大小:
        virsh vol-info /vm_storage/vm1 |grep Capacity |awk '{print $2,$3}'

    这里要注意的是, 由于我们兼容了两种格式的存储, 用 virsh vol-info volume_path
    看到的 Type 是 block 的话, 是 raw 格式, 我们先把它转换成 qcow2 格式, 然后再
    上传到远端, 上传成功后返回下载地址.

    这里如果 device 是 vda 或者 hda, 则是系统盘, 其余是数据盘.
    会把系统盘和数据盘存放到远程存储机器, 并拿到下载 url.

    """
    cmd = "virsh domblklist --domain {name} |awk 'NR>2' ".format(name=name)
    return_out = utils.shell(cmd, strip=True)
    device_info = [ (i.split()[0],i.split()[1]) \
        for i in return_out.splitlines() \
        if i.split()[1] != "-" ]

    # 如果实例的 volume 大于2, 可能数据有两个 volume, 此时 guestfish add data_volume
    # 会缺数据, 所有要用 guestfish -d name, 而 -d name 参数需要关机.
    def _is_running(_name):
        cmd = """virsh list |grep running |awk '{print $2}'"""
        runnings = [i.strip() for i in utils.shell(cmd, strip=True).splitlines()]
        return _name in runnings
    is_running = _is_running(name)
    if len(device_info) > 2 and is_running:
        raise Exception("{name} is running".format(name=name))
 
    for device, volume_path in device_info:
        if (device == "vda" or device == "hda"):
            if "_os" not in locals():
                os_file_name = "{wmi_id}_os".format(wmi_id=wmi_id)                
                url = storage.upload_os(volume_path, os_file_name)
                _os = {
                    "device": device,
                    "size": "{size}G".format(size=volume.path_size(volume_path)),
                    "url": url
                }

                # 对系统盘的数据打包, 仅供在 raw 格式的宿主机上使用.
                os_tar_file_name = "{wmi_id}_os_tar".format(wmi_id=wmi_id)
                _os["tar"] = storage.upload_os_tar(volume_path, os_tar_file_name)

                # 下面会用.
                os_volume_path = volume_path

        else:
            if "_data" not in locals():
                data_file_name = "{wmi_id}_data".format(wmi_id=wmi_id)
                url = storage.upload_data(name, is_running, 
                    volume_path, data_file_name, excludes)
                _data = {
                    "device": device,
                    "size": "{size}G".format(size=volume.path_size(volume_path)),
                    "url": url
                }

    logger.info("os volume:{os}".format(os=_os))
    logger.info("data volume:{data}".format(data=_data))

    # 为了实现在 raw 格式的宿主机上基于镜像创建虚拟机的时候尽量少的拷贝数据, 我们这里获取镜像的分区表信息, 
    # 并备份 mbr, boot 分区和 lvm header 信息.
    # 当在 qcow2 格式的宿主机上基于镜像创建虚拟机的时候用不到此分区表信息.
    _partition = storage.get_partition(os_volume_path, wmi_id)
    logger.info("partition info:{partition}".format(partition=_partition))

    return _os, _data, _partition


def get(_id):
    """ 获取 wmi 信息.

    """
    client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, 
                         db=REDIS_DB)
    key = "wmi:" + _id
    return json.loads(client.get(key))
