#!/bin/bash
#
# run command first: sudo mv /var/run/usbmuxd /var/run/usbmuxx
# forward through socat: sudo socat -t100 -x -v UNIX-LISTEN:/var/run/usbmuxd,mode=777,reuseaddr,fork UNIX-CONNECT:/var/run/usbmuxx

PROGRAM="$(basename $0)"
SOCKET="/var/run/usbmuxd"
BACKUP_SOCKET="$(dirname "${SOCKET}")/$(basename "${SOCKET}").tidevice_bak"
FORWARD_SOCKET=${BACKUP_SOCKET}
CURDIR=$(cd $(dirname $0); pwd)

USAGE="Usage:
	$PROGRAM --help               Show this message
	$PROGRAM [--ssl|-s]           Enable SSL inspect
	$PROGRAM --tcp_redirect 6789
"

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
	-h | --help)
		echo -n "$USAGE"
		exit 0
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


function safe_run_bg() {
	local DEBUG_COLOR="\033[0;32m"
	local RESET="\033[0m"
	echo -e "${DEBUG_COLOR}>> $@""${RESET}"
	"$@" &
	PID=$!
	trap "kill $PID" EXIT
}

function safe_run() {
	local DEBUG_COLOR="\033[0;32m"
	local RESET="\033[0m"
	echo -e "${DEBUG_COLOR}>> $@""${RESET}"
	"$@"
}

if test $(whoami) != "root"; then
	echo "Must be run as root"
	exit 1
fi

if test $(tidevice list -1 | wc -l) != 1; then
	tidevice list
	echo "-------------"
	echo "ERROR: should connect one device"
	exit 1
fi

UDID=$(tidevice list -1)
tidevice version
echo "UDID: ${UDID:?}"

# 保存设备配对公钥
tidevice savesslfile

# 需要host证书提供给client，host私钥以解密client数据

PEMFILE=ssl/${UDID}_all.pem
if ! test -f $PEMFILE; then
	echo "Pemfile: $PEMFILE not exists"
	exit 1
fi

function recover() {
	echo "Recover environment"
	# https://github.com/alibaba/taobao-iphone-device/commit/bb0c56eb05bf10fbd48c3f9dd0f811d3e7192306
	# 当plistdump-tcp-proxy.py异常结束时，socat会继续运行导致端口占用，所以这里必须kill掉
	# kill %%
	safe_run mv ${BACKUP_SOCKET} ${SOCKET}
}

safe_run mv ${SOCKET} ${BACKUP_SOCKET}
trap recover EXIT

# 启用 tcp redirect 后可以用 https://github.com/douniwan5788/usbmuxd_debug.git 在wireshark中抓包分析
# 注意 SSLContext.keylog_filename 支持需要使用 openssl 1.1.1 的 python 3.8 及以上版本, Mac自带的 python3.8 使用 LibreSSL 所以不支持.
# 可以使用以下方法查看
# >>> import ssl; ssl.OPENSSL_VERSION
# sudo SSLKEYLOGFILE=./tlskeys.log ./run-usbmuxd-proxy.sh --ssl -t 9876
if [ x"$REDIRECT_PORT" != x"" ]; then
	# Setup pipe over TCP that we can tap into
	safe_run_bg socat -t100 "TCP-LISTEN:${REDIRECT_PORT},bind=127.0.0.1,reuseaddr,fork" "UNIX-CONNECT:${BACKUP_SOCKET}"
	echo "SSLKEYLOGFILE: $SSLKEYLOGFILE"
	export SSLKEYLOGFILE
fi

# sudo socat -t100 -v UNIX-LISTEN:${SOCKET},mode=777,reuseaddr,fork UNIX-CONNECT:${SOCKET}.tidevice_orig
python3 "$CURDIR/plistdump-tcp-proxy.py" -L ${SOCKET} -F ${FORWARD_SOCKET} ${SSL} \
	--pemfile ${PEMFILE} "$@"
