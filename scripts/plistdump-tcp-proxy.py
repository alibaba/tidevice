#!/usr/bin/python
# This is a simple port-forward / proxy, written using only the default python
# library. If you want to make a suggestion or fix something you can contact-me
# at voorloop_at_gmail.com
# Distributed over IDC(I Don't Care) license

# Python3
# Modified: 2020/05/15 (Fri) shengxiang.ssx

import argparse
import datetime
import os
import plistlib
import pprint
import re
import select
import socket
import ssl
import string
import struct
import sys
import threading
import time
import traceback

import hexdump
from logzero import logger

# Changing the buffer_size and delay, you can improve the speed and bandwidth.
# But when buffer get to high or delay go too down, you can broke things
buffer_size = 40960
delay = 0.0001


_package_index = [0]

def next_package_index() -> int:
    _package_index[0] += 1
    return _package_index[0]


def create_socket(addr) -> socket.socket:
    if isinstance(addr, (tuple, list)):
        return socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    elif isinstance(addr, str):
        return socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)


def is_ssl_data(data: bytes) -> bool:
    """ FIXME(ssx): better to change to EnableSSLSession """
    return len(data) >= 8 and \
        data[:3] == b'\x16\x03\x01' and data[5:6] == b'\x01'


def recvall(sock: socket.socket, n: int) -> bytearray:
    buf = bytearray()
    while n > len(buf):
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ValueError("socket not recv all bytes")
        buf.extend(chunk)
    return buf


