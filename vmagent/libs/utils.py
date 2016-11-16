#-*- coding: utf-8 -*- 

import os
import subprocess
import re
import random
import time

from libs import log


logger = log.LogHandler().logger


def shell(cmd, exception=True, strip=False):
    process = subprocess.Popen(args = cmd, 
        stdout = subprocess.PIPE, stderr = subprocess.PIPE, 
        shell = True)
    std_out, std_err = process.communicate()
    return_code = process.poll()

    if return_code == 0:
        logger.info("cmd:{cmd}".format(cmd=cmd))
    else:
        message = "cmd:{cmd}, error:{error}".format(cmd=cmd, error=std_err)
        logger.warning(message)
        if exception:
            raise Exception(message)
        else:
            return
    if strip:
        return std_out.strip()
    else:
        return std_out


def is_valid_ip(ip):
    """Returns true if the given string is a well-formed IP address.

    Supports IPv4 and IPv6.

    """
    import socket
    if not ip or '\x00' in ip:
        return False
    try:
        res = socket.getaddrinfo(ip, 0, socket.AF_UNSPEC,
                                 socket.SOCK_STREAM,
                                 0, socket.AI_NUMERICHOST)
        return bool(res)
    except socket.gaierror as e:
        if e.args[0] == socket.EAI_NONAME:
            return False
        raise
    return True


def random_id():
    total_len = 10
    base_str1 = [str(i) for i in range(0, 10)]
    base_str2 = [chr(i)
                 for i in range(ord('a'), ord('z') + 1)]
    random.seed()
    total_sample = []
    total_sample += random.sample(base_str1, random.randint(1, len(base_str1)))
    total_sample += random.sample(base_str2, total_len - len(total_sample))
    random.shuffle(total_sample)
    return ''.join(total_sample)


def random_mac():
    mac = [ 0x00, 0x16, 0x3e, random.randint(0x00, 0x7f),
            random.randint(0x00, 0xff), random.randint(0x00, 0xff) ]
    s = list()
    for item in mac:
        s.append(str("%02x" % item))

    return  ':'.join(s)


def wget(url, target, speed="30m"):
    """  下载文件.

    """
    cmd = "wget -q --limit-rate={speed} {url} -O {target}".format(
        speed=speed, url=url, target=target)
    shell(cmd)


def list_subtraction(list1, list2):
    """ 两个 list 相减.

    在 list1 中但不在 list2 中的元素列表.

    """
    return [i for i in list1 if i not in list2]


# def list_subdirs(dir):
#     """ 查看一个目录下的子目录.

#     """
#     for root, subdirs, files in os.walk(dir):
#         return subdirs


def check_wait(check_cmd, post_cmd, timeinit=0, 
               interval=10, timeout=1200):
    """  循环等待某一条件失败, 就执行 post_cmd, 时间超过 timeout 就超时.

    """
    timetotal = timeinit

    while timetotal < timeout:
        try:
            shell(check_cmd)
        except Exception, e:
            try:
                shell(post_cmd)
                return True
            except Exception, e:
                return False

        time.sleep(interval)
        timetotal += interval

    return False


def virbr0_delete():
    """ 我们使用桥接模式, 所以删除 virbr0.
    
    """
    cmds = [
        "virsh net-destroy default",
        "virsh net-undefine default",
        "/etc/init.d/libvirtd restart"
    ]
    map(shell, cmds)


def backup_mbr(block_path, file_path, bytes=512):
    """ 保存 mbr.

    对于 Centos6 的虚拟机(grub 版本是 0.97), 只要备份硬盘的前 512 字节就可以了;

    但是对于 Centos7(使用 grub2) 不够, 会启动不了, 可能使用 grub2 的方式在 512 字节
    后面有启动程序, 经过我测试, 备份第一个字节到第一个分区之前的最后一个字节可以正常启动.

    所以对于 Centos7 需要指定 bytes.

    """
    cmd = "dd if={if_path} of={of_path} bs={bytes} count=1".format(
        if_path=block_path,
        of_path=file_path,
        bytes=bytes)
    shell(cmd)


def backup_boot(block_path, file_path):
    """ 保存 boot 分区.

    """
    cmd = "dd if={if_path} of={of_path}".format(
        if_path=block_path, 
        of_path=file_path)
    shell(cmd)


def backup_lvmheader(block_path, file_path):
    """ 保存 lvm header 信息.

    """
    cmd = "dd if={if_path} of={of_path} bs=512 count=24".format(
        if_path=block_path, 
        of_path=file_path)
    shell(cmd)


def restore_mbr(file_path, block_path):
    """ 恢复 mbr.

    对于 Centos6 可以使用 bs=512 count=1 的参数, 但是对于 Centos7, mbr 的字节数
    不确定, 所以这里统一不适用使用 bs=512 count=1 .

    """
    # cmd = "dd if={if_path} of={of_path} bs=512 count=1 conv=notrunc".format(
    #     if_path=file_path, 
    #     of_path=block_path)
    cmd = "dd if={if_path} of={of_path} conv=notrunc".format(
        if_path=file_path, 
        of_path=block_path)
    shell(cmd)


