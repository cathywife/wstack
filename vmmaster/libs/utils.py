# -*- coding: utf-8 -*-

""" 虚拟机相关工具集合.
    
"""

import re
import time
import xmlrpclib

import redis
import requests
import ujson as json

from libs import asset_utils, log, mail, redisoj

from settings import (OS_SIZE, REDIS_DB_VM, VM_AREAS, IGNORED_VMHS_NODE)


logger = log.LogHandler().logger
client = redisoj.RedisClient().get(REDIS_DB_VM)


def get_uid():
    """ 获取唯一 id.

    能够保证 id 不重复.

    """
    pipe = client.pipeline()

    while 1:
        try:
            pipe.watch('uid')
            current_id = pipe.get('uid')
            if current_id is None:
                next_id = 1
            else:
                next_id = int(current_id) + 1
            pipe.multi()
            pipe.set('uid', next_id)
            pipe.execute()
            break
        except redis.exceptions.WatchError:
            continue
        finally:
            pipe.reset()

    return next_id


def get_idc_from_hostname(hostname):
    """ 根据 hostname 返回 idc.

    比如, vmh100.hy01 返回 hy01.

    """
    return hostname.split(".")[-1]


def get_network_from_ip(ip):
    """ 根据 ip 获取网络地址.

    这里网络都是 /24 的.

    """
    return ".".join(ip.split(".")[:-1]) + ".0" + "/24"


def get_gateway_from_ip(ip):
    """ 根据 ip 获取网关.

    这里网络都是 /24 的.

    """
    return ".".join(ip.split(".")[:-1]) + ".1"


def get_idcs():
    """ 获取机房列表.

    """
    return list(client.smembers("idcs"))


def query_area(vmh):
    """ 基于 vmh 查询所属 area.

    """
    for area in VM_AREAS:
        if vmh in get_vmhs(area):
            return area


def update_idcs():
    """ 设置机房信息.

    采用 redis set 数据结构保存 idcs.

    """
    idcs = asset_utils.get_idcs()
    for idc in idcs:
        if not client.sismember("idcs", idc):
            client.sadd("idcs", idc)

    for idc in get_idcs():
        if idc not in idcs:
            client.srem("idcs", idc)


def update_vmhs(email=True):
    """ 更新 vmhs 到数据库.

    """
    vmhs_all = []   # vmhs_all 是有效宿主机列表.

    for area in VM_AREAS:
        node_id = VM_AREAS[area]["node_id"]
        vmhs = asset_utils.get_hostnames_from_node(node_id)
        vmhs_all.extend(vmhs)
        for vmh in vmhs:
            idc = get_idc_from_hostname(vmh)
            if vmh not in get_vmhs(area, idc):
                add_vmh(area, idc, vmh)

                # 获取 vmh 资源.
                try:
                    update_info_from_rpc(vmh)
                except Exception, e:
                    logger.info("get vmh:{vmh} error:{error}".format(vmh=vmh, error=e))
                    del_vmh(area, idc, vmh)
                    continue
    
                # 设置 vmh 的网络信息.
                ip = asset_utils.get_ip_from_hostname(vmh)
                network = get_network_from_ip(ip)
                add_network(vmh, network)
    
                # 记日志和发邮件.
                logger.info("vmh:{vmh}, network:{network}".format(vmh=vmh, network=network))
                if email:
                    subject = u"|wdstack 宿主机| {vmh} 被添加到 {area}".format(vmh=vmh, area=area)
                    mail.send(None, subject, "") 

    # 删除不在资产系统里的 vmh, 保持本地 vmh 库最新.
    for area in VM_AREAS:
        for vmh in get_vmhs(area):
            if vmh not in vmhs_all:
                idc = get_idc_from_hostname(vmh)
                del_vmh(area, idc, vmh)

                del_network(vmh)
                del_info(vmh)


