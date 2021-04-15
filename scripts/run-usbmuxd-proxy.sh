#!/bin/bash
#
# run command first: sudo mv /var/run/usbmuxd /var/run/usbmuxx
# forward through socat: sudo socat -t100 -x -v UNIX-LISTEN:/var/run/usbmuxd,mode=777,reuseaddr,fork UNIX-CONNECT:/var/run/usbmuxx

UDID=$(idevice_id -l)
echo "UDID: ${UDID:?} $(idevicename -u $UDID)"

# 保存设备配对公钥
#tidevice savesslfile # not implemented yet.

PEMFILE=ssl/${UDID}_root.pem
if ! test -f $PEMFILE
then
	echo "Pemfile: $PEMFILE not exists"
	exit 1
fi


if test $(whoami) != "root"
then
	echo "Must be run as root"
	exit 1
fi

function recover(){
	echo "Recover"
	mv /var/run/usbmuxx /var/run/usbmuxd
}

sudo mv /var/run/usbmuxd /var/run/usbmuxx
trap recover EXIT

sudo python3 plistdump-tcp-proxy.py -L /var/run/usbmuxd -F /var/run/usbmuxx \
	--pemfile ${PEMFILE} "$@"
