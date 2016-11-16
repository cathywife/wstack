#-*- coding: utf-8 -*-

""" 存储卷函数, 对「存储池」做操作可以兼容目前两种存储结构.
    
"""

import sys

from libs import utils, log
from const import STORAGE_POOL


logger = log.LogHandler().logger


def create(volume_name, volume_size):
    """ 创建 volume.
    老存储结构用类似命令:
        virsh vol-create-as --pool vm_storage_pool --name vm1.img \
        --capacity 20G
    新存储结构则用:
        virsh vol-create-as --pool vm_storage_pool --name vm1.img \
        --capacity 20G --allocation 1G --format qcow2
    
    因为没有优雅的方法区分两种结构, 临时用下面命令来区分:
        df |grep /vm_storage
    存在 vm_storage 则是新结构, 否则是老结构.

    """
    cmd = "df |grep /vm_storage"
    try:
        utils.shell(cmd)
        cmd = """ virsh vol-create-as --pool {storage_pool} --name {volume_name} """\
            """--capacity {volume_size} --allocation 1G --format qcow2""".format(
            storage_pool=STORAGE_POOL, volume_name=volume_name, volume_size=volume_size)
    except Exception, e:
        cmd = """ virsh vol-create-as --pool {storage_pool} --name {volume_name} """\
            """--capacity {volume_size} """.format(storage_pool=STORAGE_POOL, 
                volume_name=volume_name, volume_size=volume_size)
    utils.shell(cmd)

    cmd = "virsh vol-path --pool {storage_pool} {volume_name}".format(
        storage_pool=STORAGE_POOL, volume_name=volume_name)
    volume_path = utils.shell(cmd, strip=True)
    return volume_path   # 这里返回 volume 的路径.


def delete(volume_name):
    """ 删除 volume.

    """
    cmd = ''' virsh vol-delete --pool {storage_pool} {volume_name} '''.format(
        storage_pool=STORAGE_POOL, volume_name=volume_name)
    utils.shell(cmd)


def attach(name, volume_path, target):
    """ 给虚拟机实例 attach 一个 volume, target 表示在虚拟机看到的硬盘标识,比如 vdb.

    命令例子:
    virsh attach-disk --source /vm_storage/vm1_data --target vdb 
        --domain vm1 --subdriver qcow2
    如果不指定 --subdriver 为 qcow2, 则 type 是 raw.

    在这里, 根据 volume_path 自动计算是 raw 还是 qcow2.
    比如命令:
    virsh vol-name /vm_storage/vm1_data
    virsh vol-pool /vm_storage/vm1_data
    virsh vol-info vm1_data --pool vm_storage_pool
    根据 volume_path 计算出 volume_name 和 volume_pool, 然后查看 volume 的信息,
    如果 Type 是 file, 则是 qcow2, 如果是 block 则为 raw.

    注: 此种计算方法可能只适用于本系统, 可能并不具有推广性.

    """
    _type = path_type(volume_path)
    cmd = """ virsh attach-disk --source {volume_path} """\
            """--target {target} --domain {name} --subdriver {type} """.format(
                volume_path=volume_path, target=target, name=name, type=_type)
    utils.shell(cmd)

    # 发现有的机器挂掉之后启动会挂不上第二块盘, define 就OK了.
    # 所以在这里 define 一次, 以防止出现挂不上盘的情况.
    cmd = "virsh dumpxml {name} >/etc/libvirt/qemu/{name}.xml &&"\
          "virsh define /etc/libvirt/qemu/{name}.xml".format(name=name)
    utils.shell(cmd)


def detach(name, volume_name):
    """ 取消一个 volume 和虚拟机实例的关联.
    暂不实现.

    """


def resize(volume_name, volume_size):
    """ 对存储池的一个 volume 改变大小, 这里只增大, 没法减小.

    对于 qcow2 格式, 命令类似:
        virsh vol-resize vm1_data --capacity 30G --pool vm_storage_pool
    而且只能增大, 如果减小的话, 会报类似的错:
        /usr/bin/qemu-img resize /vm_storage/vm1_data 32212254720) 
        unexpected exit status 1: This image format does not 
        support resize
    
    另外对于 raw 格式, 不能用 virsh vol-resize, 如果想增大, 用如下命令:
        lvextend -L +10G /dev/vm_storage_pool_vg/vm3
        virsh pool-refresh --pool vm_storage_pool    
    这里不考虑 raw 格式.

    """
    cmd = " virsh vol-resize {volume_name} --capacity {volume_size} --pool {vm_storage_pool}".format(
        volume_name=volume_name, volume_size=volume_size, vm_storage_pool=STORAGE_POOL)
    utils.shell(cmd)


def path_size(volume_path):
    """ 根据 volume_path 拿到 volume 大小, 单位是 G.

    指令如下:
        virsh vol-info /vm_storage/vm1 |grep Capacity |awk '{print $2,$3}'

    """
    cmd = "virsh vol-info %s |grep Capacity |awk '{print $2,$3}' " % volume_path
    return_out = utils.shell(cmd)
    if "MiB" in return_out or "MB" in return_out:
        space_total = int(return_out.split()[0].split(".")[0]) / 1024                    
    elif "GiB" in return_out or "GB" in return_out:
        volume_size = int(return_out.split()[0].split(".")[0])
    elif "TiB" in return_out or "TB" in return_out:
        volume_size = int(return_out.split()[0].split(".")[0]) * 1000
    return volume_size   # 这里是数字, 不加单位 G 了.


def path_type(volume_path):
    """ 根据 volume_path 判断 volume 类型是 file 还是 block.

    """
    cmd = """virsh vol-info %s |grep "Type" |awk '{print $NF}' """ % volume_path
    _type = utils.shell(cmd, strip=True)
    if _type == "file":
        _type = "qcow2"
    elif _type == "block":
        _type = "raw"
    return _type
