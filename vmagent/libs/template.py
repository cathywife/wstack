#-*- coding: utf-8 -*-

""" 根据模板生成虚拟机配置文件.

"""

from jinja2 import Environment, FileSystemLoader

from settings import VM_TEMPLATE_DIR, VM_TEMPLATE_FILE


def gen(data):
    vm_conf_path = "/etc/libvirt/qemu/%s.xml" % data["name"]

    j2_env = Environment(loader=FileSystemLoader(VM_TEMPLATE_DIR),
                         trim_blocks=True)
    ret = j2_env.get_template(VM_TEMPLATE_FILE).render(
        volumes=data["volumes"],
        interface_br1=data["interface_br1"],
        interface_br2=data["interface_br2"],
        name=data["name"],
        uuid=data["uuid"],
        vcpu=data["vcpu"],
        memory=data["memory"],
        currentmemory=data["currentmemory"]             
    )
    with open(vm_conf_path, 'w') as f:
        f.writelines(ret)
