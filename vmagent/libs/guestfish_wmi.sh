#!/bin/bash

name=$1
uuid=$2
ip=$3
netmask=$4
gateway=$5
hostname=$6
hwaddr_em2=$7
hwaddr_em1=$8


# 定义虚拟机, 否则无法根据域修改镜像.
virsh define /etc/libvirt/qemu/$name.xml || exit 1 

# 修改系统镜像, 包括:
# 1. 修改主机名;
# 2. 修改网卡设置(增加HWADDR的原因是系统可以把eth变成em);
# 3. 修改路由信息;
# 4. 重写 /etc/sn;
# 5. 删除 last 和 histroy 信息;
# 6. 删除 /etc/udev/rules.d/70-persistent-net.rules;
# 7. 删除 /var/lib/puppet;
# 8. 删除 /home/work/lighttpd/nginx_check/index.html;
# 9. 配置 post custom 脚本;
# 额外的, 有些镜像的 /etc/resolv.conf 是老的, 导致无法解析, 为了解决这个问题, 我们覆盖
# /etc/resolv.conf.
#
guestfish --rw -d $name -i <<_EOF_
command "sed -i 's/HOSTNAME=.*/HOSTNAME=${hostname}/g' /etc/sysconfig/network"
write /etc/hostname "${hostname}"

write /etc/sysconfig/network-scripts/ifcfg-em2 "DEVICE=em2\nHWADDR=${hwaddr_em2}\nBOOTPROTO=static\nIPADDR=$ip\nNETMASK=$netmask\nONBOOT=yes\nTYPE=Ethernet"

write /etc/sysconfig/network-scripts/ifcfg-em1 "DEVICE=em1\nHWADDR=${hwaddr_em1}"

write /etc/sysconfig/network-scripts/route-em2 "192.168.0.0/16 via ${gateway}\n10.0.0.0/8 via ${gateway}\n100.64.0.0/16 via ${gateway}\n0.0.0.0/0 via ${gateway}"

write /etc/sn "$uuid"

write /var/log/wtmp ""
write /var/log/lastlog ""
write /root/.bash_history ""
command "/bin/rm -rf /etc/udev/rules.d/70-persistent-net.rules"
command "/bin/rm -rf /var/lib/puppet/"
command "/bin/rm -f /home/work/lighttpd/nginx_check/index.html"

write-append /etc/rc.d/rc.local "curl http://wdstack.internal.nosa.me/script/gen_post_custom.sh | bash"

write /etc/resolv.conf "search nosa.me\nnameserver 10.19.20.234"
_EOF_

virsh start $name || exit 1
virsh autostart $name || exit 1


# 启动.
total=80
count=0
while [ $count -lt $total ]
do
    if ping -c 1 -W 1 $ip &>/dev/null
    then
        exit 0
    fi
    ((count++))
done
echo "ping $ip fail"
exit 1
