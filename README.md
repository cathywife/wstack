#wdstack 包括两个部分:

##1. 物理装机系统, 基于 racadm + pxe + ks, 目前只用在 DELL 机器.

pm 目录下是物理装机系统的代码, 原理见: http://www.nosa.me/?p=46

目前有两个功能:
   
```
自动安装, 全自动安装, 调用 API 即可, 不需要人为干预;
手动安装, 调用 API 后需要人为控制机器进入 PXE 模式才可安装, 一般在控制卡连不上的时候使用.
   
```

说明:
   
```
机器 hostname 和 ip 会从资产系统自动获取, 由装机之后的 %post 脚本实现, 先从 /api/v1/pm/message 获取 sn 的 usage, 作为申请主机名的 key, 根据装机时刻 DHCP 拿到的内网网段作为申请 ip 的 key, hostname 和 ip 都申请到之后再通过 /api/v1/pm/message 传回本系统.
支持 user data, 用于装机之后执行自定义脚本.

```


<br/>

##2. 虚拟机系统.

vmmaster 是 master, vmagent 是 agent, agent 跑在每台宿主机上, master 和 agent 通过 RPC 通信.

包括三个功能:

```
创建虚拟机, 包括 origin 和 wmi 方式, origin 基于 ks, wmi 即是镜像安装. 创建虚拟机同样支持 user data;
操作虚拟机, 包括 删除、关机和重启;
创建镜像, 镜像包括系统盘和数据盘, 对系统盘采用创建 qcow2 格式, 对数据盘 home 分区则采用 tar 包 的方式，因为 tar 支持 exclude 功能, 可以把 logs 等日志排除掉.

```


<br/>

##3. 部署.

使用 circus 部署，发布不会影响当前请求。