def restore_boot(file_path, block_path):
    """ 恢复 boot 分区.

    """
    cmd = "dd if={if_path} of={of_path} bs=10M".format(
        if_path=file_path, 
        of_path=block_path)
    shell(cmd)


def restore_lvmheader(file_path, block_path):
    """ 恢复 lvm header.

    """
    cmd = "dd if={if_path} of={of_path} bs=512 count=24 conv=notrunc".format(
        if_path=file_path, 
        of_path=block_path)
    shell(cmd)


def kpartx_av(block_path):
    """ 映射设备.

    返回映射出来的设备的路径.

    """
    cmd = "kpartx -av {block_path}".format(block_path=block_path)
    return map(lambda t: "/dev/mapper/"+t.strip().split()[2], 
        shell(cmd, strip=True).splitlines())


def kpartx_dv(block_path):
    """ 取消映射设备.

    """
    cmd = "kpartx -dv {block_path}".format(block_path=block_path)
    shell(cmd)


def get_available_nbd_device():
    """ 获取可用的 nbd 设备.

    假设有 16 个设备, 需在存储机器上使用下面命令来生成设备:

    modprobe nbd max_part=16

    """
    for number in xrange(16):
        device = "/dev/nbd{number}".format(number=number)
        std_out = shell("fdisk -ul {device}".format(device=device))
        if std_out.strip() == "":
            return device
    raise Exception("no nbd device available")


def connect_nbd_device(device, qcow2_path):
    """ 连接 nbd 设备.

    返回连接之后的设备路径.

    """
    cmds = [
        "qemu-nbd -n -c {device} {qcow2_path}".format(
            device=device,
            qcow2_path=qcow2_path
            ),
        "partprobe {device}".format(
            device=device),
        "sleep 3",   # 有时候发现 ls {device}p* 会报错, 睡眠一下问题没问题了.
        "ls {device}p*".format(
            device=device),
    ]
    return map(shell, cmds)[-1].strip().splitlines()


def disconnect_nbd_device(device):
    """ 断开 nbd 设备.

    """
    shell("qemu-nbd -d {device}".format(device=device))


def vgimportclone(pv):
    """ 导入并修改重名的 vg.

    """
    cmd = "vgimportclone -i {pv}".format(pv=pv)
    shell(cmd)


def get_vg_name_from_pv(pv):
    """ 根据 pv 获取 vg name.
    
    """
    cmd = """ pvs | awk '$1=="%s"{print $2}' """ % pv
    return shell(cmd, strip=True)


# def get_vg_uuid():
#     """ 获取机器的 vg uuid 列表.

#     """
#     cmd = "vgdisplay | grep 'VG UUID' | awk '{print $NF}'"
#     return shell(cmd, strip=True).splitlines()


# def vg_rename(vg_uuid, vg_name):
#     """ 修改 vg 名称.

#     """
#     cmd = "vgrename {vg_uuid} {vg_name}".format(vg_uuid=vg_uuid, vg_name=vg_name),
#     shell(cmd)


def vg_enable(vg_name):
    """ enable 一个 vg.

    """
    cmd = "vgchange -a y {vg_name}".format(vg_name=vg_name)
    shell(cmd)


def vg_disable(vg_name):
    """ disable 一个 vg.

    """
    cmd = "vgchange -a n {vg_name}".format(vg_name=vg_name)
    shell(cmd)


def get_lvs_from_vgname(vg_name):
    """ 获取一个 vg 的所有 lv.

    """
    cmd = "ls /dev/mapper/{vg_name}*".format(vg_name=vg_name)
    return shell(cmd, strip=True).splitlines()


def mount(block_path, dir, fs=None):
    """ 挂载目录.

    """
    if fs is None:
        cmd = "mount {block_path} {dir}".format(block_path=block_path, dir=dir)
    else:
        cmd = "mount -t {fs} {block_path} {dir}".format(fs=fs, block_path=block_path, dir=dir)
    shell(cmd)


def umount(dir):
    """ 卸载目录.

    """
    cmd = "umount -l {dir}".format(dir=dir)
    shell(cmd)


def mkfs_ext4(block_path):
    """ 创建 ext4 文件系统.

    """
    cmd = "mkfs.ext4 {path}".format(path=block_path)
    shell(cmd)


def make_swap(block_path, uuid=None):
    """ 创建 swap 分区.

    """
    if uuid is None:
        cmd = "mkswap -f {path}".format(path=block_path)
    else:
        cmd = "mkswap -f -U {uuid} {path}".format(uuid=uuid, path=block_path)
    shell(cmd)


def get_swap_uuid(block_path):
    """ 获取 swap uuid.

    """
    cmd = """blkid %s | awk '{print $2}' | awk -F= '{print $2}' | sed 's/"//g'""" % block_path
    return shell(cmd, strip=True)
