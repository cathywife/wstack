#-*- coding: utf-8 -*- 

import os
import re

from libs import utils


def check_mfs():
    """ 通过本机挂载 mfs 上传, 所以要先检查 /mfs 是否已经挂载.

    """
    try:
        utils.shell("df -h |grep /mfs")   # 先判断是否已经挂载 mfs.
    except Exception, e:
        cmd = "curl http://download.hy01.nosa.me/download/install_mfs_client.sh |bash"
        utils.shell(cmd)
        utils.shell("df -h |grep /mfs")


def check_nbd():
    """ 检查 nbd 模块是否已经加载, 如果没有, 则自动加载(同时安装 qemu).

    """
    try:
        utils.shell("/sbin/lsmod | grep nbd")
    except Exception, e:
        cmd = "curl http://download.hy01.nosa.me/download/install_nbd.sh |bash"
        utils.shell(cmd)
        utils.shell("/sbin/lsmod | grep nbd")
        return

    # 发现 nbd 时间久了会卡死, 这里写卸载再加载.
    # 这样并发执行使用 nbd 的任务是会有问题, mark.
    # utils.shell("/sbin/rmmod nbd && sleep 1")
    # utils.shell("/sbin/modprobe nbd")


def get_url_from_filename(file_name):
    """ 根据文件名返回下载地址.

    """
    return "http://download.hy01.nosa.me/download/wmi/{file_name}".format(
        file_name=file_name)


def get_filename_from_url(url):
    """ 从 url 中得到文件名.

    """
    return os.path.basename(url)


def get_path_from_filename(file_name):
    """ 根据文件名返回绝对路径.

    """
    return "/mfs/wmi/" + file_name


def get_filename_from_path(path):
    """ 根据文件名返回绝对路径.

    """
    return os.path.basename(path)


def upload_os(volume_path, file_name):
    """ 上传系统 volume, 我们使用 qemu-img convert 命令.
    
    """
    check_mfs()

    # 不使用压缩(-c), 太慢了.
    cmd = """qemu-img convert -O qcow2 {volume_path} {file_path}""".format(
        volume_path=volume_path, 
        file_path=get_path_from_filename(file_name))
    utils.shell(cmd)
    return get_url_from_filename(file_name)


def upload_os_tar(volume_path, file_name):
    """ 上传系统盘数据, 打出来 tar 包.
    
    此函数创建的系统盘 tar 文件用于在 raw 格式的宿主机上创建虚拟机.

    """
    check_mfs()
    check_nbd()

    from libs import volume
    volume_path_type = volume.path_type(volume_path)

    if volume_path_type == "qcow2":
        nbd_device = utils.get_available_nbd_device()
        utils.connect_nbd_device(nbd_device, volume_path)
        volume_path = nbd_device

    try:
        cmd = "guestfish -a {path} run : list-filesystems".format(path=volume_path)
        fs_text = utils.shell(cmd)
    except Exception, e:
        utils.shell("yum -y update qemu-kvm")    
        fs_text = utils.shell(cmd)
    mount_cmds = ""
    for line in fs_text.strip().splitlines()[2:]:   # 前两个是 boot 和 swap.
        block_path = line.split(":")[0]
        if block_path.split("/")[-1] == "root":
            dir = "/"
        elif block_path.split("/")[-1] in ["usr", "tmp", "opt", "var"]:
            dir = block_path.split("/")[-1]
        else:
            dir = "/"
        if dir == "/":
            mount_root_cmds = "mount {path} {dir}".format(path=block_path, dir=dir)
        if dir != "/":
            mount_cmds += "mount {path} /{dir} ".format(path=block_path, dir=dir)
            mount_cmds += ": "
    # / 最先被挂载.
    mount_cmds = mount_root_cmds + " : " +  mount_cmds

    cmd = "guestfish -a {block_path} run : {mount_cmds} tar-out / {file_path}".format(
        block_path=volume_path, 
        mount_cmds=mount_cmds,
        file_path=get_path_from_filename(file_name))
    utils.shell(cmd)

    if volume_path_type == "qcow2":
        utils.disconnect_nbd_device(nbd_device)

    return get_url_from_filename(file_name)


