# coding: utf-8
# author: codeskyblue
# created: 2020/09

import abc
import contextlib
import io
import logging
import os
import socket
import subprocess
import sys
import threading
import time
import typing

from ._proto import PROGRAM_NAME

logger = logging.getLogger(PROGRAM_NAME)
is_atty = getattr(sys.stdout, 'isatty', lambda: False)()


def get_app_dir(*paths) -> str:
    home = os.path.expanduser("~")
    appdir = os.path.join(home, "." + PROGRAM_NAME)
    if paths:
        appdir = os.path.join(appdir, *paths)
    os.makedirs(appdir, exist_ok=True)
    return appdir


# def get_app_file(*paths) -> str:
#     assert paths, "must has at least one argument"

#     basedir = get_app_dir()
#     fpath = os.path.join(basedir, *paths)
#     if create_dir:
#         os.makedirs(os.path.dirname(fpath), exist_ok=True)
#     return fpath


def get_binary_by_name(name: str) -> str:
    pyfilepath = os.path.abspath(__file__)
    abspath = os.path.join(os.path.dirname(pyfilepath), "binaries",
                           sys.platform, name)
    if not os.path.isfile(abspath):
        raise RuntimeError("Binary file {} not exist".format(name))
    return abspath


def get_current_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip


def pathjoin(path: str, *paths) -> str:
    """ join path with unix file sep: / """
    parts = [path.rstrip("/\\")]
    for p in paths:
        parts.append(p.strip("/\\"))
    return '/'.join(parts)


class ProgressReader(io.IOBase):
    def __init__(self, reader: typing.IO, total_size: int):
        self._reader = reader
        self._total_size = total_size
        self._begin = time.time()
        self._copied = 0
        self._stdout_writelen = 0

    def read(self, size: int) -> bytes:
        chunk = self._reader.read(size)
        if is_atty:
            self._clear()
            self._update(len(chunk))
        return chunk

    def format_size(self, nbytes: int, format="{:.1f}"):
        assert nbytes >= 0
        units = [("MB", 1 << 20), ("KB", 1 << 10), ("Bytes", 1)]
        for unit_name, min_size in units:
            if nbytes >= min_size:
                return "{:.1f} {}".format(nbytes / min_size, unit_name)
        return "0 Bytes"

    def format_time(self, nseconds: int):
        if nseconds < 60:
            return "{:.0f}s".format(nseconds)
        return "{:.0f}m{:.0f}s".format(nseconds // 60, nseconds % 60)

    def _update(self, chunk_size: int):
        """ 5.1 MB/s 100%"""
        self._copied += chunk_size
        bytes_per_second = self._copied / max((time.time() - self._begin), 0.01)
        speed = self.format_size(bytes_per_second) + "/s"
        percent = "{:.1f}%".format(100 * self._copied / self._total_size)
        left_seconds = (self._total_size - self._copied) / max(
            1, bytes_per_second)
        status_message = f"{speed} {percent} TimeLeft: {self.format_time(left_seconds)}"
        sys.stdout.write(status_message)
        sys.stdout.flush()
        self._stdout_writelen = len(status_message)

    def _clear(self):
        sys.stdout.write("\b" * self._stdout_writelen)
        sys.stdout.write(" " * self._stdout_writelen)
        sys.stdout.write("\b" * self._stdout_writelen)
        sys.stdout.flush()

    def finish(self):
        self._clear()
        bytes_per_second = self._copied / (time.time() - self._begin)
        speed = self.format_size(bytes_per_second) + "/s"
        duration = self.format_time(time.time() - self._begin)
        sys.stdout.write("[{} {}] ".format(speed, duration))
        sys.stdout.flush()


class BaseService(metaclass=abc.ABCMeta):
    def __init__(self):
        self._stopped = threading.Event()
        self._stopped.set()

    @property
    def running(self) -> bool:
        return not self._stopped.is_set()
    
    def set_running(self, running: bool):
        if running:
            self._stopped.clear()
        else:
            self._stopped.set()

    def start(self):
        if self.running:
            raise RuntimeError("already running")
        self.set_running(True)
        self._start()

    def stop(self):
        if not self.running:
            return False
        self._stop()
    
    def wait(self, timeout: float = None) -> bool:
        return self._stopped.wait(timeout)

    @abc.abstractmethod
    def _start(self):
        raise NotImplementedError()

    @abc.abstractmethod
    def _stop(self):
        raise NotImplementedError()


class ThreadService(BaseService):
    def __init__(self, thread_func: typing.Callable):
        """
        Args:
            thread_func: first argument must be stop_event(threading.Event) passed by this class
        
        Example of thread_func:
            def tfoo(stop_event: threading.Event):
                while not stop_event.is_set():
                    pass
        """
        super().__init__()
        self._func = thread_func
        self._stop_event = threading.Event()
        self._args = []

    def set_args(self, args: list):
        self._args = args

    def _wrapped_func(self):
        try:
            args = [self._stop_event] + self._args
            return self._func(*args)
        finally:
            self.set_running(False)

    def _start(self):
        self._stop_event.clear()

        th = threading.Thread(target=self._wrapped_func)
        th.daemon = True
        th.start()

    def _stop(self):
        """
        notifition thread to stop through stop_event
        """
        self._stop_event.set()


@contextlib.contextmanager
def exec_command(cmds: typing.List[str], logfile):
    """
    Args:
        cmds: list of program and args
        logfile: output command output to this file
    """
    with open(logfile, 'ab') as fout:
        p = subprocess.Popen(cmds, stdout=fout, stderr=subprocess.STDOUT)
        try:
            yield p
        finally:
            p.terminate()
            try:
                p.wait(3)
            except subprocess.TimeoutExpired:
                p.kill()


@contextlib.contextmanager
def set_socket_timeout(conn: typing.Union[typing.Callable[..., socket.socket], socket.socket], value: float):
    """Set conn.timeout to value
    Save previous value, yield, and then restore the previous value
    If 'value' is None, do nothing
    """
    def get_conn() -> socket.socket:
        return conn() if callable(conn) else conn    
    
    old_value = get_conn().timeout
    get_conn().settimeout(value)
    try:
        yield
    finally:
        try:
            get_conn().settimeout(old_value)
        except:
            pass