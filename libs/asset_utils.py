# -*- coding: utf-8 -*-

""" 资产系统相关函数.

"""

import requests
import ujson as json


from settings import (ASSET_HOST, ASSET_IDC_API, ASSET_HOSTNAME_API,
                      ASSET_APPLY_API, ASSET_UPDATE_API, ASSET_QUERY,
                      ASSET_DETAIL_API, ASSET_STATUS_API, ASSET_SERVERS_API)
from settings import X_Loki_Token


def get_idcs():
    """ 从资产系统获取机房列表.

    """
    url = "http://" + ASSET_HOST + ASSET_IDC_API
    return requests.get(url).json()


def get_vmhs(idc=None):
    """ 从资产系统获取宿主机列表.

    """
    if idc is None:
        url = "http://" + ASSET_HOST + ASSET_HOSTNAME_API + "?type=kvm"
    else:
        url = "http://" + ASSET_HOST + ASSET_HOSTNAME_API + "?type=kvm&idc=%s" % idc
    return requests.get(url).json()


def apply_hostname_ip(sn, _type, hostname_key, idc, network):
    """ 从资产系统获取主机名和 IP.

    对于物理机, sn 即是它的 sn, 对于虚拟机需要先生成一个 sn(uuid).

    _type 表示机器类型, 有三种 vm, kvm, raw

    hostname_key 和 idc 决定主机名;
    network 决定 ip.

    申请之后自动在资产系统中记录, 并被标记 creating.

    """
    if "*" in hostname_key:
        key = "hostname_pattern"
        hostname_key = hostname_key + "." + idc
    else:
        key = "hostname_prefix"
    url = "http://" + ASSET_HOST + ASSET_APPLY_API
    data = {
        "sn": sn,
        "type": _type,
        key: hostname_key,
        "idc": idc,
        "network": network
    }
    headers = {"Content-Type": "application/json"}

    result = requests.post(url, json=data, headers=headers)
    result_json = result.json()
    try:
        return result_json["hostname"], result_json["private_ip"]
    except Exception, e:
        message = "apply hostname and ip fail, data:{data}, status_code:{status_code}, text:{text}".format(
            data=data, status_code=result.status_code, text=result.text)
        raise Exception(message)


def update_status(sn, status):
    """ 修改服务器状态信息.

    """
    url = "http://" + ASSET_HOST + ASSET_STATUS_API
    data = {
        "status": status
    }
    headers = {"Content-Type": "application/json"}

    result = requests.post(url, json=data, headers=headers)
    import re
    if re.match("50", str(result.status_code)) is not None:
        raise Exception(result.text)


def query_from_sn(sn):
    """ 根据 sn 查询机器信息.

    """
    url = "http://" + ASSET_HOST + ASSET_DETAIL_API + "/%s" % sn
    return requests.get(url).json()


def delete_from_sn(sn):
    """ 根据 sn 删除机器.

    """
    url = "http://" + ASSET_HOST + ASSET_DETAIL_API + "/%s" % sn
    result = requests.delete(url)
    import re
    if re.match("50", str(result.status_code)) is not None:
        raise Exception(result.text)


def query_from_fuzzy_word(value):
    """ 根据机器信息模糊查询.

    """
    url = "http://" + ASSET_HOST + ASSET_QUERY + "?fuzzy_word=%s" % value
    return requests.get(url).json()


def get_hostnames_from_node(node_id):
    url = "http://" + ASSET_HOST  + ASSET_SERVERS_API + "?type=recursive&node_id={0}&with_weight=0".format(node_id)
    data = requests.get(url).json()["data"]
    return [d["hostname"] for d in data]


###


def get_ip_from_hostname(hostname):
    """ 根据机器名获取 ip.

    """
    return_list = query_from_fuzzy_word(hostname)
    if len(return_list) > 1:
        raise Exception("There are {num} items for {hostname}".format(
            num=len(return_list), hostname=hostname))
    return return_list[0]["private_ip"][0].replace("/24", "")


def get_sn_from_hostname(hostname):
    """ 根据主机名获取 sn.

    """
    return_list = query_from_fuzzy_word(hostname)
    if len(return_list) == 1:
        return return_list[0]["sn"]
    else:
        for d in return_list:
            if d["hostname"] == hostname:
                return d["sn"]
    raise Exception("There are no {hostname}".format(hostname=hostname))


def get_value_from_sn(sn, key):
    """ 基于 sn 查询 key 的 value.

    """
    return query_from_sn(sn)[key]


def get_vmh_vmname_from_sn(sn):
    """ 基于虚拟机的 sn 查询所在 vmh 和对应 vmname.

    """
    vm_info = query_from_sn(sn)
    if vm_info["type"] != "vm":
        raise Exception("{sn} is not vm".format(sn=sn))

    return vm_info["vm_host"]["hostname"], vm_info["vm_name"]


def is_exist_for_sn(sn):
    """ 判断 sn 是否存在.

    """
    return "error" not in query_from_sn(sn)


# def get_direct_switch(vmh):
#     """ 拿到宿主机的直连交换机.

#     由于在我们的网络结构上, 每个交换机的网段都不一样, 所以可以使用 vmh 的网段来代替.

#     暂不实现此函数.

#     """
#     pass


def bind_server_to_node(node_id, hostnames):
    """ 绑定机器到节点.

    """
    node_id = int(node_id)
    if node_id == 0:
        return

    url = "http://{0}/api/nodes/{1}/servers".format(ASSET_HOST, node_id)
    data = {
        "hostnames": hostnames
    }
    headers = {
        "Content-Type": "application/json", 
        "X-Loki-Token": X_Loki_Token
    }
    ret = requests.put(url, json=data, headers=headers)
    if ret.status_code != 200:
        raise Exception("bind {0} to node {1} fail".format(hostnames, node_id))