def get_vmhs(area=None, idc=None):
    """ 获取宿主机列表.

    宿主机列表通过 redis set 数据结构存储, 分 area 和 idc, key 是:
    vmhs:{area}:{idc}

    """
    if area is not None and idc is not None:
        key = "vmhs:{area}:{idc}".format(area=area, idc=idc)
        return list(client.smembers(key))

    if area is None and idc is not None:
        keys = client.keys("vmhs:*:{idc}".format(idc=idc))
    elif area is not None and idc is None:
        keys = client.keys("vmhs:{area}:*".format(area=area))
    else:
        keys = client.keys("vmhs:*:*")

    vmhs = list()
    for key in keys:
        vmhs.extend(list(client.smembers(key)))
    return vmhs


def add_vmh(area, idc, vmh):
    """ 增加宿主机.

    宿主机列表通过 redis set 数据结构存储, 分 area 和 idc, key 是:
    vmhs:{area}:{idc}

    """
    key = "vmhs:{area}:{idc}".format(area=area, idc=idc)
    client.sadd(key, vmh)


def del_vmh(area, idc, vmh):
    """ 删除宿主机.

    宿主机列表通过 redis set 数据结构存储, 分 area 和 idc, key 是:
    vmhs:{area}:{idc}

    """
    key = "vmhs:{area}:{idc}".format(area=area, idc=idc)
    client.srem(key, vmh)


def get_network(vmh):
    """ 获取宿主机的网络.

    宿主机的网络通过 redis string 类型存储, key 是:
    net:{vmh}

    """
    key = "net:{vmh}".format(vmh=vmh)
    return client.get(key)


def add_network(vmh, network):
    """ 设置宿主机的网络.

    宿主机的网络通过 redis string 类型存储, key 是:
    net:{vmh}

    """
    key = "net:{vmh}".format(vmh=vmh)
    client.set(key, network)


def del_network(vmh):
    """ 删除宿主机的网络.

    宿主机的网络通过 redis string 类型存储, key 是:
    net:{vmh}

    """
    key = "net:{vmh}".format(vmh=vmh)
    client.delete(key)


def get_info(vmh, item=None):
    """ 获取宿主机资源信息.

    宿主机资源通过 redis hash 数据结构存储, key 是:
    info:{vmh}

    item 表示资源项, 可以是 vcpu, mem, space, vmlist 等.

    """
    key = "info:{vmh}".format(vmh=vmh)
    if item is not None:
        data = client.hget(key, item)
        return json.loads(data)
    else:
        return client.hgetall(key)


def update_info(vmh, item, data):
    """ 设置宿主机资源信息.

    宿主机资源通过 redis hash 数据结构存储, key 是:
    info:{vmh}

    item 表示资源项, 可以是 vcpu, mem, space 和 vmlist.

    """
    key = "info:{vmh}".format(vmh=vmh)
    client.hset(key, item, json.dumps(data))


def del_info(vmh):
    """ 删除宿主机资源信息.

    宿主机资源通过 redis hash 数据结构存储, key 是:
    info:{vmh}

    """
    key = "info:{vmh}".format(vmh=vmh)
    client.delete(key)


def get_vmname(vmh):
    """ 获取宿主机的虚拟机标识, 比如 vm1, vmXX 等, 用来在宿主机上创建虚拟机.
    
    会对最大的后缀加1, 以保证不重复.

    """
    vmlist = get_info(vmh, "vmlist")
    if vmlist == []:
        name = "vm1"
    else:
        suffix = list()
        for v in vmlist:
            if re.match("vm\d+", v) is not None:
                tmp = int(v.replace("vm", ""))
                suffix.append(tmp)
            else:
                continue
        suffix_max = sorted(suffix)[-1]
        name = "vm" + str(suffix_max + 1)

    return name


