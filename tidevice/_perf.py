#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Created on Tue May 11 2021 16:30:17 by codeskyblue
"""

import enum
import io
import threading
import time
import typing
import uuid
from collections import defaultdict, namedtuple
from typing import Any, Iterator, Optional, Tuple, Union
import weakref

from ._device import BaseDevice
from ._proto import *


class DataType(str, enum.Enum):
    SCREENSHOT = "screenshot"
    CPU = "cpu"
    MEMORY = "memory"
    NETWORK = "network"  # 流量
    FPS = "fps"
    PAGE = "page"
    GPU = "gpu"

CallbackType = typing.Callable[[DataType, dict], None]

class RunningProcess:
    """ acturally there is a better way to monitor process pid """
    PID_UPDATE_DURATION = 5.0

    def __init__(self, d: BaseDevice, bundle_id: str):
        self._ins = d.connect_instruments()
        self._bundle_id = bundle_id
        self._app_infos = list(d.installation.iter_installed(app_type=None))
        self._next_update_time = 0.0
        self._last_pid = None
        self._lock = threading.Lock()
        weakref.finalize(self, self._ins.close)

    @property
    def bundle_id(self) -> str:
        return self._bundle_id

    def get_pid(self) -> Union[int, None]:
        """ return pid """
        with self._lock:
            if time.time() < self._next_update_time:
                return self._last_pid

            if self._last_pid and self._ins.is_running_pid(self._last_pid):
                self._next_update_time = time.time() + self.PID_UPDATE_DURATION
                return self._last_pid

            for pinfo in self._ins.app_process_list(self._app_infos):
                if pinfo['bundle_id'] == self._bundle_id:
                    self._last_pid = pinfo['pid']
                    self._next_update_time = time.time(
                    ) + self.PID_UPDATE_DURATION
                    # print(self._bundle_id, "pid:", self._last_pid)
                    return self._last_pid


class WaitGroup(object):
    """WaitGroup is like Go sync.WaitGroup.

    Without all the useful corner cases.
    """
    def __init__(self):
        self.count = 0
        self.cv = threading.Condition()

    def add(self, n):
        self.cv.acquire()
        self.count += n
        self.cv.release()

    def done(self):
        self.cv.acquire()
        self.count -= 1
        if self.count == 0:
            self.cv.notify_all()
        self.cv.release()

    # FIXME(ssx): here should quit when timeout, but maybe not
    def wait(self, timeout: Optional[float] = None):
        self.cv.acquire()
        while self.count > 0:
            self.cv.wait(timeout=timeout)
        self.cv.release()


def gen_stimestamp(seconds: Optional[float] = None) -> str:
    """ 生成专门用于tmq-service.taobao.org平台使用的timestampString """
    if seconds is None:
        seconds = time.time()
    return int(seconds * 1000)


def iter_fps(d: BaseDevice) -> Iterator[Any]:
    with d.connect_instruments() as ts:
        for data in ts.iter_opengl_data():
            fps = data['CoreAnimationFramesPerSecond'] # fps from GPU
            # print("FPS:", fps)
            yield DataType.FPS, {"fps": fps, "time": time.time(), "value": fps}


def iter_gpu(d: BaseDevice) -> Iterator[Any]:
    with d.connect_instruments() as ts:
        for data in ts.iter_opengl_data():
            device_utilization = data['Device Utilization %']  # Device Utilization
            tiler_utilization = data['Tiler Utilization %'] # Tiler Utilization
            renderer_utilization = data['Renderer Utilization %'] # Renderer Utilization
            yield DataType.GPU, {"device": device_utilization, "renderer": renderer_utilization,
                                "tiler": tiler_utilization, "time": time.time(), "value": device_utilization}


def iter_screenshot(d: BaseDevice) -> Iterator[Tuple[DataType, dict]]:
    for img in d.iter_screenshot():
        _time = time.time()
        img.thumbnail((500, 500))  # 缩小图片已方便保存
        
        # example of convert image to bytes
        # buf = io.BytesIO()
        # img.save(buf, format="JPEG")

        # turn image to URL
        yield DataType.SCREENSHOT, {"time": _time, "value": img}



ProcAttrs = namedtuple("ProcAttrs", SYSMON_PROC_ATTRS)

def _iter_complex_cpu_memory(d: BaseDevice,
                            rp: RunningProcess) -> Iterator[dict]:
    """
    content in iterator

    - {'type': 'system_cpu',
        'sys': -1.0,
        'total': 55.21212121212122,
        'user': -1.0}
    - {'type': 'process',
        'cpu_usage': 2.6393411792622925,
        'mem_anon': 54345728,
        'mem_rss': 130760704,
        'pid': 1344}
    """
    with d.connect_instruments() as ts:
        for info in ts.iter_cpu_memory():
            pid = rp.get_pid()

            if info is None or len(info) != 2:
                continue
            sinfo, pinfolist = info
            if 'CPUCount' not in sinfo:
                sinfo, pinfolist = pinfolist, sinfo

            if 'CPUCount' not in sinfo:
                continue

            cpu_count = sinfo['CPUCount']

            sys_cpu_usage = sinfo['SystemCPUUsage']
            cpu_total_load = sys_cpu_usage['CPU_TotalLoad']
            cpu_user = sys_cpu_usage['CPU_UserLoad']
            cpu_sys = sys_cpu_usage['CPU_SystemLoad']

            if 'Processes' not in pinfolist:
                continue

            # 这里的total_cpu_usage加起来的累计值大概在0.5~5.0之间
            total_cpu_usage = 0.0
            for attrs in pinfolist['Processes'].values():
                pinfo = ProcAttrs(*attrs)
                if isinstance(pinfo.cpuUsage, float):  # maybe NSNull
                    total_cpu_usage += pinfo.cpuUsage

            cpu_usage = 0.0
            attrs = pinfolist['Processes'].get(pid)
            if attrs is None:  # process is not running
                # continue
                # print('process not launched')
                pass
            else:
                assert len(attrs) == len(SYSMON_PROC_ATTRS)
                # print(ProcAttrs, attrs)
                pinfo = ProcAttrs(*attrs)
                cpu_usage = pinfo.cpuUsage
            # next_list_process_time = time.time() + next_timeout
            # cpu_usage, rss, mem_anon, pid = pinfo

            # 很诡异的计算方法，不过也就这种方法计算出来的CPU看起来正常一点
            # 计算后的cpuUsage范围 [0, 100]
            # cpu_total_load /= cpu_count
            # cpu_usage *= cpu_total_load
            # if total_cpu_usage > 0:
            #     cpu_usage /= total_cpu_usage

            # print("cpuUsage: {}, total: {}".format(cpu_usage, total_cpu_usage))
            # print("memory: {} MB".format(pinfo.physFootprint / 1024 / 1024))
            yield dict(
                type="process",
                pid=pid,
                phys_memory=pinfo.physFootprint,  # 物理内存
                phys_memory_string="{:.1f} MiB".format(pinfo.physFootprint / 1024 /
                                                    1024),
                vss=pinfo.memVirtualSize,
                rss=pinfo.memResidentSize,
                anon=pinfo.memAnon,  # 匿名内存? 这个是啥
                cpu_count=cpu_count,
                cpu_usage=cpu_usage,  # 理论上最高 100.0 (这里是除以过cpuCount的)
                sys_cpu_usage=cpu_total_load,
                attr_cpuUsage=pinfo.cpuUsage,
                attr_cpuTotal=cpu_total_load,
                attr_ctxSwitch=pinfo.ctxSwitch,
                attr_intWakeups=pinfo.intWakeups,
                attr_systemInfo=sys_cpu_usage)


def iter_cpu_memory(d: BaseDevice, rp: RunningProcess) -> Iterator[Any]:
    for minfo in _iter_complex_cpu_memory(d, rp):  # d.iter_cpu_mem(bundle_id):
        yield DataType.CPU, {
            "timestamp": gen_stimestamp(),
            "pid": minfo['pid'],
            "value": minfo['cpu_usage'],  # max 100.0?, maybe not
            "sys_value": minfo['sys_cpu_usage'],
            "count": minfo['cpu_count']
        }
        yield DataType.MEMORY, {
            "pid": minfo['pid'],
            "timestamp": gen_stimestamp(),
            "value": minfo['phys_memory'] / 1024 / 1024,  # MB
        }


def set_interval(it: Iterator[Any], interval: float):
    while True:
        start = time.time()
        data = next(it)
        yield data
        wait = max(0, interval - (time.time() - start))
        time.sleep(wait)


def iter_network_flow(d: BaseDevice, rp: RunningProcess) -> Iterator[Any]:
    n = 0
    with d.connect_instruments() as ts:
        for nstat in ts.iter_network():
            # if n < 2:
            #     n += 1
            #     continue
            yield DataType.NETWORK, {
                "timestamp": gen_stimestamp(),
                "downFlow": (nstat['rx.bytes'] or 0) / 1024,
                "upFlow": (nstat['tx.bytes'] or 0) / 1024
            }


def append_data(wg: WaitGroup, stop_event: threading.Event,
                idata: Iterator[Any], callback: CallbackType, filters: list):
    for _type, data in idata:
        assert isinstance(data, dict)
        assert isinstance(_type, DataType)

        if stop_event.is_set():
            wg.done()
            break

        if isinstance(data, dict) and "time" in data:
            stimestamp = gen_stimestamp(data.pop('time'))
            data.update({"timestamp": stimestamp})
        # result[_type].append(data)
        if _type in filters:
            callback(_type, data)
        # print(_type, data)

    stop_event.set()  # 当有一个中断，其他的全部中断，让错误暴露出来


class Performance():
    # PROMPT_TITLE = "tidevice performance"

    def __init__(self, d: BaseDevice, perfs: typing.List[DataType] = []):
        self._d = d
        self._bundle_id = None
        self._stop_event = threading.Event()
        self._wg = WaitGroup()
        self._started = False
        self._result = defaultdict(list)
        self._perfs = perfs

        # the callback function accepts all the data
        self._callback = None

    def start(self, bundle_id: str, callback: CallbackType = None):
        if not callback:
            # 默认不输出屏幕的截图（暂时没想好怎么处理）
            callback = lambda _type, data: print(_type.value, data, flush=True) if _type != DataType.SCREENSHOT and _type in self._perfs else None
        self._rp = RunningProcess(self._d, bundle_id)
        self._thread_start(callback)

    def _thread_start(self, callback: CallbackType):
        iters = []
        if DataType.CPU in self._perfs or DataType.MEMORY in self._perfs:
            iters.append(iter_cpu_memory(self._d, self._rp))
        if DataType.FPS in self._perfs:
            iters.append(iter_fps(self._d))
        if DataType.GPU in self._perfs:
            iters.append(iter_gpu(self._d))
        if DataType.SCREENSHOT in self._perfs:
            iters.append(set_interval(iter_screenshot(self._d), 1.0))
        if DataType.NETWORK in self._perfs:
            iters.append(iter_network_flow(self._d, self._rp))
        for it in (iters): # yapf: disable
            self._wg.add(1)
            threading.Thread(name="perf",
                             target=append_data,
                             args=(self._wg, self._stop_event, it,
                                   callback,self._perfs),
                             daemon=True).start()

    def stop(self): # -> PerfReport:
        self._stop_event.set()
        print("Stopped")
        # memory and fps will take at least 1 second to catch _stop_event
        # to make function run faster, we not using self._wg.wait(..) here
        # > self._wg.wait(timeout=3.0) # wait all stopped
        # > self._started = False

    def wait(self, timeout: float):
        return self._wg.wait(timeout=timeout)
