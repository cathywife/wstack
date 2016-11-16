#!/bin/bash

name=$1
uuid=$2

guestfish --rw -d $name -i <<_EOF_
write /etc/sn "$uuid"
_EOF_