def update_vmname(vmh, vmname):
    """ 更新宿主机的虚拟机标识.

    此处能解决并发修改的问题, 多个 client 可以同时 watch,
    但是一次只能一次修改, 其他会报 WatchError.

    """
    pipe = client.pipeline()
    while 1:
        try:
            # 此处特殊处理一下, 使用了 vmh 的 info.
            key = 'info:{vmh}'.format(vmh=vmh)
            pipe.watch(key)

            vmlist = get_info(vmh, "vmlist")
            vmlist.append(vmname)

            pipe.multi()
            pipe.hset(key, "vmlist", json.dumps(vmlist))
            pipe.execute()
            break
        except redis.exceptions.WatchError:
            continue
        finally:
            pipe.reset()


def get_ignores():
    """ 获取被忽略的宿主机列表.

    被忽略的宿主机列表通过 redis set 数据结构存储.

    """
    return list(client.smembers("ignores"))


def add_ignore(hostname):
    """ 增加被忽略的虚拟机.

    被忽略的宿主机列表通过 redis set 数据结构存储.

    """
    if isinstance(hostname, list):
        [client.sadd("ignores", i) for i in hostname]
    else:
        client.sadd("ignores", hostname)


def del_ignore(hostname):
    """ 删除被忽略的虚拟机.

    被忽略的宿主机列表通过 redis set 数据结构存储.

    """
    if isinstance(hostname, list):
        [client.srem("ignores", i) for i in hostname]
    else:
        client.srem("ignores", hostname)


def update_ignores():
    """ 更新被忽略的宿主机.

    """
    ignores = asset_utils.get_hostnames_from_node(IGNORED_VMHS_NODE)
    ignores_now = get_ignores()
    for i in ignores:
        if i not in ignores_now:
            add_ignore(i)

    for i in ignores_now:
        if i not in ignores:
            del_ignore(i)


def wait_status(sn, timeout=1200):
    """ 查询和等待机器是否上报到资产系统.

    """
    timetotal = 0
    interval = 1

    while timetotal < timeout:
        try:
            status = asset_utils.get_value_from_sn(sn, "status")
            if status == "online":
                return
        except Exception, e:
            pass
        finally:
            time.sleep(interval)
            timetotal += interval
    raise Exception("not uploaded to asset sys")


