#-*- coding: utf-8 -*-

""" 虚拟机网卡相关, 这里创建网卡和关联虚拟机合在了一起.
    
"""

from libs import utils


def add(name, bridge):
    """ 给虚拟机实例增加一个网卡.
    
    """

    mac = utils.random_mac()

    cmd = """ sed -i "/<\/interface>/a \    <interface type='bridge'>      """\
          """<mac address='{mac}'\/>      <source bridge='{bridge}'\/>    """\
          """<model type='virtio'/>    <\/interface>" /etc/libvirt/qemu/{name}.xml """.format(
        mac=mac, bridge=bridge, name=name)
    utils.shell(cmd)

    cmd = " virsh define /etc/libvirt/qemu/{name}.xml ".format(name=name)
    utils.shell(cmd)
