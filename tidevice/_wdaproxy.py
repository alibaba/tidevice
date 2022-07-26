#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Created on Wed Feb 03 2021 10:22:15 by codeskyblue
"""

import abc
import functools
import logging
import subprocess
import sys
import threading
import time
import typing
import traceback

import logzero
import requests

from . import requests_usbmux
from ._device import Device
from ._proto import UsbmuxReplyCode
from .exceptions import MuxReplyError


class WDAService:
    _DEFAULT_TIMEOUT = 90 # http request timeout

    def __init__(self, d: Device, bundle_id: str = "com.*.xctrunner", env: dict={}):
        self._d = d
        self._bundle_id = bundle_id
        self._service = ThreadService(self._keep_wda_running)
        self._env = env

    def set_check_interval(self, interval: float):
        self._service.set_arguments(interval)

    @property
    def udid(self) -> str:
        return self._d.udid

    @property
    @functools.lru_cache(None)
    def logger(self) -> logging.Logger:
        log_format = f'%(color)s[%(levelname)1.1s %(asctime)s %(module)s:%(lineno)d] [{self.udid}]%(end_color)s %(message)s'
        formatter = logzero.LogFormatter(fmt=log_format)
        return logzero.setup_logger(formatter=formatter)

    def _is_alive(self) -> bool:
        try:
            with requests_usbmux.Session() as session:
                resp = session.get(requests_usbmux.DEFAULT_SCHEME +
                                   f"{self.udid}:8100/HEALTH",
                                   timeout=self._DEFAULT_TIMEOUT)
                if resp.status_code != 200:
                    return False
                return resp.text.strip() == "I-AM-ALIVE"
        except requests.RequestException as e:
            self.logger.debug("request error: %s", e)
            return False
        except MuxReplyError as e:
            if e.reply_code != UsbmuxReplyCode.ConnectionRefused:
                self.logger.warning("Unknown MuxReplyError: %s", e)
            return False
        except Exception as e:
            self.logger.warning("Unknown exception: %s", e)
            return False

    def _wait_ready(self,
                    proc,
                    stop_event: threading.Event,
                    timeout: float = 60.0) -> bool:
        deadline = time.time() + timeout
        while not stop_event.is_set() and time.time() < deadline:
            alive = self._is_alive()
            if alive:
                return True

            if proc.poll() is not None:  # program quit
                return False
            stop_event.wait(1.0)
        return False

    def _wait_until_quit(self,
                         proc: subprocess.Popen,
                         stop_event: threading.Event,
                         check_interval: float = 30.0) -> float:
        """
        return running seconds
        """
        start = time.time()
        elapsed = lambda: time.time() - start

        while not stop_event.is_set():
            if proc.poll() is not None:
                break

            # stop check when check_interval is set to 0
            if check_interval < 0.00001:
                time.sleep(.1)
                continue

            if not self._is_alive():
                # maybe stuck by other request
                # check again after 10s
                self.logger.debug("WDA is not response in %d second, check again after 1s", self._DEFAULT_TIMEOUT)
                if stop_event.wait(1):
                    break
                if not self._is_alive():
                    self.logger.info("WDA confirmed not running")
                    break
                else:
                    self.logger.debug("WDA is back alive")

            end_check_time = time.time() + check_interval
            while time.time() < end_check_time:
                if proc.poll() is not None:
                    break
                time.sleep(.1)

        self.logger.info("WDA keeper stopped")
        return elapsed()

    def _keep_wda_running(self, stop_event: threading.Event, check_interval: float = 60.0):
        """
        Keep wda running, launch when quit
        """
        if check_interval > .1:
            self.logger.info("WDA check every %.1f seconds", check_interval)
        tries: int = 0
        crash_times: int = 0 # detect unrecoverable launch

        d = Device(self.udid)
        while not stop_event.is_set():
            self.logger.debug("launch WDA")
            tries += 1
            
            cmds = [
                sys.executable, '-m', 'tidevice',
                '-u', self.udid,
                'xctest',
                '--bundle_id', self._bundle_id,
                #'-e', 'MJPEG_SERVER_PORT:8103'
            ]
            
            for key in self._env:
                cmds.append('-e')
                val = self._env[key]
                cmds.append( key + ':' + val )
            
            try:
                proc = subprocess.Popen(cmds)
                if not self._wait_ready(proc, stop_event):
                    self.logger.error("wda started failed")
                    crash_times += 1
                    if crash_times >= 5:
                        break
                    continue
                elapsed = self._wait_until_quit(proc, stop_event, check_interval=check_interval)
                crash_times = 0
                
                self.logger.info("WDA stopped for the %dst time, running %.1f minutes", tries, elapsed / 60)
            finally:
                proc.terminate()
            
            if not d.is_connected():
                self.logger.warning("device offline")
                break

    def start(self):
        return self._service.start()

    def stop(self):
        return self._service.stop()


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
        self._kwargs = {}

    def set_arguments(self, *args, **kwargs):
        self._args = args
        self._kwargs = kwargs

    def _wrapped_func(self):
        try:
            args = [self._stop_event] + list(self._args)
            return self._func(*args, **self._kwargs)
        except:
            traceback.print_exc()
        finally:
            self.set_running(False)

    def _start(self):
        self._stop_event.clear()

        th = threading.Thread(target=self._wrapped_func, name="wda")
        th.daemon = True
        th.start()

    def _stop(self):
        """
        notifition thread to stop through stop_event
        """
        self._stop_event.set()