def get_vmhs_on_demand(area, idc, num, vcpu, mem, data_size, _reverse):
    """ 基于参数获取满足需求的宿主机列表.

        1. 虚拟机必须不在同一个宿主机上,如果不满足,创建失败;
        2. 尽量不在同一个交换机,如果有两个宿主机在同一个交换机上,也会创建;
        3. 支持剩余资源从大到小 和 从 小到大 的顺序选取宿主机;

        _reverse 为 True 表示从大到小 的顺序选取宿主机;
                 为 False 表示从小到大的顺序选取宿主机.

        vmh_dict 表示各个宿主机对应的资源;
        switch_dict 表示各个交换机下面的宿主机;
        switch_list 表示交换机列表,列表是经过排序的(根据宿主机资源).

    """
    vmh_dict = dict()
    switch_dict = dict()
    switch_list = list()

    # 去除忽略的宿主机, 拿到有效的宿主机列表.
    vmhs = get_vmhs(area, idc)
    for ignore_vmh in get_ignores():
        if ignore_vmh in vmhs:
            vmhs.remove(ignore_vmh)

    for vmh in vmhs:
        if get_info(vmh) != {}:
            try:
                vcpu_free = get_info(vmh, "vcpu")["free"]
                mem_free = get_info(vmh, "mem")["free"]
                space_free = get_info(vmh, "space")["free"]

                if vcpu_free < vcpu or mem_free < mem or space_free < data_size + OS_SIZE:
                    continue
            except Exception, e:
                continue

            # 我们这里需要获取 vmh 的交换机, 但是在我们的网络结构上每个交换机的网段都不一样, 
            # 所以可以使用 vmh 的网段来代替.
            # switch = asset_utils.get_direct_switch(vmh)
            switch = get_network(vmh)

            if not switch:
                logger.warning("vmh:{vmh}, switch:{switch}".format(vmh=vmh, switch=switch))
                continue

            if switch not in switch_dict.keys():
                switch_dict[switch] = [vmh]
            else:
                switch_dict[switch].append(vmh)

            vmh_dict[vmh] = [vcpu_free, mem_free, space_free]

    logger.info("switch_dict:{switch_dict}".format(switch_dict=switch_dict))
    logger.info("vmh_dict:{vmh_dict}".format(vmh_dict=vmh_dict))

    for switch in switch_dict:
        vmhs = switch_dict[switch]

        tmp = dict()
        for i in vmhs:
            tmp[i] = vmh_dict[i]
        tmp2 = sorted(tmp.items(), 
                      key=lambda t: (t[1][0], t[1][1], t[1][2]), 
                      reverse=_reverse)
        tmp3 = [ i[0] for i in tmp2 ]

        switch_dict[switch] = tmp3

    vmhs = list()
    tmp = dict()
    for switch in switch_dict:
        vmh = switch_dict[switch][0]
        vmhs.append(vmh)
        tmp[vmh] = switch
    tmp2 = dict()
    for i in vmhs:
        tmp2[i] = vmh_dict[i]
    tmp3 = sorted(tmp2.items(), 
                  key=lambda t: (t[1][0], t[1][1], t[1][2]), 
                  reverse=_reverse)
    for i in tmp3:
        switch_list.append(tmp[i[0]])
    logger.info("switch_list:{switch_list}".format(switch_list=switch_list))

    switch_max_len = 0
    for switch in switch_dict:
        if len(switch_dict[switch]) > switch_max_len:
            switch_max_len = len(switch_dict[switch])

    vmhlist = list()
    n = 0
    while 1:
        if n > switch_max_len:
            break

        for switch in switch_list:
            tmp = switch_dict[switch]
            if n >= len(tmp):
                continue

            vmhlist.append(tmp[n])
        n += 1

    if len(vmhlist) < num:
        return False
    else:
        logger.info("vmhlist:{vmhlist}".format(vmhlist=vmhlist))
        return vmhlist[:num]


def get_vminfo_from_ip(ip):
    """ 根据 ip 查看 主机名和网络设置, 这个功能用于虚拟机装机.

    """
    if client.exists(ip):
        netmask = "255.255.255.0"
        gateway = get_gateway_from_ip(ip)
        hostname = client.get(ip)

        return {
            "ip": ip, 
            "netmask": netmask, 
            "gateway": gateway, 
            "hostname": hostname
        }


def get_rpc_client(vmh):
    """ 获取 vmh rpc client.

    """
    return xmlrpclib.ServerProxy('http://{vmh}:8000/vmagent'.format(vmh=vmh),
                                 allow_none=True)


def update_info_from_rpc(vmh):
    """ 获取和更新 vmh 资源信息.

    某些集群可能有有超配, 仅限于 vcpu 和 mem.

    """
    rpc_client = get_rpc_client(vmh)

    vmlist = rpc_client.resource_vmlist()
    vcpu = rpc_client.resource_vcpu()
    mem = rpc_client.resource_mem()
    space = rpc_client.resource_space()
    _type = rpc_client.resource_type()

    area = query_area(vmh)
    for key in vcpu:
        vcpu[key] = vcpu[key] * (1 + VM_AREAS[area]['over_conf'])

    for key in mem:
        mem[key] = mem[key] * (1 + VM_AREAS[area]['over_conf'])

    update_info(vmh, "vcpu", vcpu)
    update_info(vmh, "mem", mem)
    update_info(vmh, "space", space)
    update_info(vmh, "vmlist", vmlist)
    update_info(vmh, "type", _type)


def get_vmname_from_hostname(hostname):
    """ 根据 hostname 拿到 vmh 和 vmname.

    """
    sn = asset_utils.get_sn_from_hostname(hostname)
    vmh ,vmname = asset_utils.get_vmh_vmname_from_sn(sn)
    return {
        "hostname": hostname,
        "vmh": vmh, 
        "vmname": vmname
    }
