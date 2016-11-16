#!/bin/bash

export PYTHONPATH=.

# for i in main_service.py vmh_info_sync.py vmh_list_sync.py vmh_resource_email.py
for i in  circusd main_service.py vmh_info_sync.py vmh_list_sync.py vmh_resource_email.py
do
    ps -ef |grep $i |grep -v grep |awk '{print $2}' |xargs sudo kill
done
