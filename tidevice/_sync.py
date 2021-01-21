# codeskyblue 2020/06/03
#

import contextlib
import datetime
import io
import logging
import os
import re
import struct
import typing
from collections import namedtuple
from types import SimpleNamespace
from typing import Iterator, List, Union

from . import struct2 as ct
from ._proto import *
from ._utils import pathjoin
from ._safe_socket import PlistSocket
from .exceptions import MuxError

# 00000000: 43 46 41 36 4C 50 41 41  84 00 00 00 00 00 00 00  magic(CFA6LPAA), length(0x84)
# 00000010: 28 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00  unknown(0x28), tag(0x0)
# 00000020: 02 00 00 00 00 00 00 00                           operation(0x02)
#
# Ref: https://github.com/anonymous5l/iConsole/blob/master/services/afc.go


FHeader = ct.Struct("FHeader",
    ct.Field("magic", b"CFA6LPAA", format="8s"),
    ct.U64("length"),
    ct.U64("this_len"),
    ct.U64("tag", 0),
    ct.U64("operation")) # yapf: disable


logger = logging.getLogger(PROGRAM_NAME)


class Sync(PlistSocket):
    def prepare(self):
        self.__tag = -1

    def _next_tag(self):
        self.__tag += 1
        return self.__tag

    def _send(self, op: AFC, data: bytes, payload: bytes = b''):
        total_len = FHeader.size + len(data) + len(payload)
        this_len = FHeader.size + len(data)
        fheader = FHeader.build(
            length=total_len,
            tag=self._next_tag(),
            this_len=this_len,
            operation=op.value,
        )
        self.sendall(fheader + data + payload)

    def _recv(self):
        buf = self.recvall(FHeader.size)
        fheader = FHeader.parse(buf)
        assert fheader.magic == AFC_MAGIC, fheader.magic
        assert fheader.length >= FHeader.size

        body_size = fheader.length - FHeader.size
        buf = self.recvall(body_size)
        data = buf[:fheader.this_len - FHeader.size]
        payload = buf[fheader.this_len - FHeader.size:]

        status = AFCStatus.SUCCESS
        if fheader.operation == AFC.OP_STATUS:
            (status, ) = struct.unpack("<Q", data)
        elif fheader.operation not in [
                AFC.OP_DATA, AFC.OP_FILE_CLOSE, AFC.OP_FILE_OPEN_RES
        ]:
            logger.info("Unknown FHeader operation: %s",
                        AFC(fheader.operation))
        return namedtuple("AFCPacket",
                          ['status', 'data', 'payload'])(AFCStatus(status),
                                                         data, payload)

    def _request(self, op: AFC, data: bytes, payload: bytes = b''):
        self._send(op, data, payload)
        return self._recv()

    def listdir(self, dpath: str):
        self._send(AFC.OP_READ_DIR, dpath.encode('utf-8'))
        pkg = self._recv()
        fnames = []
        for v in pkg.payload.rstrip(b'\x00').split(b'\x00'):
            fname = v.decode('utf-8')
            if fname in ('.', '..'):
                continue
            fnames.append(fname)
        return fnames

    def _pad00(self, filename: str):
        return filename.encode('utf-8') + b'\x00'

    def mkdir(self, dpath: str):
        pkg = self._request(AFC.OP_MAKE_DIR, dpath.encode('utf-8'))
        return pkg.status

    def rmdir(self, dpath: str):
        """
        This function is semantically identical to remove
        """
        return self.remove(dpath)

    def remove(self, dpath: str):
        """
        Remove can also remove empty directory
        """
        pkg = self._request(AFC.OP_REMOVE_PATH, self._pad00(dpath))
        return pkg.status

    def exists(self, path: str):
        try:
            self.stat(path)
            return True
        except MuxError:
            return False

    def rename(self, src, dst):
        pkg = self._request(AFC.OP_RENAME_PATH,
                            self._pad00(src) + self._pad00(dst))
        return pkg.status

    def stat(self, fpath: str, with_error: bool = False):
        """
        Returns:
            if with_error False:
                SimpleNamespace(is_link, is_dir, st_size, st_mtime, st_ctime, st_ifmt)
            else:
                return_value, error(None or AFCStatus)

        Raw return:
            {'st_size': '96',
            'st_blocks': '0',
            'st_nlink': '3',
            'st_ifmt': 'S_IFDIR',
            'st_mtime': '1591588092361862409',
            'st_birthtime': '1591588092361695702'}
        """
        pkg = self._request(AFC.OP_GET_FILE_INFO, fpath.encode('utf-8'))
        if pkg.status != AFCStatus.SUCCESS:
            if with_error:
                return None, AFCStatus(pkg.status)
            raise MuxError("stat {} - {!s}".format(fpath,
                                                   AFCStatus(pkg.status)))

        items = pkg.payload.rstrip(b"\x00").split(b'\x00')
        assert len(items) % 2 == 0

        result = {}
        keys = ['st_size']
        for i in range(len(items) // 2):
            key = items[i * 2].decode('utf-8')
            val = items[i * 2 + 1].decode('utf-8')
            result[key] = val

        for key in ('st_size', 'st_blocks', 'st_nlink'):
            if key in result:
                result[key] = int(result[key])
        result['is_dir'] = result['st_ifmt'] == 'S_IFDIR'
        result['is_link'] = result['st_ifmt'] == 'S_IFLNK'
        result['st_mtime'] = datetime.datetime.fromtimestamp(
            int(result['st_mtime']) / 1e9)
        result['st_ctime'] = datetime.datetime.fromtimestamp(
            int(result.pop('st_birthtime')) / 1e9)
        simple_ret = SimpleNamespace(**result)
        if with_error:
            return simple_ret, None
        return simple_ret

    def rmtree(self, dpath: str) -> list:
        """ remove recursive """
        info = self.stat(dpath)
        if info.is_dir:
            rmfiles = []
            for fname in self.listdir(dpath):
                fpath = dpath.rstrip("/") + "/" + fname
                files = self.rmtree(fpath)
                rmfiles.extend(files)
            rmfiles.append(dpath + "/")
            self.rmdir(dpath)
            return rmfiles
        else:
            self.remove(dpath)
            return [dpath]

    def treeview(self, dpath: str, depth=2, _prefix='', _last=False, _depth=0):
        """
        depth: -1 means ignore depth
        """
        if depth != -1 and _depth > depth:
            return
        info, err = self.stat(dpath, with_error=True)
        if err:
            print("{} [ERR] {!r} {!s}".format(_prefix, os.path.basename(dpath),
                                              err))
        elif info.is_dir:
            print(_prefix, "-", os.path.basename(dpath) + "/")
            filenames = self.listdir(dpath)
            for fname in filenames:
                if fname == "":  # strange name, but exists
                    continue
                _last = (fname == filenames[-1])
                fpath = dpath.rstrip("/") + "/" + fname
                self.treeview(fpath,
                              _prefix=_prefix + "   ",
                              depth=depth,
                              _last=_last,
                              _depth=_depth + 1)
        else:
            print(_prefix, "-", os.path.basename(dpath))

    def walk(
        self,
        top: str,
        followlinks: bool = False
    ) -> typing.Iterator[typing.Union[str, List, List]]:
        """
        Same as os.walk but implemented for AFC
        """
        if not self.stat(top).is_dir:
            return
        allfiles = self.listdir(top)
        dirs, files = [], []
        for fname in allfiles:
            if fname == "":  # ignore invalid empty name
                continue

            path = pathjoin(top, fname)
            info = self.stat(path)
            if info.is_dir:
                if info.is_link:
                    if followlinks:
                        dirs.append(fname)
                    continue
                else:
                    dirs.append(fname)
            else:
                files.append(fname)
        yield top, dirs, files
        for dname in dirs:
            root = pathjoin(top, dname)
            yield from self.walk(root, followlinks=followlinks)

    def _file_open(self, path, open_mode=AFC.O_RDONLY) -> int:
        """
        Return file handle fd
        """
        payload = struct.pack("<Q", open_mode)
        payload += self._pad00(path)
        pkg = self._request(AFC.OP_FILE_OPEN, payload)
        fd = struct.unpack("<Q", pkg.data)[0]
        assert fd, "file descriptor should not be zero"
        return fd

    def _file_close(self, fd: int):
        pkg = self._request(AFC.OP_FILE_CLOSE, struct.pack("<Q", fd))
        return pkg.status

    @contextlib.contextmanager
    def _context_open(self, path, open_mode):
        h = self._file_open(path, open_mode)
        yield h
        self._file_close(h)
        # try:
        # finally:
        #     self._file_close(h)

    def iter_content(self, path: str) -> Iterator[bytes]:
        info = self.stat(path)
        if info.is_dir:
            raise MuxError("{} is a directory", path)
        if info.is_link:
            path = info['LinkTarget']

        with self._context_open(path, AFC.O_RDONLY) as fd:
            left_size = info.st_size
            max_read_size = 1 << 16
            while left_size > 0:
                pkg = self._request(AFC.OP_READ,
                                    struct.pack("<QQ", fd, max_read_size))
                if pkg.status != AFCStatus.SUCCESS:
                    raise MuxError("read {} error, status {}".format(
                        path, pkg.status))
                left_size -= len(pkg.payload)
                yield pkg.payload

    def pull_content(self, path: str) -> bytearray:
        buf = bytearray()
        for chunk in self.iter_content(path):
            buf.extend(chunk)
        return buf

    def push_content(self, path: str, data: Union[typing.IO, bytes,
                                                  bytearray]):
        with self._context_open(path, AFC.O_WR) as fd:
            chunk_size = 1 << 15

            if isinstance(data, io.IOBase):
                buf = data
            else:
                buf = io.BytesIO(data)

            while True:
                chunk = buf.read(chunk_size)
                if chunk == b'':
                    break
                pkg = self._request(AFC.OP_WRITE, struct.pack("<Q", fd), chunk)
                if pkg.status != 0:
                    raise MuxError("write error: {!s}".format(pkg.status))
