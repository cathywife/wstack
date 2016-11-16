#-*- coding: utf-8 -*-

LOG_DIR = "./logs/"
LOG_NAME = "wdstack_vmagent"

REDIS_HOST = "pxe0.hlg01"
REDIS_PORT = 6379
REDIS_DB = 1

STORAGE_POOL = "vm_storage_pool"

ISO_URLS = {
    "centos6": "http://pxe.internal.nosa.me/iso/CentOS-6.3-x86_64-minimal.iso",
    "centos7": "http://pxe.internal.nosa.me/iso/CentOS-7-x86_64-DVD-1511.iso"
}

VM_TEMPLATE_DIR = "template"
VM_TEMPLATE_FILE = "vm.xml"

NAMESERVER = "10.19.20.234"
DOMAIN = "nosa.me"
