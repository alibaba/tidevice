#!/bin/bash
#

if test $(whoami) != "root"
then
	sudo "$0"
	exit
fi

mv /var/run/usbmuxd /var/run/usbmuxd-orig
trap "mv /var/run/usbmuxd-orig /var/run/usbmuxd" EXIT

socat -t100 -x -v UNIX-LISTEN:/var/run/usbmuxd,mode=777,reuseaddr,fork UNIX-CONNECT:/var/run/usbmuxd-orig


