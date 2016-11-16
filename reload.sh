#!/bin/bash

# 只有 wdstack 支持信号平滑退出, 会等请求结束再退出.
# 其他进程没有, 其他进程会退出.
# 进程退出之后都会被 circusd 起来.
for i in main_service.py vmh_info_sync.py vmh_list_sync.py vmh_resource_email.py
do
    ps -ef |grep $i |grep -v grep |awk '{print $2}' |xargs sudo kill
done
