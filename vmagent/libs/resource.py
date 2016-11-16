#-*- coding: utf-8 -*-

import re

from libs import log, utils
from const import STORAGE_POOL


logger = log.LogHandler().logger


def vmlist():
    cmd = ''' virsh list --all |egrep -i "running|stop|shut" |awk '{print $2}' '''
    return_out = utils.shell(cmd)
    return return_out.splitlines()


def vcpu():
    cmd = " grep processor /proc/cpuinfo |wc -l "
    return_out = utils.shell(cmd)

    cpu_total = int(return_out)
    cpu_used = 0

    for name in vmlist():
        cmd = ''' virsh dominfo %s |grep "CPU(s):" |awk '{print $2}' ''' % name
        return_out = utils.shell(cmd)
        cpu_used += int(return_out)

    cpu_free = cpu_total - cpu_used
    if cpu_free < 0:
        cpu_free = 0

    return {"total": cpu_total, "free": cpu_free}


def mem():
    cmd = """ free -m |grep -i "Mem:" |awk '{print $2}' """
    return_out = utils.shell(cmd)

    mem_total = int(return_out)
    mem_used = 0

    for i in vmlist():
        cmd = ''' virsh dominfo %s |grep -i "Max memory:" |awk '{print $3}' ''' % i
        return_out = utils.shell(cmd)
        mem_used += int(return_out)/1024

    mem_free = mem_total - mem_used
    if mem_free < 0:
        mem_free = 0

    return {"total": mem_total, "free": mem_free}


def space():
    """ 获取存储池的总空间和剩余空间(G).

    如果是 qcow2 格式的存储, 用下面的命令
        virsh pool-info --pool vm_storage_pool |grep Available 

    看到的是真正使用的空间, 有坑, 所以把每个 volume 的 Capacity 拿到相加,
    然后用总空间减去它即是剩余空间.

    先用 
        virsh vol-list --pool vm_storage_pool 
    拿到每个 volume, 然后用 
        virsh vol-info --pool vm_storage_pool vm1 |grep Capacity
    拿到每个 volume 的 Capacity.

    """
    cmd = """ virsh pool-info --pool %s |egrep "Capacity" """\
        """|awk '{print $2,$3}' """ % STORAGE_POOL
    return_out = utils.shell(cmd, strip=True)

    if "MiB" in return_out or "MB" in return_out:
        space_total = int(return_out.split()[0].split(".")[0]) / 1024        
    elif "GiB" in return_out or "GB" in return_out:
        space_total = int(return_out.split()[0].split(".")[0])
    elif "TiB" in return_out or "TB" in return_out:
        space_total = int(return_out.split()[0].split(".")[0]) * 1000
    else:
        raise Exception("space unit isn't MB, GB or TB.")

    space_used = 0
    cmd = """ virsh vol-list --pool %s |awk 'NR>2' |grep -v lost+found """\
            """|awk '{print $1}' """ % STORAGE_POOL
    return_out = utils.shell(cmd, strip=True)

    vol_list = return_out.splitlines()
    for vol in vol_list:
        cmd = """ virsh vol-info --pool %s %s |grep Capacity """\
                """|awk '{print $2,$3}' """ % (STORAGE_POOL, vol)
        return_out = utils.shell(cmd, strip=True)
        if "MiB" in return_out or "MB" in return_out:
            space_total = int(return_out.split()[0].split(".")[0]) / 1024            
        elif "GiB" in return_out or "GB" in return_out:
            space_used += int(return_out.split()[0].split(".")[0])
        elif "TiB" in return_out or "TB" in return_out:
            space_used += int(return_out.split()[0].split(".")[0]) * 1000
        else:
            raise Exception("space unit isn't MB, GB or TB.")

    space_free = space_total - space_used
    return {"total": space_total, "free": space_free}


def _type():
    """ 获取存储结构.

    老的结构是 raw 格式, 新的结构是 qcow2 格式.
    
    """
    try:
        utils.shell("df |grep /vm_storage")
    except Exception, e:
        return "raw"
    return "qcow2"
