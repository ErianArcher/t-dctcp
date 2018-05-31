#!/bin/bash
make
cp ./tcp_tdctcp.ko /lib/modules/$(uname -r)/kernel/net/ipv4/
depmod -A
modprobe tcp_tdctcp