def _aggregate_log_dir(files):
    """ 聚合日志.

    检查名为 log 或 logs 的目录, 并聚合.

    """
    log_dirs = list()

    # 得到含有日志的目录和文件.
    log_files = list()
    for _file in files:
        _file = _file.strip()
        if re.match("^log/|^logs/|.*/log|.*/logs", _file):
            log_files.append(_file)

    # 进行聚合.
    for log_file in log_files:
        log_split = log_file.split("/")
        if "log" in log_split and "logs" in log_split: 
            log_index = log_split.index("log")
            logs_index = log_split.index("logs")
            if log_index < logs_index:
                index = log_index + 1
            else:
                index = logs_index + 1
        elif "log" in log_split:
            index = log_split.index("log") + 1
        elif "logs" in log_split:
            index = log_split.index("logs") + 1
        else:
            continue

        log_dirs.append("/".join(log_split[:index]))

    log_dirs = {}.fromkeys(log_dirs).keys()
    return map(lambda s: s+"/*", log_dirs)


def upload_data(name, is_running, volume_path, file_name, excludes):
    """ 上传数据, 我们使用 guestfish tar-out 命令.

    excludes 指定了去除的目录或文件, 这里我们默认去除 log 和  logs 目录和 bash_history 文件.

    """
    check_mfs()

    if excludes is None:
        excludes = []
    else:
        excludes = excludes.strip().split(",")

    if "work/*" in excludes:
        excludes_default = []
    else:
        if not is_running:
            cmd = '''guestfish -d {name} -i sh "find /home -type d -name log -o -name logs " '''.format(
                name=name)
            excludes_default = [i.strip() + "/*" for i in utils.shell(cmd, strip=True).splitlines()]
        else:
            cmd = '''guestfish add {volume_path} : run : mount /dev/datavg/home / : find /'''.format(
                volume_path=volume_path)
            # 有些宿主机 qemu-kvm 版本过低, 会导致 run 失败, 这里升级一下 qemu-kvm.
            try:
                files = utils.shell(cmd)
            except Exception, e:
                utils.shell("yum -y update qemu-kvm")
                files = utils.shell(cmd)

            data_files = [i.strip() for i in files.strip().splitlines()]
            excludes_default = _aggregate_log_dir(data_files)

    # 去除 bash_history.
    excludes_default.append("*/.bash_history")

    # 和默认的 excludes 相加去重, 得到最后的 excludes.
    excludes.extend(excludes_default)
    excludes = {}.fromkeys(excludes).keys()
    excludes = " ".join(excludes)

    # 打包.
    if not is_running:
        cmd = '''guestfish -d {name} run : mount /dev/datavg/home / : tar-out / {file_path} compress:gzip "excludes:{excludes}"'''.format(
            name=name, 
            file_path=get_path_from_filename(file_name), 
            excludes=excludes)
    else:
        cmd = '''guestfish add {volume_path} : run : mount /dev/datavg/home / : tar-out / {file_path} compress:gzip "excludes:{excludes}"'''.format(
            volume_path=volume_path, 
            file_path=get_path_from_filename(file_name),  
            excludes=excludes)
    utils.shell(cmd)
    return get_url_from_filename(file_name)


def get_partition(os_volume_path, wmi_id):
    """ 拿到分区表信息, 会备份 mbr 和 boot 分区.

    当在 raw 格式的宿主机上基于镜像创建虚拟机时, 会用到此功能.    

    """
    check_mfs()
    check_nbd()

    # 连接 nbd 设备.
    nbd_device = utils.get_available_nbd_device()
    utils.connect_nbd_device(nbd_device, os_volume_path)

    # 备份 boot 分区和 lvm header 信息.
    # 使用 dd 备份 boot 分区:
    # MBR 的 512 字节中的前 446 字节是 Boot loader, Boot loader 
    # 会根据位置查找 boot 分区中的引导文件来继续引导, 故而使用拷贝数据的
    # 方式不凑效.
    # 备份 lvm header 的原因:
    # 系统盘中的 LVM vg 可能和宿主机中的 vg 重名, 会修改它, 
    # 所以备份 lvm header 以便恢复.
    partition_dict = dict()
    cmd = "fdisk -ul {device}".format(device=nbd_device)
    partition_text = utils.shell(cmd)    
    for line in partition_text.strip().splitlines():
        if re.match("^/dev/", line):
            if "*" in line:
                # 备份 mbr, 备份硬盘第一个字节到第一个分区之前的最后一个字节, 原因见 backup_mbr 函数.
                utils.backup_mbr(nbd_device, get_path_from_filename(wmi_id+"_mbr"),
                    (int(line.split()[2]) - 1) * 512)
                partition_dict["mbr"] = {
                    "url": get_url_from_filename(wmi_id+"_mbr")
                }

                # 备份 boot.
                utils.backup_boot(line.split()[0], get_path_from_filename(wmi_id+"_boot"))
                partition_dict["boot"] = {
                    "url": get_url_from_filename(wmi_id+"_boot")
                }
            elif "swap" in line:
                # 备份 swap uuid.
                partition_dict["swap"] = {
                    "uuid": utils.get_swap_uuid(line.split()[0])
                }
            elif "LVM" in line:
                # 备份 LVM.
                utils.backup_lvmheader(line.split()[0], get_path_from_filename(wmi_id+"_lvmheader"))
                partition_dict["lvmheader"] = {
                    "url": get_url_from_filename(wmi_id+"_lvmheader")
                }

    # 断开 nbd 设备连接.
    utils.disconnect_nbd_device(nbd_device)

    return partition_dict


