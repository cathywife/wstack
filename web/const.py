# -*- coding: utf-8 -*-

# 绑定的 IP 和 端口.
BIND_IP = "0.0.0.0"
BIND_PORT = "8080"

# 日志路径.
LOG_DIR = './logs'
LOG_NAME = "wdstack"

# REDIS 信息.
REDIS_HOST = "pxe0.nosa01"
REDIS_PORT = 6379
REDIS_DB_PM = 0
REDIS_DB_VM = 1
# 用于存储 user_data 信息, PM VM 都会用到, 所以单独放在一个 db 中.
REDIS_DB_COMMON = 2

# 资产和DNS信息.
ASSET_HOST = "loki.hy01.internal.nosa.me"
ASSET_IDC_API = "/api/asset/query/idc"
ASSET_HOSTNAME_API = "/api/asset/query/hostname"
ASSET_APPLY_API = "/api/asset/apply"
ASSET_UPDATE_API = "/api/asset/update"
ASSET_QUERY = "/api/asset/query"
ASSET_DETAIL_API = "/api/asset/detail"
ASSET_STATUS_API = "/api/asset/status"

DNS_HOST = "dns.internal.nosa.me"
DNS_AUTH_API = "api/v1/ldapauth"
DNS_AUTH_USERNAME = ""
DNS_AUTH_PASSWD = ''


# 物理机信息
# 可能的控制卡密码, 会自动尝试出正确的密码.
ILO_PASSWDS = ['nosa.me', 'sre123.nosa.me', 'calvin']

# 系统类型和系统版本号.
OS_TYPES = ['kvm', 'raw', 'docker', 'wipe']
OS_VERSIONS = ['centos6', 'centos7']

# 系统类型和系统版本号 分别对应的 pxelinux.cfg 文件路径.
PXELINUX_CFGS = {
    "raw": {
        "centos6": "/home/work/pxe/pxelinux.cfg/centos6_x64_raw_clean",
        "centos7": "/home/work/pxe/pxelinux.cfg/centos7_raw_clean"
    },
    "kvm": {
        "centos6": "/home/work/pxe/pxelinux.cfg/centos6_x64_kvm_host",
        "centos7": "/home/work/pxe/pxelinux.cfg/centos7_kvm_host"
    },
    "docker": {
        "centos7": "/home/work/pxe/pxelinux.cfg/centos7_docker_host"
    },
    "wipe": {
        "centos7": "/home/work/pxe/pxelinux.cfg/centos7_raw_wipe"
    }
}

# 装机并发数, 一个任务最多支持的同时装机数量.
MAX_THREAD_NUM = 20


# 虚拟机信息
# 虚拟机集群:
VM_AREAS = {
    "online": "vmh",
    "apps": "vmh-apps",
    "eyepetizer": "vmh-eyepetizer",
    "dt": "vmh-dt",
    "pre-online": "vmhp",
    "dev": "vmh-dev",
    "test": "vmht"
}

# 超配容量.
# 超配只针对 CPU 和 内存.
OVER_CONFS = {
    "online": 0,
    "apps": 0.2,
    "eyepetizer": 0.2,
    "dt": 0.2,
    "pre-online": 0.5,
     "dev": 0.2,
    "test": 0 
}

# 一些参数.
# DISK_DEFAULT = ""
NETMASK_DEFAULT = "255.255.255.0"
KSS = {
    "centos6": "http://pxe.internal.nosa.me/ks/centos6_x64_kvm_guest.cfg",
    "centos7": "http://pxe.internal.nosa.me/ks/centos7_kvm_guest.cfg",
}
LOCATIONS= {
    "centos6": "/tmp/CentOS-6.3-x86_64-minimal.iso",
    "centos7": "/tmp/CentOS-7-x86_64-DVD-1511.iso"
}

BRIDGE_DEFAULT = "br2"
OS_SIZE = 18   # 系统盘大小(G)

# puppet ca, 申请到主机名之后需要清掉 ca 上已经签发的证书, 防止新机器申请证书失败.
PUPPET_CA_HOST = "puppetca.corp.nosa.me:8140"
