# -*- coding: utf-8 -*-

# 绑定的 IP 和 端口.
BIND_IP = "0.0.0.0"
BIND_PORT = "8080"

# 日志路径.
LOG_DIR = './logs'
LOG_NAME = "wdstack"

# LDAP 信息.
LDAP_HOST = "ldap.corp.DOMAIN.COM"
LDAP_DN = "ou=People,dc=DOMAIN,dc=com"
LDAP_USER = "cn=root,dc=DOMAIN,dc=com"

# REDIS 信息.
REDIS_HOST = "pxe0.hlg01"
REDIS_PORT = 6379
REDIS_DB_PM = 0
REDIS_DB_VM = 1
# 用于存储 user_data 信息, PM VM 都会用到, 所以单独放在一个 db 中.
REDIS_DB_COMMON = 2

# 资产和 DNS 信息.
ASSET_HOST = "loki.hy01.internal.DOMAIN.COM"
ASSET_IDC_API = "/api/asset/query/idc"
ASSET_HOSTNAME_API = "/api/asset/query/hostname"
ASSET_APPLY_API = "/api/asset/apply"
ASSET_UPDATE_API = "/api/asset/update"
ASSET_QUERY = "/api/asset/query"
ASSET_DETAIL_API = "/api/asset/detail"
ASSET_STATUS_API = "/api/asset/status"
ASSET_SERVERS_API = "/server/api/servers"

X_Loki_Token = "token:9uaADGx7FdNOIayh9/Rl"

DNS_HOST = "dns.internal.DOMAIN.COM"
DNS_AUTH_API = "api/v1/ldapauth"
DNS_AUTH_USERNAME = ""
DNS_AUTH_PASSWD = ''


# 物理机信息
# 可能的控制卡密码, 会自动尝试出正确的密码.
ILO_PASSWDS = ['DOMAIN.COM', 'sre123.DOMAIN.COM', 'calvin']

# 系统类型和系统版本号.
OS_TYPES = ['kvm', 'raw', 'docker', 'wipe']
OS_VERSIONS = ['centos6', 'centos7']

# 系统类型和系统版本号分别对应的 pxelinux.cfg 下载地址.
PXELINUX_DIR = '/var/lib/tftpboot/pxelinux.cfg/'
PXELINUX_CFGS = {
    "raw": {
        "centos6": "http://wdstack.internal.DOMAIN.COM/pxelinux.cfg/centos6_x64_raw_clean",
        "centos7": "http://wdstack.internal.DOMAIN.COM/pxelinux.cfg/centos7_raw_clean"
    },
    "kvm": {
        "centos6": "http://wdstack.internal.DOMAIN.COM/pxelinux.cfg/centos6_x64_kvm_host",
        "centos7": "http://wdstack.internal.DOMAIN.COM/pxelinux.cfg/centos7_kvm_host"
    },
    "docker": {
        "centos7": "http://wdstack.internal.DOMAIN.COM/pxelinux.cfg/centos7_docker_host"
    },
    "wipe": {
        "centos7": "http://wdstack.internal.DOMAIN.COM/pxelinux.cfg/centos7_raw_wipe"
    }
}

# 装机并发数, 一个任务最多支持的同时装机数量.
MAX_THREAD_NUM = 20


# 虚拟机信息
# 虚拟机集群信息, node_id 表示机器的宿主机来源, over_conf 表示超配额度.
VM_AREAS = {
    "apps": {
        "node_id": 4278,
        "over_conf": 0.2
    },
    "eyepetizer": {
        "node_id": 4279,
        "over_conf": 0.2
    },
    "dt": {
        "node_id": 4280,
        "over_conf": 0.2
    },
    "pre-online": {
        "node_id": 4281,
        "over_conf": 0.5
    },
    "dev": {
        "node_id": 4282,
        "over_conf": 0.2
    }
}
IGNORED_VMHS_NODE = 4296

# 一些参数.
# DISK_DEFAULT = ""
NETMASK_DEFAULT = "255.255.255.0"
KSS = {
    "centos6": "http://pxe.internal.DOMAIN.COM/ks/centos6_x64_kvm_guest.cfg",
    "centos7": "http://pxe.internal.DOMAIN.COM/ks/centos7_kvm_guest.cfg",
}
LOCATIONS= {
    "centos6": "/tmp/CentOS-6.3-x86_64-minimal.iso",
    "centos7": "/tmp/CentOS-7-x86_64-DVD-1511.iso"
}

BRIDGE_DEFAULT = "br2"
OS_SIZE = 18   # 系统盘大小(G)

# puppet ca, 申请到主机名之后需要清掉 ca 上已经签发的证书, 防止新机器申请证书失败.
PUPPET_CA_HOST = "puppetca.corp.DOMAIN.COM:8140"
PUPPET_DOMAIN = ".DOMAIN.COM"