def restore_rawos_from_qcow2_image(dst_os, wmi_data):
    """ 把 qcow2 格式化的系统盘镜像恢复到 raw 格式的系统盘镜像.

    """
    check_mfs()

    # 拿到需要的文件路径.
    src_os_url = wmi_data["os"]["tar"]   # 用系统盘的 tar 包.

    src_mbr = get_path_from_filename(get_filename_from_url(wmi_data["partition"]["mbr"]["url"]))
    src_boot = get_path_from_filename(get_filename_from_url(wmi_data["partition"]["boot"]["url"]))
    src_lvmheader = get_path_from_filename(get_filename_from_url(wmi_data["partition"]["lvmheader"]["url"]))
    src_swap_uuid = wmi_data["partition"]["swap"]["uuid"]

    # 恢复 mbr.
    utils.restore_mbr(src_mbr, dst_os)

    # 映射系统盘中的设备, 拿到 boot, swap 和 lvm 设备路径.
    x = utils.kpartx_av(dst_os)
    dst_boot, dst_swap, dst_lvm = x[0], x[1], x[2]   # kpartx 拿到结果是这个顺序.

    # 恢复 boot 分区.
    utils.restore_boot(src_boot, dst_boot)

    # 恢复 swap 分区.
    utils.make_swap(dst_swap, src_swap_uuid)

    # 恢复 lvm header.
    utils.restore_lvmheader(src_lvmheader, dst_lvm)    

    # 导入目标虚拟机中的 lvm, 拿到 vg name.
    # vgimportclone 可能会报 fatal: not in vg 的错误, 升级 qemu-kvm 后解决.
    try:
        utils.vgimportclone(dst_lvm)
    except Exception, e:
        utils.shell("yum -y update qemu-kvm")
        utils.vgimportclone(dst_lvm)
    dst_lvm_vg_name = utils.get_vg_name_from_pv(dst_lvm)

    # 对目标虚拟机的 lvm vg 改名, 激活 vg, 获取 vg 中的 lv, 并格式化.
    utils.vg_enable(dst_lvm_vg_name)
    dst_lvm_lvs = utils.get_lvs_from_vgname(dst_lvm_vg_name)
    map(utils.mkfs_ext4, dst_lvm_lvs)

    # 准备挂载目录.
    random_id = utils.random_id()
    dst_mount_dir = "/mnt/{random_id}/".format(random_id=random_id)
    os.makedirs(dst_mount_dir)

    # 挂载函数.
    def _mount(lvs, base_dir):
        lv_root = filter(lambda x : "-root" in x, lvs)[0]   # 只有一个 root lv.
        utils.mount(lv_root, base_dir)   # 先挂载 root 目录, 
        for lv in utils.list_subtraction(lvs, [lv_root]):
            x = base_dir + "/" + lv.split("-")[-1]
            if not os.path.isdir(x):
                os.makedirs(x)
            utils.mount(lv, x)

    # 挂载目标虚拟机中的 lvm lv.
    _mount(dst_lvm_lvs, dst_mount_dir)

    # 拷贝数据.
    cmd = "curl {src_tar_url}| tar xf - -C {dst_dir}".format(
        src_tar_url=src_os_url, dst_dir=dst_mount_dir)
    utils.shell(cmd)

    # 卸载函数.
    def _umount(base_dir):
        cmd = "df | grep %s | awk '{print $NF}'" % base_dir.rstrip("/")
        umount_dirs = utils.shell(cmd, strip=True).splitlines()
        umount_dirs = umount_dirs[::-1]   # 反转, 先挂载的后卸载.
        map(utils.umount, umount_dirs)

    # 卸载目录, 删除临时挂载目录.
    _umount(dst_mount_dir)
    import shutil
    shutil.rmtree(dst_mount_dir)

    # disable vg.
    utils.vg_disable(dst_lvm_vg_name)

    # 上面修改过 vg name，需要还原, 覆盖 lvm header 即可.
    utils.restore_lvmheader(src_lvmheader, dst_lvm)

    # disable 目标虚拟机的 lvm vg, 去掉映射.
    utils.kpartx_dv(dst_os)
