#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Created on Mon Jan 04 2021 17:22:26 by codeskyblue
"""

import argparse
import base64
import json
import logging
import os
import pathlib
import re
import subprocess
import sys
import time
import typing
from collections import defaultdict
from datetime import datetime
from pprint import pformat, pprint
from typing import Optional, Union

import requests
from logzero import setup_logger
from tabulate import tabulate
from loguru import logger as ulogger

from ._device import Device
from ._imagemounter import cache_developer_image
from ._ipautil import IPAReader
from ._perf import DataType
from ._proto import LOG, MODELS, PROGRAM_NAME
from ._relay import relay
from ._types import ConnectionType
from ._usbmux import Usbmux
from ._utils import get_app_dir, get_binary_by_name, is_atty
from ._version import __version__
from ._wdaproxy import WDAService
from .exceptions import MuxError, MuxServiceError, ServiceError

um: Usbmux = None  # Usbmux
logger = logging.getLogger(PROGRAM_NAME)


# ulogger.remove()
# ulogger.add(sys.stderr, level="INFO")


def _complete_udid(udid: Optional[str] = None) -> str:
    infos = um.device_list()
    # Find udid exactly match
    for info in infos:
        if info.udid == udid:
            return udid
    if udid:
        sys.exit("Device for %s not detected" % udid)

    if len(infos) == 1:
        return infos[0].udid

    # filter only usb connected devices
    infos = [info for info in infos if info.conn_type == ConnectionType.USB]
    if not udid:
        if len(infos) >= 2:
            sys.exit("More than 2 usb devices detected")
        if len(infos) == 0:
            sys.exit("No local device detected")
        return infos[0].udid

    ## Find udid starts-with
    # _udids = [
    #     info.udid for info in infos
    #     if info.udid.startswith(udid)
    # ]

    # if len(_udids) == 1:
    #     return _udids[0]
    raise RuntimeError("No matched device", udid)


def _udid2device(udid: Optional[str] = None) -> Device:
    _udid = _complete_udid(udid)
    if _udid != udid:
        logger.debug("AutoComplete udid %s", _udid)
    del (udid)
    return Device(_udid, um)


def cmd_list(args: argparse.Namespace):
    _json: typing.Final[bool] = args.json
    ds = um.device_list()
    if args.usb:
        ds = [info for info in ds if info.conn_type == ConnectionType.USB]
    
    if args.one:
        for info in ds:
            print(info.udid)
        return

    headers = ['UDID', 'SerialNumber', 'NAME', 'MarketName', 'ProductVersion', "ConnType"]
    keys = ["udid", "serial", "name", "market_name", "product_version", "conn_type"]
    tabdata = []
    for dinfo in ds:
        udid, conn_type = dinfo.udid, dinfo.conn_type
        try:
            _d = Device(udid, um)
            name = _d.name
            serial = _d.get_value("SerialNumber")
            tabdata.append([udid, serial, name, MODELS.get(_d.product_type, "-"), _d.product_version, conn_type])

        except MuxError:
            name = ""
    if _json:
        result = []
        for item in tabdata:
            result.append({key: item[idx] for idx, key in enumerate(keys)})
        _print_json(result)
    else:
        print(tabulate(tabdata, headers=headers, tablefmt="plain"))


def _print_json(value):
    def _bytes_hook(obj):
        if isinstance(obj, bytes):
            return base64.b64encode(obj).decode()
        else:
            return str(obj)

    print(json.dumps(value, indent=4, ensure_ascii=False, default=_bytes_hook))


def cmd_device_info(args: argparse.Namespace):
    d = _udid2device(args.udid)
    value = d.get_value(no_session=args.simple,
                        key=args.key,
                        domain=args.domain)
    if args.json:
        _print_json(value)
    elif args.key or args.domain:
        pprint(value)
    else:
        print("{:17s} {}".format("MarketName:",
                                 MODELS.get(value['ProductType'])))
        for attr in ('DeviceName', 'ProductVersion', 'ProductType',
                     'ModelNumber', 'SerialNumber', 'PhoneNumber',
                     'CPUArchitecture', 'ProductName', 'ProtocolVersion',
                     'RegionInfo', 'TimeIntervalSince1970', 'TimeZone',
                     'UniqueDeviceID', 'WiFiAddress', 'BluetoothAddress',
                     'BasebandVersion'):
            print("{:17s} {}".format(attr + ":", value.get(attr)))


def cmd_date(args: argparse.Namespace):
    d = _udid2device(args.udid)
    value = d.get_value() or {}
    timestamp = value.get("TimeIntervalSince1970")
    if args.timestamp:
        print(timestamp)
    else:
        print(datetime.fromtimestamp(int(timestamp)))


def cmd_version(args: argparse.Namespace):
    print(PROGRAM_NAME, "version", __version__)


def cmd_install(args: argparse.Namespace):
    d = _udid2device(args.udid)
    bundle_id = d.app_install(args.filepath_or_url)

    if args.launch:
        with d.connect_instruments() as ts:
            pid = ts.app_launch(bundle_id)
            logger.info("Launch %r, process pid: %d", bundle_id, pid)


def cmd_uninstall(args: argparse.Namespace):
    d = _udid2device(args.udid)
    ok = d.app_uninstall(args.bundle_id)
    if not ok:
        sys.exit(1)


def cmd_reboot(args: argparse.Namespace):
    d = _udid2device(args.udid)
    print(d.reboot())


def cmd_shutdown(args: argparse.Namespace):
    d = _udid2device(args.udid)
    print(d.shutdown())


def cmd_parse(args: argparse.Namespace):
    uri = args.uri
    _all = args.all

    fp = None
    if re.match(r"^https?://", uri):
        try:
            import httpio
        except ImportError:
            print("Install missing lib: httpip")
            retcode = subprocess.call(
                [sys.executable, '-m', 'pip', 'install', '-U', 'httpio'])
            assert retcode == 0
            import httpio

        fp = httpio.open(uri, block_size=-1)
    else:
        assert os.path.isfile(uri)
        fp = open(uri, 'rb')

    try:
        ir = IPAReader(fp)
        ir.dump_info(all=_all)
    finally:
        fp.close()


def cmd_watch(args: argparse.Namespace):
    """
    Info example:
    {'DeviceID': 13,
     'MessageType': 'Attached',
     'Properties': {'ConnectionSpeed': 480000000,
                    'ConnectionType': 'USB',
                    'DeviceID': 13,
                    'LocationID': 340918272,
                    'ProductID': 4776,
                    'SerialNumber': '84ad172e22d8372eb752f413280722cdcc200954',
                    'USBSerialNumber': '84ad172e22d8372eb752f413280722cdcc200954'}}
    """
    for info in um.watch_device():
        logger.info("%s", pformat(info))


def cmd_wait_for_device(args):
    u = Usbmux(args.socket)

    for info in u.watch_device():
        logger.debug("%s", pformat(info))
        if info['MessageType'] != 'Attached':
            continue
        udid = info['Properties']['SerialNumber']
        if args.udid is None:
            break
        if udid == args.udid:
            print("Device {!r} attached".format(
                info['Properties']['SerialNumber']))
            break


def cmd_xctest(args: argparse.Namespace):
    """
    Run XCTest required WDA installed.
    """
    if args.debug:
        ulogger.enable(PROGRAM_NAME)
        setup_logger(LOG.xctest, level=logging.DEBUG)

    d = _udid2device(args.udid)
    env = {}
    for kv in args.env or []:
        key, val = kv.split(":", 1)
        env[key] = val
    if env:
        logger.info("Launch env: %s", env)
    d.xctest(args.bundle_id,
             target_bundle_id=args.target_bundle_id,
             logger=setup_logger(level=logging.INFO),
             env=env)


def cmd_screenshot(args: argparse.Namespace):
    d = _udid2device(args.udid)
    filename = args.filename or "screenshot.jpg"
    print("Screenshot saved to", filename)
    d.screenshot().convert("RGB").save(filename)


def cmd_app_info(args: argparse.Namespace):
    d = _udid2device(args.udid)
    info = d.installation.lookup(args.bundle_id)
    if info is None:
        sys.exit(1)
    if args.json:
        _print_json(info)
    else:
        pprint(info)


def cmd_applist(args: argparse.Namespace):
    d = _udid2device(args.udid)
    # appinfos = d.installation.list_installed()
    # apps = d.instruments.app_list()
    # pprint(apps)
    _type = args.type
    app_type = {
        "user": "User",
        "system": "System",
        "all": None,
    }[_type]

    for info in d.installation.iter_installed(app_type=app_type):
        # bundle_path = info['BundlePath']
        bundle_id = info['CFBundleIdentifier']

        try:
            display_name = info['CFBundleDisplayName']
            # major.minor.patch
            version = info.get('CFBundleShortVersionString', '')
            print(bundle_id, display_name, version)
        except BrokenPipeError:
            break
        # print(" ".join(
        #     (bundle_path, bundle_id, info['DisplayName'],
        #         info.get('Version', ''), info['Type'])))

def cmd_energy(args: argparse.Namespace):
    d = _udid2device(args.udid)
    ts = d.connect_instruments()
    try:
        pid = ts.app_launch(args.bundle_id,
                                       args=args.arguments,
                                       kill_running=args.kill)
        ts.start_energy_sampling(pid)
        while True:
            ret = ts.get_process_energy_stats(pid)
            if ret != None:
                print(json.dumps(ret))
            time.sleep(1.0)
    except ServiceError as e:
        sys.exit(e)

def cmd_launch(args: argparse.Namespace):
    d = _udid2device(args.udid)

    env = {}
    for kv in args.env or []:
        key, val = kv.split(":", 1)
        env[key] = val
    if env:
        logger.info("App launch env: %s", env)

    try:
        with d.connect_instruments() as ts:
            pid = ts.app_launch(args.bundle_id,
                                        app_env=env,
                                        args=args.arguments,
                                        kill_running=args.kill)
            print("PID:", pid)
    except ServiceError as e:
        sys.exit(e)


def cmd_kill(args: argparse.Namespace):
    d = _udid2device(args.udid)
    if args.name.isdigit():
        pid = int(args.name)
        d.app_kill(int(args.name))
    else:
        pid = d.app_kill(args.name)
        if pid is None:
            print("No app killed")
        else:
            print("Kill pid:", pid)


def cmd_system_info(args):
    d = _udid2device(args.udid)
    with d.connect_instruments() as ts:
        sinfo = ts.system_info()
        pprint(sinfo)


def cmd_battery(args: argparse.Namespace):
    d = _udid2device(args.udid)
    power_info = d.get_io_power()
    if args.json:
        _print_json(power_info)
    else:
        if power_info['Status'] != "Success":
            pprint(power_info)
            return
        # dump power info
        info = power_info['Diagnostics']['IORegistry']
        indexes = (
            ('CurrentCapacity', '当前电量', '%'),
            ('CycleCount', '充电次数', '次'),
            ('AbsoluteCapacity', '当前电量', 'mAh'),
            ('NominalChargeCapacity', '实际容量', 'mAh'),
            ('DesignCapacity', '设计容量', 'mAh'),
            ('NominalChargeCapacity', '电池寿命', lambda cap: '{}%'.format(round(cap / info['DesignCapacity'] * 100))),
            ('Serial', '序列号', ''),
            ('Temperature', '电池温度', '/100℃'),
            ('Voltage', '当前电压', 'mV'),
            ('BootVoltage', '开机电压', 'mV'),
            (('AdapterDetails', 'Watts'), '充电器功率', 'W'),
            (('AdapterDetails', 'Voltage'), '充电器电压', 'mV'),
            ('InstantAmperage', '当前电流', 'mA'),
            ('UpdateTime', '更新时间', lambda v: datetime.fromtimestamp(v).strftime("%Y-%m-%d %H:%M:%S")),
        )
        # 数据一般20s更新一次

        for keypath, cn_name, unit in indexes:
            value = info
            if isinstance(keypath, str):
                value = info[keypath]
            else:
                value = info
                for key in keypath:
                    value = value[key]
            if callable(unit):
                value = unit(value)
                unit = ""
            print("{:10s}{}{}".format(cn_name, value, unit))


def cmd_crashreport(args: argparse.Namespace):
    d = _udid2device(args.udid)
    cm = d.get_crashmanager()
    if args.list:
        cm.preview()
        return
    if args.clear:
        cm.remove_all()
        return
    if not args.output_directory:
        print("OUTPUT_DIRECTORY must be provided")
        sys.exit(1)

    remove: bool = not args.keep
    cm.afc.pull("/", args.output_directory, remove=remove)
    logger.info("Done")

def cmd_developer(args: argparse.Namespace):
    if args.download_all:
        for major in range(7, 15):
            for minor in range(0, 10):
                version = f"{major}.{minor}"
                try:
                    cache_developer_image(version)
                except requests.HTTPError:
                    break
        #     print("finish cache developer image {}".format(version))
    else:
        d = _udid2device(args.udid)
        d.mount_developer_image()
    return


def cmd_relay(args: argparse.Namespace):
    d = _udid2device(args.udid)
    relay(d, args.lport, args.rport, debug=args.debug)


def cmd_wdaproxy(args: argparse.Namespace):
    """ start xctest and relay """
    d = _udid2device(args.udid)

    env = {}
    for kv in args.env or []:
        key, val = kv.split(":", 1)
        env[key] = val
    if env:
        logger.info("Launch env: %s", env)

    serv = WDAService(d, args.bundle_id, env)
    serv.set_check_interval(args.check_interval)

    p = None
    if args.port:
        cmds = [
            sys.executable, '-m', 'tidevice', '-u', d.udid, 'relay',
            str(args.port), '8100'
        ]
        p = subprocess.Popen(cmds, stdout=sys.stdout, stderr=sys.stderr)

    try:
        serv.start()
        while serv._service.running and p.poll() is None:
            time.sleep(.1)
    finally:
        p and p.terminate()
        serv.stop()


def cmd_syslog(args: argparse.Namespace):
    d = _udid2device(args.udid)
    s = d.start_service("com.apple.syslog_relay")
    try:
        while True:
            text = s.psock.recv().decode('utf-8')
            print(text, end='', flush=True)
    except (BrokenPipeError, IOError):
        # Python flushes standard streams on exit; redirect remaining output
        # to devnull to avoid another BrokenPipeError at shutdown
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())


def cmd_dump_fps(args):
    d = _udid2device(args.udid)
    for data in d.connect_instruments().iter_opengl_data():
        if isinstance(data, str):
            continue
        fps = data['CoreAnimationFramesPerSecond']
        print("{:>2d} {}".format(fps, "-" * fps))


def cmd_pair(args: argparse.Namespace):
    d = _udid2device(args.udid)
    pair_record = d.pair()
    print("Paired with device", d.udid, "HostID:", pair_record['HostID'])


def cmd_unpair(args: argparse.Namespace):
    d = _udid2device(args.udid)
    d.delete_pair_record()


def cmd_fsync(args: argparse.Namespace):
    d = _udid2device(args.udid)
    if args.bundle_id:
        sync = d.app_sync(args.bundle_id)
    else:
        sync = d.sync

    arg0 = args.arguments[0]
    if args.command == 'ls':
        for filename in sync.listdir(arg0):
            finfo = sync.stat(pathlib.Path(arg0) / filename)
            if finfo.is_dir():
                print(filename+"/")
            else:
                print("-", filename, finfo.st_size)
    elif args.command == 'rm':
        for arg in args.arguments:
            pprint(sync.remove(arg))
    elif args.command == 'stat':
        finfo = sync.stat(arg0)
        print("IFMT:", finfo.st_ifmt)
        print("CTime:", finfo.st_ctime)
        print("MTime:", finfo.st_mtime)
        print("Size:", finfo.st_size)
    elif args.command == 'tree':
        sync.treeview(arg0, depth=-1)
    elif args.command == 'pull':
        arg1 = "./"
        if len(args.arguments) == 2:
            arg1 = args.arguments[1]
        src = pathlib.Path(arg0)
        dst = pathlib.Path(arg1)
        if dst.is_dir() and src.name and sync.stat(src).is_dir():
            dst = dst.joinpath(src.name)

        sync.pull(src, dst)
        print("pulled", src, "->", dst)
    elif args.command == 'cat':
        for chunk in sync.iter_content(arg0):
            sys.stdout.write(chunk.decode('utf-8'))
            sys.stdout.flush()
    elif args.command == 'push':
        local_path = args.arguments[0]
        device_path = args.arguments[1]
        assert os.path.isfile(local_path)
        with open(local_path, "rb") as f:
            content = f.read()
            sync.push_content(device_path, content)
            print("pushed to", device_path)
    elif args.command == 'rmtree':
        pprint(sync.rmtree(arg0))
    elif args.command == 'mkdir':
        pprint(sync.mkdir(arg0))
    else:
        raise NotImplementedError()


def cmd_ps(args: argparse.Namespace):
    d = _udid2device(args.udid)
    app_infos = list(d.installation.iter_installed(app_type=None))
    with d.connect_instruments() as ts:
        ps = list(ts.app_process_list(app_infos))

    lens = defaultdict(int)
    json_data = []
    keys = ['pid', 'name', 'bundle_id', 'display_name']
    for p in ps:
        if not args.all and not p['isApplication']:
            continue
        for key in keys:
            lens[key] = max(lens[key], len(str(p[key])))
        json_data.append({key: p[key] for key in keys})

    if args.json:
        _print_json(json_data)
        return

    # {:0} is not allowed, so max(1, xx) is necessary
    fmt = ' '.join(['{:%d}' % max(1, lens[key]) for key in keys])
    fmt = '{:>' + fmt[2:]  # set PID right align
    if is_atty:
        print(fmt.format(*[key.upper() for key in keys]))

    for p in ps:
        if not args.all and not p['isApplication']:
            continue
        print(fmt.format(*[p[key] for key in keys]), flush=True)


def cmd_perf(args: argparse.Namespace):
    assert args.bundle_id
    #print("BundleID:", args.bundle_id)
    from ._perf import Performance
    d = _udid2device(args.udid)
    perfs = list(DataType)
    if args.perfs:
        perfs = []
        for _typename in args.perfs.split(","):
            perfs.append(DataType(_typename))
    # print(perfs)
    perf = Performance(d, perfs=perfs)

    def _cb(_type: DataType, data):
        print(_type.value, data, flush=True)

    try:
        perf.start(args.bundle_id, callback=_cb)
        #print("Ctrl-C to finish")
        while True:
            time.sleep(.1)
    finally:
        perf.stop()


def cmd_set_assistive_touch(args: argparse.Namespace):
    d = _udid2device(args.udid)
    d.set_assistive_touch(args.enabled)


def cmd_savesslfile(args: argparse.Namespace):
    os.makedirs("ssl", exist_ok=True)

    d = _udid2device(args.udid)
    pr = d.pair_record

    pathlib.Path(f"ssl/{d.udid}_all.pem").write_bytes(
        pr['HostPrivateKey']
        + pr['HostCertificate']
        # + pr['RootCertificate']
    )


def cmd_test(args: argparse.Namespace):
    print("Just test")


_commands = [
    dict(action=cmd_version, command="version", help="show current version"),
    dict(action=cmd_list,
         command="list",
         flags=[
             dict(args=['--json'],
                  action='store_true',
                  help='output in json format'),
             dict(args=['--usb'],
                  action='store_true',
                  help='usb USB device'),
             dict(args=['-1'],
                  dest="one",
                  action='store_true',
                  help='output one entry per line')
         ],
         help="show connected iOS devices"),
    dict(
        action=cmd_device_info,
        command="info",
        flags=[
            dict(args=['--json'],
                 action='store_true',
                 help="output as json format"),
            dict(
                args=['-s', '--simple'],
                action='store_true',
                help=
                'use a simple connection to avoid auto-pairing with the device'
            ),
            dict(args=['-k', '--key'],
                 type=str,
                 help='only query specified KEY'),
            dict(args=['--domain'], help='set domain of query to NAME.'),
        ],
        help="show device info"),
    dict(action=cmd_date,
         command="date",
         flags=[
             dict(args=['--timestamp'],
                  action='store_true',
                  help="format timestamp")
         ],
         help="device current date"),
    dict(action=cmd_system_info,
         command="sysinfo",
         help="show device system info"),
    dict(action=cmd_app_info,
         command="appinfo",
         flags=[
             dict(args=['--json'],
                  action='store_true',
                  help='format output as json'),
             dict(args=['bundle_id'], help='bundle identifier'),
         ],
         help="inspect app info"),
    dict(action=cmd_applist,
         command="applist",
         flags=[
             dict(args=['--type'], default='user', help='filter app with type', choices=['user', 'system', 'all'])
         ],
         help="list packages"),
    dict(action=cmd_battery,
         command='battery',
         flags=[
             dict(args=['--json'],
                  action='store_true',
                  help='format output as json')
         ],
         help='show battery info'),
    dict(action=cmd_screenshot,
         command="screenshot",
         help="take screenshot",
         flags=[dict(args=['filename'], nargs="?", help="output filename")]),
    dict(action=cmd_install,
         command="install",
         flags=[
             dict(args=['-L', '--launch'],
                  action='store_true',
                  help='launch after installed'),
             dict(args=['filepath_or_url'], help="local filepath or url")
         ],
         help="install application"),
    dict(action=cmd_uninstall,
         command="uninstall",
         flags=[dict(args=['bundle_id'], help="bundle_id of application")],
         help="uninstall application"),
    dict(action=cmd_reboot, command="reboot", help="reboot device"),
    dict(action=cmd_shutdown, command="shutdown", help="shutdown device"),
    dict(action=cmd_parse,
         command="parse",
         flags=[
             dict(args=['--all'], action='store_true', help='show all info'),
             dict(args=['uri'], help="local path or url")
         ],
         help="parse ipa bundle id"),
    dict(action=cmd_watch, command="watch", help="watch device"),
    dict(action=cmd_wait_for_device,
         command='wait-for-device',
         help='wait for device attached'),
    dict(action=cmd_launch,
         command="launch",
         flags=[
             dict(args=['--kill'],
                  action='store_true',
                  help='kill app if running'),
             dict(args=["bundle_id"], help="app bundleId"),
             dict(args=['arguments'], nargs='*', help='app arguments'),
             dict(
                 args=['-e', '--env'],
                 action='append',
                 help="set env with format key:value, support multi -e"),
         ],
         help="launch app with bundle_id"),
    dict(action=cmd_energy,
         command="energy",
         flags=[
             dict(args=['--kill'],
                  action='store_true',
                  help='kill app if running'),
             dict(args=["bundle_id"], help="app bundleId"),
             dict(args=['arguments'], nargs='*', help='app arguments'),
         ],
         help="launch app with bundle_id"),
    dict(action=cmd_kill,
         command="kill",
         flags=[dict(args=['name'], help='pid or bundle_id')],
         help="kill by pid or bundle_id"),
    dict(action=cmd_ps,
         command="ps",
         flags=[
             dict(args=['--json'],
                  action='store_true',
                  help='format output as json'),
             dict(args=['-A', '--all'],
                  action='store_true',
                  help='show all process')
         ],
         help="show running processes"),
    dict(action=cmd_relay,
         command="relay",
         flags=[
             dict(args=['-x', "--debug"],
                  action='store_true',
                  help='verbose data traffic, hexadecimal'),
             dict(args=['lport'], type=int, help='local port'),
             dict(args=['rport'], type=int, help='remote port'),
         ],
         help="relay phone inner port to pc, same as iproxy"),
    dict(
        action=cmd_xctest,
        command="xctest",
        flags=[
            dict(args=['--debug'], action='store_true', help='show debug log'),
            dict(args=['-B', '--bundle_id', '--bundle-id'],
                 default="com.*.xctrunner",
                 help="bundle id of the test to launch"),
            dict(args=['--target-bundle-id'],
                 help='bundle id of the target app [optional]'),
            #  dict(args=['-I', '--install-wda'],
            #       action='store_true',
            #       help='install webdriveragent app'),
            dict(args=['-e', '--env'],
                 action='append',
                 help="set env with format key:value, support multi -e"),
        ],
        help="run XCTest"),
    dict(
        action=cmd_wdaproxy,
        command='wdaproxy',
        flags=[
            dict(
                args=['-B', '--bundle_id'],
                default="com.*.xctrunner",
                help="test application bundle id"),
            dict(
                args=['-p', '--port'],
                type=int,
                default=8100,
                help='pc listen port, set to 0 to disable port forward'),
            dict(
                args=['-e', '--env'],
                action='append',
                help="set env with format key:value, support multi -e"),
            dict(
                args=['--check-interval'],
                type=float,
                default=30.0,
                help=
                "check if wda is alive every CHECK_INTERVAL seconds, stop check when set to 0"
            ),
        ],
        help='keep WDA running and relay WDA service to pc'),
    dict(action=cmd_syslog, command='syslog', help="print iphone syslog"),
    dict(action=cmd_fsync,
         command="fsync",
         flags=[
             dict(args=['-B', '--bundle_id'], help='app bundle id'),
             dict(args=['command'],
                  choices=[
                      'ls', 'rm', 'cat', 'pull', 'push', 'stat', 'tree',
                      'rmtree', 'mkdir'
                  ]),
             dict(args=['arguments'], nargs='+', help='command arguments'),
         ],
         help="app file management"),
    dict(action=cmd_crashreport,
         command="crashreport",
         flags=[
             dict(args=['-l', '--list'], action='store_true', help='list all crash files'),
             dict(args=['-k', '--keep'], action='store_true', help="copy but do not remove crash reports from device"),
             dict(args=['-c', '--clear'], action='store_true', help='clear crash files'),
             dict(args=['output_directory'], nargs="?", help='The output dir to save crash logs synced from device'),
         ],
         help="crash log tools"),
    dict(action=cmd_dump_fps, command='dumpfps', help='dump fps'),
    dict(action=cmd_developer,
         command="developer",
         flags=[
             dict(args=['--download-all'],
                  action="store_true",
                  help="download all developer to local")
         ],
         help="mount developer image to device"),
    dict(action=cmd_pair, command='pair', help='pair device'),
    dict(action=cmd_unpair, command="unpair", help="unpair device"),
    dict(action=cmd_perf,
         command="perf",
         flags=[
             dict(args=['-B', '--bundle_id'],
                  help='app bundle id',
                  required=True),
             dict(args=['-o'],
                  dest='perfs',
                  help='cpu,memory,fps,network,screenshot. separate by ","',
                  required=False),
         ],
         help="performance of app"),
    dict(action=cmd_set_assistive_touch,
         command="set-assistive-touch",
         flags=[
             dict(args=['--enabled'], action='store_true', help="set enabled")
         ],
         help="command for developer"),
    dict(action=cmd_savesslfile,
         command="savesslfile",
         help="save to ssl/xxxx_root.pem and ssl/xxxx_host.pem"),
    dict(action=cmd_test, command="test", help="command for developer"),
]


def main():
    # yapf: disable
    parser = argparse.ArgumentParser(
        description="Tool for communicate with iOS devices, version {}, created: codeskyblue 2020/05".format(__version__),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("-v", "--version", action="store_true", help="show current version"),
    parser.add_argument("-u", "--udid", help="specify unique device identifier")
    parser.add_argument("--socket", help="usbmuxd listen address, host:port or local-path")

    subparser = parser.add_subparsers(dest='subparser')
    actions = {}
    for c in _commands:
        cmd_name = c['command']
        actions[cmd_name] = c['action']
        sp = subparser.add_parser(cmd_name, help=c.get('help'),
                                  formatter_class=argparse.ArgumentDefaultsHelpFormatter)
        for f in c.get('flags', []):
            args = f.get('args')
            if not args:
                args = ['-'*min(2, len(n)) + n for n in f['name']]
            kwargs = f.copy()
            kwargs.pop('name', None)
            kwargs.pop('args', None)
            sp.add_argument(*args, **kwargs)

    args = parser.parse_args()

    if args.version:
        print(__version__)
        return

    if not args.subparser:
        parser.print_help()
        # show_upgrade_message()
        return

    # log setup
    setup_logger(LOG.main,
        level=logging.DEBUG if os.getenv("DEBUG") in ("1", "on", "true") else logging.INFO)

    global um
    um = Usbmux(args.socket)
    actions[args.subparser](args)
    # yapf: enable


if __name__ == "__main__":
    main()
