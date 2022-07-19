# coding: utf-8
#
# Python 3.x
# codeskyblue 2020/05/18

import contextlib
import datetime
import fnmatch
import io
import logging
import os
import pathlib
import re
import shutil
import socket
import ssl
import sys
import tempfile
import threading
import time
import typing
import uuid
import zipfile
from typing import Iterator, Optional, Union

import requests
from deprecation import deprecated
from logzero import setup_logger
from PIL import Image

from . import bplist
from ._crash import CrashManager
from ._imagemounter import ImageMounter, cache_developer_image
from ._installation import Installation
from ._instruments import (AUXMessageBuffer, DTXMessage, DTXService, Event,
                           ServiceInstruments)
from ._ipautil import IPAReader
from ._proto import *
from ._safe_socket import *
from ._sync import Sync
from ._types import DeviceInfo
from ._usbmux import Usbmux
from ._utils import ProgressReader, get_app_dir, set_socket_timeout
from .exceptions import *

logger = logging.getLogger(LOG.main)


def pil_imread(data: Union[str, pathlib.Path, bytes, bytearray]) -> Image.Image:
    """ Convert data(path, binary) to PIL.Image.Image
    
    Raises:
        TypeError
    """
    if isinstance(data, (bytes, bytearray)):
        memory_fd = io.BytesIO(data)
        im = Image.open(memory_fd)
        im.load()
        del (memory_fd)
        return im
    elif isinstance(data, str):
        return Image.open(data)
    else:
        raise TypeError("Unknown data type", type(data))


