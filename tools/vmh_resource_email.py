#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import datetime
import time

from libs import mail
from vmmaster.libs import utils
from web.const import VM_AREAS


def get_resource(area, idc):
    return_list = list()
    ignore_vmhs = utils.get_ignore_vmhs()
    for vmh in utils.get_vmhs(area, idc):
        _dict = {
            "area": area,
            "idc": idc,
            "vmh": vmh,
            "vcpu": utils.get_info(vmh, "vcpu")["free"],
            "mem": utils.get_info(vmh, "mem")["free"],
            "space": utils.get_info(vmh, "space")["free"]
        }

        if vmh in ignore_vmhs:
            _dict["ignored"] = True
        else:
            _dict["ignored"] = False
        return_list.append(_dict)
    return_list.sort(key=lambda t: (t["vcpu"], t["mem"], t["space"]), reverse=True)
    return_list = return_list[:100]
    return return_list


def _main():
    areas = VM_AREAS.keys()
    idcs = utils.get_idcs()

    content = u"""每个 area 和 idc 剩余资源 TOP100.<br/><br/>
        可以访问下面 url 查看具体 area 和 idc 的资源:<br/><br/>
        http://wdstack.internal.nosa.me/api/v1/vm/resources/?area=apps&idc=hlg01
        <br/><br/><br/><br/>
    """

    for area in areas:
        for idc in idcs:
            resouce = get_resource(area, idc)
            if resouce == []:
                continue
            else:
                content += mail.content_format(
                    resouce, main=["ignored", "area", "idc", "vmh", "vcpu", "mem", "space"])
                content += "<br/><br/>"

    today = datetime.datetime.now().strftime('%Y%m%d')
    subject = u"|wdstack 虚拟机| 每日资源统计 - {today}".format(today=today)

    mail.send(None, subject, content)


def main():
    if os.getenv('RUN_ONCE'):
        _main()
        sys.exit(0)

    while 1:
        tomorrow_now = datetime.datetime.now() + datetime.timedelta(days=1)
        string = tomorrow_now.strftime("%Y-%m-%d")
        tomorrow_zero = datetime.datetime.strptime(string, "%Y-%m-%d")
        tomorrow_zero.strftime("%s")
        tomorrow_zero_seconds = int(tomorrow_zero.strftime("%s"))
        time.sleep(tomorrow_zero_seconds + 3600 * 2 - time.time())

        _main()


if __name__ == '__main__':
    main()