class TheServer:
    input_list = []
    channel = {}
    socket_tags = {}

    def __init__(self,
                 listen_addr: str,
                 forward_to: str,
                 parse_ssl: bool = False,
                 pemfile=None):
        print("Listening on", listen_addr, "forward to", forward_to)
        self.server = create_socket(listen_addr)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind(listen_addr)
        if isinstance(listen_addr, str):
            os.chmod(listen_addr, 0o777)
        self.server.listen(200)

        self.ssl_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.ssl_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.ssl_server.bind(('localhost', 10443))
        self.ssl_server.listen(200)

        self.forward_to = forward_to
        self.parse_ssl = parse_ssl
        self.pemfile = pemfile

        self.__tempsocks = {}  # Store SSLSocket
        self.__tag = 0
        self._data_directory = "usbmuxd-dumpdata/" + time.strftime(
            "%Y%m%d-%H-%M-%S")

    def main_loop(self):
        self.input_list.append(self.server)
        self.input_list.append(self.ssl_server)

        while True:
            time.sleep(delay)
            timeout = .5
            inputready, outputready, exceptready = select.select(self.input_list, [], [], timeout)
            for self.s in inputready:
                if self.s == self.server:
                    self.on_accept()
                    break

                if self.s == self.ssl_server:
                    self.on_ssl_accept()
                    break

                try:
                    self.data = self.s.recv(buffer_size)
                    if len(self.data) == 0:
                        self.on_close()
                        break
                    self.on_recv()
                except ssl.SSLError as e:
                    logger.warning("SSLError: tag: %d, %s",
                                   self.socket_tags[self.s], e)

                    self.on_close()
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    #logger.warning("Unknown error: %s", e)

    def gen_tag(self) -> int:  # return uniq int
        self.__tag += 1
        return self.__tag

    def pipe_socket(self, clientsock, serversock, tag=None):
        assert clientsock not in self.channel, (clientsock, "already piped")
        self.input_list.append(clientsock)
        self.input_list.append(serversock)
        self.channel[clientsock] = serversock
        self.channel[serversock] = clientsock
        if tag:
            self.socket_tags[serversock] = -tag
            self.socket_tags[clientsock] = tag

    def unpipe_socket(self, clientsock) -> int:
        """
        return socket tag
        """
        serversock = self.channel[clientsock]
        del self.channel[clientsock]
        del self.channel[serversock]
        self.remove_from_list(self.input_list, clientsock)
        self.remove_from_list(self.input_list, serversock)
        self.socket_tags.pop(serversock, None)  # socket_tags
        return self.socket_tags.pop(clientsock, None)

    def remove_from_list(self, _list, value):
        try:
            _list.remove(value)
        except ValueError:
            pass

    def on_accept(self):
        forward = create_socket(self.forward_to)
        forward.connect(self.forward_to)

        clientsock, clientaddr = self.server.accept()
        if forward:
            print('[proxy]', clientaddr, "has connected")
            self.pipe_socket(clientsock, forward, self.gen_tag())
        else:
            print("[proxy] Can't establish connection with remote server.", )
            print("[proxy] Closing connection with client side", clientaddr)
            clientsock.close()

    def on_ssl_accept(self):
        sock, addr = self.ssl_server.accept()

        header = recvall(sock, 4)  #sock.recv(4)
        (tag, ) = struct.unpack("I", header)
        logger.info("on ssl accept: %s, tag: %d", addr, tag)
        ssl_serversock = self.__tempsocks[tag]

        def wait_ssl_socket():
            ssock = ssl.wrap_socket(sock,
                                    keyfile=self.pemfile,
                                    certfile=self.pemfile,
                                    server_side=True)
            self.pipe_socket(ssock, ssl_serversock, tag)

        th = threading.Thread(target=wait_ssl_socket)
        th.daemon = True
        th.start()

    def pretty_format_data(self, data: bytes) -> str:
        try:
            return '\n'.join(list(self._iter_pretty_format_data(data)))
        except:
            print(list(self._iter_pretty_format_data(data)))
            raise

    def _iter_pretty_format_data(self, data: bytes):
        if b'<plist version=' in data:
            lindex = data.find(b'<?xml version=')
            rindex = data.find(b'</plist>') + len('</plist>')
            plistdata = data[lindex:rindex]

            yield hexdump.hexdump(data[:lindex], "return")
            yield "## Plist-XML"
            try:
                pdata = plistlib.loads(plistdata)
                if 'PairRecordData' in pdata:
                    yield "... PairRecordData ..."
                else:
                    yield pprint.pformat(pdata)
                yield hexdump.hexdump(data[rindex:], "return")
            except:
                yield hexdump.hexdump(data, "return")
        elif b'bplist00' in data:
            # parse bplist data
            from tinstruments import bplist
            buf = data
            while True:
                lindex = buf.find(b'bplist00')
                #print("bplist00", hex(lindex))
                if lindex == -1:
                    break
                m = re.search(b"\x00{6}[\x02\x01]{2}.{24}", buf)
                if not m:
                    break
                rindex = m.end()

                yield hexdump.hexdump(buf[:lindex], "return")
                try:
                    yield "## NSKeyedArchiver-BINARY: [{}, {}]".format(hex(lindex), hex(rindex))
                    pdata = bplist.objc_decode(buf[lindex:rindex])
                    yield pprint.pformat(pdata)
                except bplist.InvalidNSKeyedArchiverFormat:
                    yield "## Plist-BINARY: [{}, {}]".format(hex(lindex), hex(rindex))
                    pdata = bplist.loads(buf[lindex:rindex])
                    yield pprint.pformat(pdata)
                except Exception as e:
                    yield "## Parse plist-BINARY error: [{}, {}]".format(hex(lindex), hex(rindex))
                    yield traceback.format_exc()
                    # BPlistdata failed string indices must be integers
                    yield "load binary plistdata failed: {}".format(e)
                    yield hexdump.hexdump(buf[lindex:rindex], "return")
                finally:
                    buf = buf[rindex:]
            yield hexdump.hexdump(buf, "return")
        else:  # just call hexdump
            yield f"## RAW length={len(data)}"
            max_length = 512
            if len(data) > max_length // 2:
                yield hexdump.hexdump(data[:max_length // 2], "return")
                yield "........ " * 5
                yield hexdump.hexdump(data[-max_length // 2:], "return")
            else:
                yield hexdump.hexdump(data, "return")
        # else:
        #     try:
        #         pdata = data.decode('utf-8')
        #         print(pdata)
        #     except UnicodeDecodeError:
        #         hexdump.hexdump(data)

    def dump_data(self, data):
        if self.s not in self.socket_tags:
            return

        tag = self.socket_tags[self.s]
        direction = ">"
        if tag < 0:
            direction = "<"
        index = abs(tag)

        print(f' {index} '.center(50, direction))
        if isinstance(self.s, ssl.SSLSocket):  # secure tunnel
            print('\33[32m', end="")
        print(f"Length={len(data)} 0x{len(data):02X}")
        print("Time:", datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3])

        # TODO
        #if tag < 0:
        #    print("Skip show receving data")
        #    return
        if True:
            os.makedirs(self._data_directory, 0o755, exist_ok=True)
            fpath = os.path.join(self._data_directory, f"{index}.txt")
            with open(fpath, "a") as f:
                f.write(f'# INDEX: {index} {direction*5}\n')
                f.write(f"Size: oct:{len(data)} hex:0x{len(data):02X}\n")
                f.write(f"Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}\n")
                f.write(f"Package index: {next_package_index()}\n")
                f.write(self.pretty_format_data(data) + "\n")
                f.write('\n\n')

        if True:
            for line in self._iter_pretty_format_data(data):
                print(line)

        #else:
        #    try:
        #        pdata = data.decode('utf-8')
        #        print(pdata)
        #    except UnicodeDecodeError:
        #        hexdump.hexdump(data)

        if isinstance(self.s, ssl.SSLSocket):  # secure tunnel
            print('\33[0m', end="")

    def man_in_middle_ssl(self, clientsock, ssl_hello_data: bytes):
        serversock = self.channel[clientsock]
        tag = self.unpipe_socket(clientsock)

        ssl_serversock = ssl.wrap_socket(
            serversock,
            keyfile=self.pemfile,  # iPhoneSE
            certfile=self.pemfile)
        print("serversock secure ready, tag: {}".format(tag))

        self.__tempsocks[tag] = ssl_serversock

        mim_clientsock = socket.create_connection(('localhost', 10443))
        mim_clientsock.sendall(struct.pack("I", tag))

        hexdump.hexdump(ssl_hello_data[:1024])
        mim_clientsock.sendall(ssl_hello_data)
        self.pipe_socket(clientsock, mim_clientsock)

    def on_recv(self):
        # here we can parse and/or modify the data before send forward
        data = self.data

        # Check SSL ClientHello message
        if self.parse_ssl and is_ssl_data(data):
            logger.info("Mock SSL-Server")
            clientsock = self.s
            self.man_in_middle_ssl(clientsock, data)
            return

        # if b'PairRecordData' in data and b'DeviceCertificate' in data:
        #     print(".... PairRecordData ....")
        # else:
        self.dump_data(data)

        try:
            self.channel[self.s].send(data)
        except BrokenPipeError:
            print("channel broken pipe")

    def on_close(self):
        print('[proxy]', self.socket_tags.get(self.s), "has disconnected")
        # print('[proxy]', self.channel[self.s].getpeername(), "has disconnected, too")

        #remove objects from input_list

        # self.input_list.remove(self.s)
        # self.input_list.remove(self.channel[self.s])

        out = self.channel[self.s]
        # close the connection with client
        self.channel[out].close()  # equivalent to do self.s.close()
        # close the connection with remote server
        self.channel[self.s].close()
        # delete both objects from channel dict

        self.unpipe_socket(self.s)
        # del self.channel[out]
        # del self.channel[self.s]


def _parse_addr(addr: str):
    if ':' in addr:
        host, port = addr.split(":", 1)
        return (host, int(port))
    return addr


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-L",
                        "--listen-addr",
                        default="/var/run/usbmuxd",
                        help="listen address, eg :5555 or /tmp/listen.sock")
    parser.add_argument(
        "-F",
        "--forward-to",
        default="/var/run/usbmuxx",
        help="forward to, eg: localhost:5037 or /var/lib/usbmuxd")
    parser.add_argument("-S",
                        "--ssl",
                        action="store_true",
                        help="parse ssl data")
    parser.add_argument("--pemfile", help="ssl pemfile")
    args = parser.parse_args()
    #print(args)

    listen_addr = _parse_addr(args.listen_addr)
    forward_to = _parse_addr(args.forward_to)

    server = TheServer(listen_addr,
                       forward_to,
                       parse_ssl=args.ssl,
                       pemfile=args.pemfile)
    try:
        server.main_loop()
    except KeyboardInterrupt:
        print("Ctrl C - Stopping server")
        sys.exit(1)
    finally:
        if isinstance(listen_addr, str):
            import os
            os.unlink(listen_addr)


if __name__ == '__main__':
    main()