class BaseDevice():
    def __init__(self,
                 udid: Optional[str] = None,
                 usbmux: Union[Usbmux, str, None] = None):
        if udid is None:
            udid = os.environ.get("TMQ_DEVICE_UDID")
            if udid:
                logger.info("use udid from env: %s=%s", "TMQ_DEVICE_UDID",
                            udid)
        if usbmux is None:
            usbmux = os.environ.get("TMQ_USBMUX")
            if usbmux:
                logger.info("use usbmux from env: %s=%s", "TMQ_USBMUX", usbmux)

        if not usbmux:
            self._usbmux = Usbmux()
        elif isinstance(usbmux, str):
            self._usbmux = Usbmux(usbmux)
        elif isinstance(usbmux, Usbmux):
            self._usbmux = usbmux

        self._udid = udid
        self._info: DeviceInfo = None
        self._lock = threading.Lock()
        self._pair_record = None

    @property
    def debug(self) -> bool:
        return logging.getLogger(LOG.main).level == logging.DEBUG

    @debug.setter
    def debug(self, v: bool):
        # log setup
        setup_logger(LOG.main,
            level=logging.DEBUG if v else logging.INFO)

    @property
    def usbmux(self) -> Usbmux:
        return self._usbmux

    @property
    def info(self) -> DeviceInfo:
        if self._info:
            return self._info
        devices = self._usbmux.device_list()
        if self._udid:
            for d in devices:
                if d.udid == self._udid:
                    self._info = d
        else:
            if len(devices) == 0:
                raise MuxError("No device connected")
            elif len(devices) > 1:
                raise MuxError("More then one device connected")
            _d = devices[0]
            self._udid = _d.udid
            self._info = _d

        if not self._info:
            raise MuxError("Device: {} not ready".format(self._udid))
        return self._info

    def is_connected(self) -> bool:
        return self.udid in self.usbmux.device_udid_list()

    @property
    def udid(self) -> str:
        return self._udid

    @property
    def devid(self) -> int:
        return self.info.device_id

    @property
    def pair_record(self) -> dict:
        if not self._pair_record:
            self.handshake()
        return self._pair_record

    @pair_record.setter
    def pair_record(self, val: Optional[dict]):
        self._pair_record = val

    def _read_pair_record(self) -> dict:
        """
        DeviceCertificate
        EscrowBag
        HostID
        HostCertificate
        HostPrivateKey
        RootCertificate
        RootPrivateKey
        SystemBUID
        WiFiMACAddress

        Pair data can be found in
            win32: os.environ["ALLUSERSPROFILE"] + "/Apple/Lockdown/"
            darwin: /var/db/lockdown/
            linux: /var/lib/lockdown/
        
        if ios version > 13.0
            get pair data from usbmuxd
        else:
            generate pair data with python
        """
        payload = {
            'MessageType': 'ReadPairRecord',  # Required
            'PairRecordID': self.udid,  # Required
            'ClientVersionString': 'libusbmuxd 1.1.0',
            'ProgName': PROGRAM_NAME,
            'kLibUSBMuxVersion': 3
        }
        data = self._usbmux.send_recv(payload)
        record_data = data['PairRecordData']
        return bplist.loads(record_data)

    def delete_pair_record(self):
        data = self._usbmux.send_recv({
            "MessageType": "DeletePairRecord",
            "PairRecordID": self.udid,
            "ProgName": PROGRAM_NAME,
        })
        # Expect: {'MessageType': 'Result', 'Number': 0}

    def pair(self):
        """
        Same as idevicepair pair
        iconsole is a github project, hosted in https://github.com/anonymous5l/iConsole
        """
        device_public_key = self.get_value("DevicePublicKey", no_session=True)
        if not device_public_key:
            raise MuxError("Unable to retrieve DevicePublicKey")
        buid = self._usbmux.read_system_BUID()
        wifi_address = self.get_value("WiFiAddress", no_session=True)

        try:
            from ._ssl import make_certs_and_key
        except ImportError:
            #print("DevicePair require pyOpenSSL and pyans1, install by the following command")
            #print("\tpip3 install pyOpenSSL pyasn1", flush=True)
            raise RuntimeError("DevicePair required lib, fix with: pip3 install pyOpenSSL pyasn1")

        cert_pem, priv_key_pem, dev_cert_pem = make_certs_and_key(device_public_key)
        pair_record = {
            'DevicePublicKey': device_public_key,
            'DeviceCertificate': dev_cert_pem,
            'HostCertificate': cert_pem,
            'HostID': str(uuid.uuid4()).upper(),
            'RootCertificate': cert_pem,
            'SystemBUID': buid,
        }

        with self.create_inner_connection() as s:
            ret = s.send_recv_packet({
                "Request": "Pair",
                "PairRecord": pair_record,
                "Label": PROGRAM_NAME,
                "ProtocolVersion": "2",
                "PairingOptions": {
                    "ExtendedPairingErrors": True,
                }
            })
            assert ret, "Pair request got empty response"
            if "Error" in ret:
                # error could be "PasswordProtected" or "PairingDialogResponsePending"
                raise MuxError("pair:", ret['Error'])

            assert 'EscrowBag' in ret, ret
            pair_record['HostPrivateKey'] = priv_key_pem
            pair_record['EscrowBag'] = ret['EscrowBag']
            pair_record['WiFiMACAddress'] = wifi_address

        self.usbmux.send_recv({
            "MessageType": "SavePairRecord",
            "PairRecordID": self.udid,
            "PairRecordData": bplist.dumps(pair_record),
            "DeviceID": self.devid,
        })
        return pair_record

    def handshake(self):
        """
        set self._pair_record
        """
        try:
            self._pair_record = self._read_pair_record()
        except MuxReplyError as err:
            if err.reply_code == UsbmuxReplyCode.BadDevice:
                self._pair_record = self.pair()

    @property
    def ssl_pemfile_path(self):
        with self._lock:
            appdir = get_app_dir("ssl")
            fpath = os.path.join(appdir, self._udid + "-" + self._host_id + ".pem")
            if os.path.exists(fpath):
                # 3 minutes not regenerate pemfile
                st_mtime = datetime.datetime.fromtimestamp(
                    os.stat(fpath).st_mtime)
                if datetime.datetime.now() - st_mtime < datetime.timedelta(
                        minutes=3):
                    return fpath
            with open(fpath, "wb") as f:
                pdata = self.pair_record
                f.write(pdata['HostPrivateKey'])
                f.write(b"\n")
                f.write(pdata['HostCertificate'])
            return fpath

    @property
    def _host_id(self):
        return self.pair_record['HostID']

    @property
    def _system_BUID(self):
        return self.pair_record['SystemBUID']

    def create_inner_connection(
            self,
            port: int = LOCKDOWN_PORT,  # 0xf27e,
            _ssl: bool = False,
            ssl_dial_only: bool = False) -> PlistSocketProxy:
        device_id = self.info.device_id
        conn = self._usbmux.connect_device_port(device_id, port)
        if _ssl:
            with set_socket_timeout(conn.get_socket, 10.0):
                psock = conn.psock
                psock.switch_to_ssl(self.ssl_pemfile_path)
                if ssl_dial_only:
                    psock.ssl_unwrap()
        return conn

    @contextlib.contextmanager
    def create_session(self) -> PlistSocketProxy:
        """
        Create session inside SSLContext
        """
        with self.create_inner_connection() as _s:  # 62078=0xf27e
            s: PlistSocketProxy = _s
            del(_s)

            data = s.send_recv_packet({"Request": "QueryType"})
            # Expect: {'Request': 'QueryType', 'Type': 'com.apple.mobile.lockdown'}
            assert data['Type'] == LockdownService.MobileLockdown

            data = s.send_recv_packet({
                'Request': 'GetValue',
                'Key': 'ProductVersion',
                'Label': PROGRAM_NAME,
            })
            # Expect: {'Key': 'ProductVersion', 'Request': 'GetValue', 'Value': '13.4.1'}

            data = s.send_recv_packet({
                "Request": "StartSession",
                "HostID": self.pair_record['HostID'],
                "SystemBUID": self.pair_record['SystemBUID'],
                "ProgName": PROGRAM_NAME,
            })
            if 'Error' in data:
                if data['Error'] == 'InvalidHostID':
                    # try to repair device
                    self.pair_record = None
                    self.delete_pair_record()
                    self.handshake()
                    # After paired, call StartSession again
                    data = s.send_recv_packet({
                        "Request": "StartSession",
                        "HostID": self.pair_record['HostID'],
                        "SystemBUID": self.pair_record['SystemBUID'],
                        "ProgName": PROGRAM_NAME,
                    })
                else:
                    raise MuxError("StartSession", data['Error'])

            session_id = data['SessionID']
            if data['EnableSessionSSL']:
                # tempfile.NamedTemporaryFile is not working well on windows
                # See: https://stackoverflow.com/questions/6416782/what-is-namedtemporaryfile-useful-for-on-windows
                s.psock.switch_to_ssl(self.ssl_pemfile_path)

            yield s

            s.send_packet({
                "Request": "StopSession",
                "ProtocolVersion": '2',
                "Label": PROGRAM_NAME,
                "SessionID": session_id,
            })
            s.recv_packet()

    def device_info(self, domain: Optional[str] = None) -> dict:
        """
        Args:
            domain: can be found in "ideviceinfo -h", eg: com.apple.disk_usage
        """
        return self.get_value(domain=domain)

    def get_value(self, key: str = '', domain: str = "", no_session: bool = False):
        """ key can be: ProductVersion
        Args:
            domain (str): com.apple.disk_usage
            no_session: set to True when not paired
        """
        request = {
            "Request": "GetValue",
            "Label": PROGRAM_NAME,
        }
        if key:
            request['Key'] = key
        if domain:
            request['Domain'] = domain

        if no_session:
            with self.create_inner_connection() as s:
                ret = s.send_recv_packet(request)
                return ret['Value']
        else:
            with self.create_session() as conn:
                ret = conn.send_recv_packet(request)
                return ret['Value']

    def set_value(self, domain: str, key: str, value: typing.Any):
        request = {
            "Domain": domain,
            "Key": key,
            "Label": "oa",
            "Request": "SetValue",
            "Value": value
        }
        with self.create_session() as s:
            ret = s.send_recv_packet(request)
            error = ret.get("Error")
            if error:
                raise ServiceError(error)

    def set_assistive_touch(self, enabled: bool):
        """
        show or close screen assitive touch button

        Raises:
            ServiceError
        """
        self.set_value("com.apple.Accessibility", "AssistiveTouchEnabledByiTunes", enabled)

    def screen_info(self) -> tuple:
        info = self.device_info("com.apple.mobile.iTunes")
        return {
            "width": info['ScreenWidth'],
            "height": info['ScreenHeight'],
            "scale": info['ScreenScaleFactor'],  # type: float
        }

    def battery_info(self) -> dict:
        info = self.device_info('com.apple.mobile.battery')
        return {
            "level": info['BatteryCurrentCapacity'],
        }

    def storage_info(self) -> dict:
        """ the unit might be 1000 not 1024 """
        info = self.device_info('com.apple.disk_usage')
        disk = info['TotalDiskCapacity']
        size = info['TotalDataCapacity']
        free = info['TotalDataAvailable']
        used = size - free
        return {
            "disk_size": disk,
            "used": used,
            "free": free,
            # "free_percent": free * 100 / size + 2), 10) + '%'
        }

    def reboot(self) -> str:
        """ reboot device """
        conn = self.start_service("com.apple.mobile.diagnostics_relay")
        ret = conn.send_recv_packet({
            "Request": "Restart",
            "Label": PROGRAM_NAME,
        })
        return ret['Status']

    def shutdown(self):
        conn = self.start_service("com.apple.mobile.diagnostics_relay")
        ret = conn.send_recv_packet({
            "Request": "Shutdown",
            "Label": PROGRAM_NAME,
        })
        return ret['Status']

    def get_io_power(self) -> dict:
        return self.get_io_registry('IOPMPowerSource')

    def get_io_registry(self, name: str) -> dict:
        conn = self.start_service("com.apple.mobile.diagnostics_relay")
        ret = conn.send_recv_packet({
            'Request': 'IORegistry',
            'EntryClass': name,
            "Label": PROGRAM_NAME,
        })
        return ret

    def get_crashmanager(self) -> CrashManager:
        """
        https://github.com/libimobiledevice/libimobiledevice/blob/master/tools/idevicecrashreport.c
        """
        # read "ping" message which indicates the crash logs have been moved to a safe harbor
        move_conn = self.start_service(LockdownService.CRASH_REPORT_MOVER_SERVICE)
        ack = b'ping\x00'
        if ack != move_conn.psock.recvall(len(ack)):
            raise ServiceError("ERROR: Crash logs could not be moved. Connection interrupted")

        copy_conn = self.start_service(LockdownService.CRASH_REPORT_COPY_MOBILE_SERVICE)
        return CrashManager(copy_conn)

    def start_service(self, name: str) -> PlistSocketProxy:
        try:
            return self._unsafe_start_service(name)
        except MuxServiceError:
            self.mount_developer_image()
            # maybe should wait here
            time.sleep(.5)
            return self._unsafe_start_service(name)

    def _unsafe_start_service(self, name: str) -> PlistSocketProxy:
        with self.create_session() as _s:
            s: PlistSocketProxy = _s
            del(_s)

            data = s.send_recv_packet({
                "Request": "StartService",
                "Service": name,
                "Label": PROGRAM_NAME,
            })
            if 'Error' in data:  # data['Error'] is InvalidService
                error = data['Error'] # PasswordProtected, InvalidService
                raise MuxServiceError(error)

        # Expect recv
        # {'EnableServiceSSL': True,
        #  'Port': 53428,
        #  'Request': 'StartService',
        #  'Service': 'com.apple.xxx'}
        assert data['Service'] == name
        _ssl = data.get(
            'EnableServiceSSL',
            False)

        # These DTX based services only execute a SSL Handshake
        # and then go back to sending unencrypted data right after the handshake.
        ssl_dial_only = False
        if name in ("com.apple.instruments.remoteserver",
                    "com.apple.accessibility.axAuditDaemon.remoteserver",
                    "com.apple.testmanagerd.lockdown",
                    "com.apple.debugserver"):
            ssl_dial_only = True
        conn = self.create_inner_connection(data['Port'], _ssl=_ssl, ssl_dial_only=ssl_dial_only)
        conn.name = data['Service']
        return conn

    def screenshot(self) -> Image.Image:
        return next(self.iter_screenshot())

    def iter_screenshot(self) -> Iterator[Image.Image]:
        """ take screenshot infinite """

        conn = self.start_service(LockdownService.MobileScreenshotr)
        version_exchange = conn.recv_packet()
        # Expect recv: ['DLMessageVersionExchange', 300, 0]

        data = conn.send_recv_packet([
            'DLMessageVersionExchange', 'DLVersionsOk', version_exchange[1]
        ])
        # Expect recv: ['DLMessageDeviceReady']
        assert data[0] == 'DLMessageDeviceReady'

        while True:
            # code will be blocked here until next(..) called
            data = conn.send_recv_packet([
                'DLMessageProcessMessage', {
                    'MessageType': 'ScreenShotRequest'
                }
            ])
            # Expect recv: ['DLMessageProcessMessage', {'MessageType': 'ScreenShotReply', ScreenShotData': b'\x89PNG\r\n\x...'}]
            assert len(data) == 2 and data[0] == 'DLMessageProcessMessage'
            assert isinstance(data[1], dict)
            assert data[1]['MessageType'] == "ScreenShotReply"

            png_data = data[1]['ScreenShotData']

            yield pil_imread(png_data)

    @property
    def name(self):
        return self.get_value("DeviceName", no_session=True)

    @property
    def product_version(self) -> str:
        return self.get_value("ProductVersion", no_session=True)

    @property
    def product_type(self) -> str:
        return self.get_value("ProductType", no_session=True)

    def app_sync(self, bundle_id: str, command: str = "VendDocuments") -> Sync:
        # Change command(VendContainer -> VendDocuments)
        # According to https://github.com/GNOME/gvfs/commit/b8ad223b1e2fbe0aec24baeec224a76d91f4ca2f
        # Ref: https://github.com/libimobiledevice/libimobiledevice/issues/193
        conn = self.start_service(LockdownService.MobileHouseArrest)
        conn.send_packet({
            "Command": command,
            "Identifier": bundle_id,
        })
        return Sync(conn)

    @property
    def installation(self) -> Installation:
        conn = self.start_service(Installation.SERVICE_NAME)
        return Installation(conn)

    @property
    def imagemounter(self) -> ImageMounter:
        """
        start_service will call imagemounter, so here should call
        _unsafe_start_service instead
        """
        conn = self._unsafe_start_service(ImageMounter.SERVICE_NAME)
        return ImageMounter(conn)

    @contextlib.contextmanager
    def _request_developer_image_dir(self):
        # use local path first
        # use download cache resource second
        # download from network third
        product_version = self.get_value("ProductVersion")
        logger.info("ProductVersion: %s", product_version)
        major, minor = product_version.split(".")[:2]
        version = major + "." + minor

        mac_developer_dir = f"/Applications/Xcode.app/Contents/Developer/Platforms/iPhoneOS.platform/DeviceSupport/{version}"
        image_path = os.path.join(mac_developer_dir, "DeveloperDiskImage.dmg")
        signature_path = image_path + ".signature"
        if os.path.isfile(image_path) and os.path.isfile(signature_path):
            yield mac_developer_dir
        else:
            image_zip_path = cache_developer_image(version)
            with tempfile.TemporaryDirectory() as tmpdir:
                zf = zipfile.ZipFile(image_zip_path)
                zf.extractall(tmpdir)
                rootfiles = os.listdir(tmpdir)

                rootdirs = []
                for fname in rootfiles:
                    if fname.startswith("_") or fname.startswith("."):
                        continue
                    if os.path.isdir(os.path.join(tmpdir, fname)):
                        rootdirs.append(fname)

                if len(rootfiles) == 0: # empty zip
                    raise RuntimeError("deviceSupport zip file is empty")
                elif os.path.isfile(os.path.join(tmpdir, "DeveloperDiskImage.dmg")):
                    yield tmpdir
                elif version in rootdirs: # contains directory: {version}
                    yield os.path.join(tmpdir, version)
                elif len(rootdirs) == 1: # only contain one directory
                    yield os.path.join(tmpdir, rootdirs[0])
                else:
                    raise RuntimeError("deviceSupport for {} not detected DeveloperDiskImage".format(version))

    def _test_if_developer_mounted(self) -> bool:
        try:
            with self.create_session():
                self._unsafe_start_service(LockdownService.MobileLockdown)
                return True
        except MuxServiceError:
            return False

    def mount_developer_image(self):
        """
        Raises:
            MuxError
        """
        try:
            if self.imagemounter.is_developer_mounted():
                logger.info("DeveloperImage already mounted")
                return
        except MuxError: # expect: DeviceLocked
            pass

        if self._test_if_developer_mounted():
            logger.info("DeviceLocked, but DeveloperImage already mounted")
            return

        with self._request_developer_image_dir() as _dir: #, signature_path:
            image_path = os.path.join(_dir, "DeveloperDiskImage.dmg")
            signature_path = image_path + ".signature"
            self.imagemounter.mount(image_path, signature_path)
            logger.info("DeveloperImage mounted successfully")

    @property
    def sync(self) -> Sync:
        conn = self.start_service(LockdownService.AFC)
        return Sync(conn)

    def app_stop(self, pid_or_name: Union[int, str]) -> int:
        """
        return pid killed
        """
        with self.connect_instruments() as ts:
            if isinstance(pid_or_name, int):
                ts.app_kill(pid_or_name)
                return pid_or_name
            elif isinstance(pid_or_name, str):
                bundle_id = pid_or_name
                app_infos = list(self.installation.iter_installed(app_type=None))
                ps = ts.app_process_list(app_infos)
                for p in ps:
                    if p['bundle_id'] == bundle_id:
                        ts.app_kill(p['pid'])
                        return p['pid']
        return None

    def app_kill(self, *args, **kwargs) -> int:
        """ alias of app_stop """
        return self.app_stop(*args, **kwargs)

    def app_start(self,
                  bundle_id: str,
                  args: Optional[list] = [],
                  kill_running: bool = False) -> int:
        """
        start application
        
        return pid
        """
        with self.connect_instruments() as ts:
            return ts.app_launch(bundle_id, args=args, kill_running=kill_running)

    def app_install(self, file_or_url: Union[str, typing.IO]) -> str:
        """
        Args:
            file_or_url: local path or url

        Returns:
            bundle_id

        Raises:
            ServiceError, IOError

        # Copying 'WebDriverAgentRunner-Runner-resign.ipa' to device... DONE.
        # Installing 'com.facebook.WebDriverAgentRunner.xctrunner'
        #  - CreatingStagingDirectory (5%)
        #  - ExtractingPackage (15%)
        #  - InspectingPackage (20%)
        #  - TakingInstallLock (20%)
        #  - PreflightingApplication (30%)
        #  - InstallingEmbeddedProfile (30%)
        #  - VerifyingApplication (40%)
        #  - CreatingContainer (50%)
        #  - InstallingApplication (60%)
        #  - PostflightingApplication (70%)
        #  - SandboxingApplication (80%)
        #  - GeneratingApplicationMap (90%)
        #  - Complete
        """
        is_url = bool(re.match(r"^https?://", file_or_url))
        if is_url:
            url = file_or_url
            tmpdir = tempfile.TemporaryDirectory()
            filepath = os.path.join(tmpdir.name, "_tmp.ipa")
            logger.info("Download to tmp path: %s", filepath)
            with requests.get(url, stream=True) as r:
                filesize = int(r.headers.get("content-length"))
                preader = ProgressReader(r.raw, filesize)
                with open(filepath, "wb") as f:
                    shutil.copyfileobj(preader, f)
                preader.finish()
        elif os.path.isfile(file_or_url):
            filepath = file_or_url
        else:
            raise IOError(
                "Local path {} not exist".format(file_or_url))

        ir = IPAReader(filepath)
        bundle_id = ir.get_bundle_id()
        short_version = ir.get_short_version()
        ir.close()

        conn = self.start_service(LockdownService.AFC)
        afc = Sync(conn)

        ipa_tmp_dir = "PublicStaging"
        if not afc.exists(ipa_tmp_dir):
            afc.mkdir(ipa_tmp_dir)

        print("Copying {!r} to device...".format(filepath), end=" ")
        sys.stdout.flush()
        target_path = ipa_tmp_dir + "/" + bundle_id + ".ipa"

        filesize = os.path.getsize(filepath)
        with open(filepath, 'rb') as f:
            preader = ProgressReader(f, filesize)
            afc.push_content(target_path, preader)
        preader.finish()
        print("DONE.")

        print("Installing {!r} {!r}".format(bundle_id, short_version))
        return self.installation.install(bundle_id, target_path)

    def app_uninstall(self, bundle_id: str) -> bool:
        """
        Note: It seems always return True
        """
        return self.installation.uninstall(bundle_id)

    def _connect_testmanagerd_lockdown(self) -> DTXService:
        if self.major_version() >= 14:
            conn = self.start_service(
                LockdownService.TestmanagerdLockdownSecure)
        else:
            conn = self.start_service(LockdownService.TestmanagerdLockdown)
        return DTXService(conn)

    def connect_instruments(self) -> ServiceInstruments:
        """ start service for instruments """
        if self.major_version() >= 14:
            conn = self.start_service(
                LockdownService.InstrumentsRemoteServerSecure)
        else:
            conn = self.start_service(LockdownService.InstrumentsRemoteServer)

        return ServiceInstruments(conn)
    
    @deprecated(details="use connect_instruments instead")
    def instruments_context(self) -> typing.Generator[ServiceInstruments, None, None]:
        return self.connect_instruments()
        
    def _launch_app_runner(self,
                    bundle_id: str,
                    session_identifier: uuid.UUID,
                    env: dict = {},
                    target_app_bundle_id: str = None,
                    logger: logging.Logger = logging,
                    quit_event: threading.Event = None) -> typing.Tuple[ServiceInstruments, int]:  # pid

        logger = logging.getLogger(LOG.xctest)

        app_info = self.installation.lookup(bundle_id)
        sign_identity = app_info.get("SignerIdentity", "")
        logger.info("SignIdentity: %r", sign_identity)

        app_container = app_info['Container']

        # CFBundleName always endswith -Runner
        exec_name = app_info['CFBundleExecutable']
        logger.info("CFBundleExecutable: %s", exec_name)
        assert exec_name.endswith("-Runner"), "Invalid CFBundleExecutable: %s" % exec_name
        target_name = exec_name[:-len("-Runner")]

        xctest_path = f"/tmp/{target_name}-{str(session_identifier).upper()}.xctestconfiguration"  # yapf: disable
        xctest_content = bplist.objc_encode(bplist.XCTestConfiguration({
            "testBundleURL": bplist.NSURL(None, f"file://{app_info['Path']}/PlugIns/{target_name}.xctest"),
            "sessionIdentifier": session_identifier,
            "targetApplicationBundleID": target_app_bundle_id,
        }))  # yapf: disable

        fsync = self.app_sync(bundle_id, command="VendContainer")
        for fname in fsync.listdir("/tmp"):
            if fname.endswith(".xctestconfiguration"):
                logger.debug("remove /tmp/%s", fname)
                fsync.remove("/tmp/" + fname)
        fsync.push_content(xctest_path, xctest_content)

        # service: com.apple.instruments.remoteserver
        conn = self.connect_instruments()
        channel = conn.make_channel(InstrumentsService.ProcessControl)

        conn.call_message(channel, "processIdentifierForBundleIdentifier:",
                          [bundle_id])

        # launch app
        identifier = "launchSuspendedProcessWithDevicePath:bundleIdentifier:environment:arguments:options:"
        app_path = app_info['Path']

        xctestconfiguration_path = app_container + xctest_path  # "/tmp/WebDriverAgentRunner-" + str(session_identifier).upper() + ".xctestconfiguration"
        logger.debug("AppPath: %s", app_path)
        logger.info("AppContainer: %s", app_container)
        app_env = {
            'CA_ASSERT_MAIN_THREAD_TRANSACTIONS': '0',
            'CA_DEBUG_TRANSACTIONS': '0',
            'DYLD_FRAMEWORK_PATH': app_path + '/Frameworks:',
            'DYLD_LIBRARY_PATH': app_path + '/Frameworks',
            'NSUnbufferedIO': 'YES',
            'SQLITE_ENABLE_THREAD_ASSERTIONS': '1',
            'WDA_PRODUCT_BUNDLE_IDENTIFIER': '',
            'XCTestConfigurationFilePath': xctestconfiguration_path,
            'XCODE_DBG_XPC_EXCLUSIONS': 'com.apple.dt.xctestSymbolicator',
            # '__XCODE_BUILT_PRODUCTS_DIR_PATHS': '/tmp/derivedDataPath/Build/Products/Release-iphoneos',
            # '__XPC_DYLD_FRAMEWORK_PATH': '/tmp/derivedDataPath/Build/Products/Release-iphoneos',
            # '__XPC_DYLD_LIBRARY_PATH': '/tmp/derivedDataPath/Build/Products/Release-iphoneos',
            'MJPEG_SERVER_PORT': '',
            'USE_PORT': '',
            # maybe no needed
            'LLVM_PROFILE_FILE': app_container + "/tmp/%p.profraw", # %p means pid
        } # yapf: disable
        app_env.update(env)

        if self.major_version() >= 11:
            app_env['DYLD_INSERT_LIBRARIES'] = '/Developer/usr/lib/libMainThreadChecker.dylib'
            app_env['OS_ACTIVITY_DT_MODE'] = 'YES'

        app_args = [
            '-NSTreatUnknownArgumentsAsOpen', 'NO',
            '-ApplePersistenceIgnoreState', 'YES'
        ]
        app_options = {'StartSuspendedKey': False}
        if self.major_version() >= 12:
            app_options['ActivateSuspended'] = True

        pid = conn.call_message(
            channel, identifier,
            [app_path, bundle_id, app_env, app_args, app_options])
        if not isinstance(pid, int):
            logger.error("Launch failed: %s", pid)
            raise MuxError("Launch failed")

        logger.info("Launch %r pid: %d", bundle_id, pid)
        aux = AUXMessageBuffer()
        aux.append_obj(pid)
        conn.call_message(channel, "startObservingPid:", aux)

        # activitytracetap = False  # even through xcode use it, but it seems works fine without it
        # if activitytracetap:

        # if self._is_12_plus:
        #     actchan = conn.make_channel(
        #         'com.apple.instruments.server.services.activitytracetap')
        #     conn.call_message(
        #         actchan, 'setConfig:',
        #         [{
        #             'bm': 0,
        #             'excludeDebug': True,
        #             'excludeInfo': True,
        #             'onlySignposts': False,
        #             'predicate': "processID == %d && messageType == 'fault' && subsystem == 'com.apple.runtime-issues'".format(pid),
        #             'ur': 500
        #         }]) # yapf: disable
        #     # start activitytracetap
        #     conn.call_message(actchan, "start", [])

        def _callback(m: DTXMessage):
            # logger.info("output: %s", m.result)
            if m is None:
                logger.warning("WebDriverAgentRunner quitted")
                return
            if m.flags == 0x02:
                method, args = m.result
                if method == 'outputReceived:fromProcess:atTime:':
                    # logger.info("Output: %s", args[0].strip())
                    logger.debug("logProcess: %s", args[0].rstrip())
                    # In low iOS versions, 'Using singleton test manager' may not be printed... mark wda launch status = True if server url has been printed
                    if "ServerURLHere" in args[0]:
                        logger.info("WebDriverAgent start successfully")

        def _log_message_callback(m: DTXMessage):
            identifier, args = m.result
            logger.debug("logConsole: %s", args)

        conn.register_callback("_XCT_logDebugMessage:", _log_message_callback)
        conn.register_callback(Event.NOTIFICATION, _callback)
        if quit_event:
            conn.register_callback(Event.FINISHED, lambda _: quit_event.set())
        return conn, pid

    def major_version(self) -> int:
        version = self.get_value("ProductVersion")
        logger.debug("ProductVersion: %s", version)
        return int(version.split(".")[0])

    def _fnmatch_find_bundle_id(self, bundle_id: str) -> str:
        bundle_ids = []
        for binfo in self.installation.iter_installed(
                attrs=['CFBundleIdentifier']):
            if fnmatch.fnmatch(binfo['CFBundleIdentifier'], bundle_id):
                bundle_ids.append(binfo['CFBundleIdentifier'])
        if not bundle_ids:
            raise MuxError("No app matches", bundle_id)

        # use irma first
        bundle_ids.sort(
            key=lambda v: v != 'com.facebook.wda.irmarunner.xctrunner')
        return bundle_ids[0]

    def xctest(self, fuzzy_bundle_id="com.*.xctrunner", target_bundle_id=None, logger=None, env: dict={}):
        """ Alias of xcuitest """
        bundle_id = self._fnmatch_find_bundle_id(fuzzy_bundle_id)
        logger.info("BundleID: %s", bundle_id)
        return self.xcuitest(bundle_id, target_bundle_id=target_bundle_id, logger=logger, env=env)

    def xcuitest(self, bundle_id, target_bundle_id=None, logger=None, env: dict={}):
        """
        Launch xctrunner and wait until quit

        Args:
            bundle_id (str): xctrunner bundle id
            target_bundle_id (str): optional, launch WDA-UITests will not need it
            env: launch env
        """
        if not logger:
            logger = setup_logger(level=logging.INFO)

        product_version = self.get_value("ProductVersion")
        logger.info("ProductVersion: %s", product_version)
        logger.info("DeviceIdentifier: %s", self.udid)

        XCODE_VERSION = 29
        session_identifier = uuid.uuid4()

        # when connections closes, this event will be set
        quit_event = threading.Event()

        ##
        ## IDE 1st connection
        x1 = self._connect_testmanagerd_lockdown()

        # index: 427
        x1_daemon_chan = x1.make_channel(
            'dtxproxy:XCTestManager_IDEInterface:XCTestManager_DaemonConnectionInterface'
        )

        if self.major_version() >= 11:
            identifier = '_IDE_initiateControlSessionWithProtocolVersion:'
            aux = AUXMessageBuffer()
            aux.append_obj(XCODE_VERSION)
            result = x1.call_message(x1_daemon_chan, identifier, aux)
            logger.debug("result: %s", result)
        x1.register_callback(Event.FINISHED, lambda _: quit_event.set())

        ##
        ## IDE 2nd connection
        x2 = self._connect_testmanagerd_lockdown()
        x2_deamon_chan = x2.make_channel(
            'dtxproxy:XCTestManager_IDEInterface:XCTestManager_DaemonConnectionInterface'
        )
        x2.register_callback(Event.FINISHED, lambda _: quit_event.set())
        #x2.register_callback("pidDiedCallback:" # maybe no needed

        _start_flag = threading.Event()

        def _start_executing(m: Optional[DTXMessage] = None):
            if _start_flag.is_set():
                return
            _start_flag.set()

            logger.info("Start execute test plan with IDE version: %d",
                        XCODE_VERSION)
            x2.call_message(0xFFFFFFFF, '_IDE_startExecutingTestPlanWithProtocolVersion:', [XCODE_VERSION], expects_reply=False)

        def _show_log_message(m: DTXMessage):
            logger.debug("logMessage: %s", m.result[1])
            if 'Received test runner ready reply with error: (null' in ''.join(
                    m.result[1]):
                logger.info("Test runner ready detected")
                _start_executing()

        x2.register_callback(
            '_XCT_testBundleReadyWithProtocolVersion:minimumVersion:',
            _start_executing)  # This only happends <= iOS 13
        x2.register_callback('_XCT_logDebugMessage:', _show_log_message)

        # index: 469
        identifier = '_IDE_initiateSessionWithIdentifier:forClient:atPath:protocolVersion:'
        aux = AUXMessageBuffer()
        aux.append_obj(session_identifier)
        aux.append_obj(str(session_identifier) + '-6722-000247F15966B083')
        aux.append_obj(
            '/Applications/Xcode.app/Contents/Developer/usr/bin/xcodebuild')
        aux.append_obj(XCODE_VERSION)
        result = x2.call_message(x2_deamon_chan, identifier, aux)
        logger.debug("result: %s", result)

        # launch test app
        # index: 1540
        xclogger = setup_logger(name='xctest')
        _, pid = self._launch_app_runner(bundle_id, session_identifier,
            target_app_bundle_id=target_bundle_id,
            env=env, logger=xclogger)

        # xcode call the following commented method, twice
        # but it seems can be ignored

        # identifier = '_IDE_collectNewCrashReportsInDirectories:matchingProcessNames:'
        # aux = AUXMessageBuffer()
        # aux.append_obj(['/var/mobile/Library/Logs/CrashReporter/'])
        # aux.append_obj(['SpringBoard', 'backboardd', 'xctest'])
        # result = x1.call_message(chan, identifier, aux)
        # logger.debug("result: %s", result)

        # identifier = '_IDE_collectNewCrashReportsInDirectories:matchingProcessNames:'
        # aux = AUXMessageBuffer()
        # aux.append_obj(['/var/mobile/Library/Logs/CrashReporter/'])
        # aux.append_obj(['SpringBoard', 'backboardd', 'xctest'])
        # result = x1.call_message(chan, identifier, aux)
        # logger.debug("result: %s", result)

        # after app launched, operation bellow must be send in 0.1s
        # or wda will launch failed
        if self.major_version() >= 12:
            identifier = '_IDE_authorizeTestSessionWithProcessID:'
            aux = AUXMessageBuffer()
            aux.append_obj(pid)
            result = x1.call_message(x1_daemon_chan, identifier, aux)
            logger.debug("result: %s", result)
        elif self.major_version() <= 9:
            identifier = '_IDE_initiateControlSessionForTestProcessID:'
            aux = AUXMessageBuffer()
            aux.append_obj(pid)
            result = x1.call_message(x1_daemon_chan, identifier, aux)
            logger.debug("result: %s", result)
        else:
            identifier = '_IDE_initiateControlSessionForTestProcessID:protocolVersion:'
            aux = AUXMessageBuffer()
            aux.append_obj(pid)
            aux.append_obj(XCODE_VERSION)
            result = x1.call_message(x1_daemon_chan, identifier, aux)
            logger.debug("result: %s", result)

        if "NSError" in str(result):
            raise RuntimeError("Xcode Invocation Failed: {}".format(result))

        # wait for quit
        # on windows threading.Event.wait can't handle ctrl-c
        while not quit_event.wait(.1):
            pass
        logger.info("xctrunner quited")


Device = BaseDevice
