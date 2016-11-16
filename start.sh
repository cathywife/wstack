#!/bin/bash


# export PYTHONPATH=.

# nohup python web/main_service.py &
# 
# nohup python tools/vm_sync.py &
# nohup python tools/vm_resource_free.py &
 
export working_dir=.
export PYTHONPATH=.
nohup circusd deploy/circus.ini &
