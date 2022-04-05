#!/bin/bash
#
# run command first: sudo mv /var/run/usbmuxd /var/run/usbmuxx
# forward through socat: sudo socat -t100 -x -v UNIX-LISTEN:/var/run/usbmuxd,mode=777,reuseaddr,fork UNIX-CONNECT:/var/run/usbmuxx

SOCKET="/var/run/usbmuxd"
BACKUP_SOCKET="$(dirname "${SOCKET}")/$(basename "${SOCKET}").tidevice_bak"
FORWARD_SOCKET=${BACKUP_SOCKET}

if test $(whoami) != "root"; then
	echo "Must be run as root"
	exit 1
fi

while [[ $# -gt 0 ]]; do
	case $1 in
	-s | --ssl)
		SSL="--ssl"
		shift # past argument
		;;
	-t | --tcp_redirect)
		REDIRECT_PORT="$2"
		FORWARD_SOCKET="127.0.0.1:${REDIRECT_PORT}"
		shift # past argument
		shift # past value
		;;
	-* | --*)
		echo "Unknown option $1"
		exit 1
		;;
	*)
		shift # past argument
		;;
	esac
done

DEVICES=($(tidevice list | sed -n '2p'))
UDID=${DEVICES[0]}
NAME=${DEVICES[1]}
echo "UDID: ${UDID:?} ${NAME}"

# 保存设备配对公钥
tidevice savesslfile

# 需要host证书提供给client，host私钥以解密client数据

PEMFILE=ssl/${UDID}_all.pem
if ! test -f $PEMFILE; then
	echo "Pemfile: $PEMFILE not exists"
	exit 1
fi

function recover() {
	echo "Recover"
	mv ${BACKUP_SOCKET} ${SOCKET}
	# kill socat
	kill %%
}

sudo mv ${SOCKET} ${BACKUP_SOCKET}
trap recover EXIT

# 启用 tcp redirect 后可以用 https://github.com/douniwan5788/usbmuxd_debug.git 在wireshark中抓包分析
if [ x"$REDIRECT_PORT" != x"" ]; then
	# Setup pipe over TCP that we can tap into
	socat -t100 "TCP-LISTEN:${REDIRECT_PORT},bind=127.0.0.1,reuseaddr,fork" "UNIX-CONNECT:${BACKUP_SOCKET}" &
	export SSLKEYLOGFILE
fi

# sudo socat -t100 -v UNIX-LISTEN:${SOCKET},mode=777,reuseaddr,fork UNIX-CONNECT:${SOCKET}.tidevice_orig
python3 plistdump-tcp-proxy.py -L ${SOCKET} -F ${FORWARD_SOCKET} ${SSL} \
	--pemfile ${PEMFILE} "$@"
