#-*- coding: utf-8 -*-

import time
import traceback

import ujson as json

from web.const import REDIS_DB_PM
from libs import asset_utils, redisoj


client = redisoj.RedisClient().get(REDIS_DB_PM)


def exception(func):
    def _decorator(*args, **kwargs):
        sn = args[0]["sn"]
        try:
            # 如果机器已经存在, 屏蔽报警.
            if asset_utils.is_exist_for_sn(sn):
                hostname = asset_utils.get_value_from_sn(sn, "hostname")

            # 执行安装.
            return_data = func(*args, **kwargs)
        except Exception, e:
            data = args[0]
            data["code"] = 1
            data["error_message"] = traceback.format_exc()
            return data

        # 如果这台机器在宿主机黑名单中, 删除.
        from vmmaster.libs import utils
        utils.del_ignore(sn)

        return_data["code"] = 0
        return_data["error_message"] = None
        return return_data

    return _decorator


def wait(sn, timeout=2700, interval=10):
    timetotal = 0
    installed = False
    in_asset = False

    while timetotal < timeout:
        if not installed:
            hostname = json.loads(client.hget(sn, "hostname"))
            ip = json.loads(client.hget(sn, "ip"))

            if "" in [hostname, ip]:
                time.sleep(interval)
                timetotal += interval
            else:
                installed = True

        elif installed and not in_asset:
            try:
                status = asset_utils.get_value_from_sn(sn, "status")
                if status == "online":
                    in_asset = True
                else:
                    raise Exception("{sn} status is not online".format(sn=sn))
            except Exception, e:
                time.sleep(interval)
                timetotal += interval                
        else:
            break
    return installed, in_asset, hostname, ip
