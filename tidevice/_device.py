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
import pprint
import re
import ssl
import sys
import shutil
import subprocess
import tempfile
import threading
import time
import typing
import urllib.request
import uuid
from collections import namedtuple
from typing import Iterator, Optional, Tuple, Union

import requests
from cached_property import cached_property
from logzero import setup_logger
from PIL import Image

from . import bplist
from ._imagemounter import ImageMounter
from ._installation import Installation
from ._instruments import (AUXMessageBuffer, DTXMessage, DTXService, Event,
                           ServiceInstruments)
from ._ipautil import IPAReader
from ._proto import *
from ._safe_socket import *
from ._sync import Sync
from ._usbmux import Usbmux
from ._utils import ProgressReader, get_app_dir, get_binary_by_name
from .exceptions import *

logger = setup_logger(PROGRAM_NAME,
    level=logging.DEBUG if os.getenv("DEBUG") else logging.INFO)


def pil_imread(data: Union[str, bytes, bytearray]) -> Image.Image:
    """ Convert data to PIL.Image.Image """
    if isinstance(data, (bytes, bytearray)):
        memory_fd = io.BytesIO(data)
        im = Image.open(memory_fd)
        im.load()
        del (memory_fd)
        del (data)
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
        self._info = self.info
        self._lock = threading.Lock()
        self._pair_record = None

    @property
    def usbmux(self) -> Usbmux:
        return self._usbmux

    @cached_property
    def info(self) -> dict:
        """
        Example return:
        {
            "SerialNumber": "xxxx", # udid
            "DeviceID": 12,
        }
        """
        devices = self._usbmux.device_list()
        if not self._udid:
            assert len(
                devices
            ) == 1, "Device is not present or multi devices connected"
            _d = devices[0]
            self._udid = _d['SerialNumber']
            return _d
        else:
            for d in devices:
                if d['SerialNumber'] == self._udid:
                    return d
        raise MuxError("Device: {} not ready".format(self._udid))

    def is_connected(self) -> bool:
        return self.udid in self.usbmux.device_udid_list()

    @property
    def udid(self) -> str:
        return self._udid

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
        iconsole_path = get_binary_by_name("iconsole")
        if not os.path.isfile(iconsole_path):
            raise MuxError("Unable to pair without iconsole")
        output = subprocess.check_output([iconsole_path, 'afc', '-u', self.udid, 'space']).decode('utf-8')
        if 'TotalSpace:' not in output:
            raise MuxError("Pair: " + output)

    def handshake(self):
        """
        set self._pair_record
        """
        try:
            self._pair_record = self._read_pair_record()
        except MuxReplyError as err:
            if err.reply_code == UsbmuxReplyCode.BadDevice:
                self.pair()
                self._pair_record = self._read_pair_record()

    @property
    def ssl_pemfile_path(self):
        with self._lock:
            appdir = get_app_dir("ssl", create_dir=True)
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
            _ssl: bool = False) -> PlistSocket:
        # I really donot know why do this
        # The following code convert port(0x1234) to port(0x3412)
        _port = ((port & 0xff) << 8) | (port >> 8)
        # logger.debug("port convert %s(%d) -> %s(%d)", hex(port), port,
        #              hex(_port), _port)
        del (port)

        device_id = self.info['DeviceID']
        conn = self._usbmux.create_connection()
        payload = {
            'DeviceID': device_id,  # Required
            'MessageType': 'Connect',  # Required
            'PortNumber': _port,  # Required
            'ProgName': PROGRAM_NAME,
        }
        logger.debug("Send payload: %s", payload)
        data = conn.send_recv_packet(payload)
        logger.debug("connect port: %d", _port)
        self._usbmux._check(data)

        if _ssl:
            conn.switch_to_ssl(self.ssl_pemfile_path)
        return conn

    @contextlib.contextmanager
    def create_session(self) -> PlistSocket:
        """
        Create session inside SSLContext
        """
        with self.create_inner_connection() as s:  # 62078=0xf27e
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
                s.switch_to_ssl(self.ssl_pemfile_path)

            yield s

            s.send_packet({
                "Request": "StopSession",
                "SessionID": session_id,
            })
            s.recv_packet()

    def device_info(self, domain: Optional[str] = None) -> dict:
        """
        Args:
            domain: can be found in "ideviceinfo -h", eg: com.apple.disk_usage
        """
        with self.create_session() as conn:
            packet = {
                "Request": "GetValue",
                "Label": PROGRAM_NAME,
            }
            if domain:
                packet["Domain"] = domain
            ret = conn.send_recv_packet(packet)
            return ret['Value']

    def get_value(self, key: str, no_session: bool = False):
        """ key can be: ProductVersion
        Args:
            no_session: set to True when not paired
        """
        if no_session:
            with self.create_inner_connection() as s:
                ret = s.send_recv_packet({
                    "Request": "GetValue",
                    "Key": key,
                    "Label": PROGRAM_NAME,
                })
                return ret['Value']
        else:
            with self.create_session() as conn:
                ret = conn.send_recv_packet({
                    "Request": "GetValue",
                    "Key": key,
                    "Label": PROGRAM_NAME,
                })
                return ret['Value']

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

    def get_io_power(self) -> dict:
        conn = self.start_service("com.apple.mobile.diagnostics_relay")
        ret = conn.send_recv_packet({
            'EntryClass': 'IOPMPowerSource',
            'Request': 'IORegistry',
            "Label": PROGRAM_NAME,
        })
        return ret

    def get_io_registry(self, name: str) -> dict:
        conn = self.start_service("com.apple.mobile.diagnostics_relay")
        ret = conn.send_recv_packet({
            'Request': 'IORegistry',
            'EntryClass': name,
            "Label": PROGRAM_NAME,
        })
        return ret

    def start_service(self, name: str) -> PlistSocket:
        try:
            return self._unsafe_start_service(name)
        except MuxServiceError:
            self.mount_developer_image()
            # maybe should wait here
            time.sleep(.5)
            return self._unsafe_start_service(name)

    def _unsafe_start_service(self, name: str) -> PlistSocket:
        with self.create_session() as s:
            data = s.send_recv_packet({
                "Request": "StartService",
                "Service": name,
                "Label": PROGRAM_NAME,
            })
            if 'Error' in data:  # data['Error'] is InvalidService
                raise MuxServiceError("Could not start service: {0}! {2}".format(
                    name, data['Error'],
                    "Remember that you have to mount the Developer disk image on your device"
                ))

        # Expect recv
        # {'EnableServiceSSL': True,
        #  'Port': 53428,
        #  'Request': 'StartService',
        #  'Service': 'com.apple.xxx'}
        assert data['Service'] == name
        _ssl = data.get(
            'EnableServiceSSL',
            False)  # and name != "com.apple.instruments.remoteserver"
        conn = self.create_inner_connection(data['Port'], _ssl=_ssl)
        return conn

    def screenshot(self) -> Image.Image:
        return next(self.iter_screenshot())

    def iter_screenshot(self) -> Iterator[Image.Image]:
        """ take screenshot infinite """
        with self.start_service(LockdownService.MobileScreenshotr) as conn:
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
        with self.create_inner_connection() as s:
            data = s.send_recv_packet({
                'Request': 'GetValue',
                'Key': 'DeviceName',
                'Label': PROGRAM_NAME,
            })
            return data['Value']

    def app_sync(self, bundle_id: str) -> Sync:
        # 'com.facebook.WebDriverAgentRunner.xctrunner'
        conn = self.start_service(LockdownService.MobileHouseArrest)
        conn.send_packet({
            "Command": "VendContainer",
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

    def _get_developer_image_path(self):
        # use local path first
        # use download cache resource second
        # download from network third
        product_version = self.get_value("ProductVersion")
        logger.info("ProductVersion: %s", product_version)
        major, minor = product_version.split(".")[:2]
        version = major + "." + minor

        mac_developer_dir = "/Applications/Xcode.app/Contents/Developer/Platforms/iPhoneOS.platform/DeviceSupport"
        image_path = os.path.join(mac_developer_dir, version,
                                  "DeveloperDiskImage.dmg")
        signature_path = image_path + ".signature"
        if os.path.isfile(image_path) and os.path.isfile(signature_path):
            return image_path, signature_path

        raise NotImplementedError("Download DeveloperDiskImage.dmg from web is not ready yet")
        # # not ready yet
        # # download from github binaries
        # image_url = f"https://github.com/alibaba/tidevice/releases/download/device-support/iphoneos-{version}.zip"
        # signature_url = image_url + ".signature"

        # app_dir = get_app_dir("DeviceSupport/iPhoneOS",
        #                       version,
        #                       create_dir=True)
        # image_path = app_dir + "/DeveloperDiskImage.dmg"
        # signature_path = image_path + ".signature"

        # # no caches
        # if not os.path.exists(image_path) or not os.path.exists(
        #         signature_path):
        #     logger.info("Downloading developer image")
        #     urllib.request.urlretrieve(image_url, image_path)
        #     urllib.request.urlretrieve(signature_url, signature_path)
        # return image_path, signature_path

    def mount_developer_image(self):
        """
        Raises:
            MuxError
        """
        signatures = self.imagemounter.lookup()
        if signatures:
            logger.info("DeveloperImage already mounted")
            return

        image_path, signature_path = self._get_developer_image_path()
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
        instruments = self.connect_instruments()
        if isinstance(pid_or_name, int):
            instruments.app_kill(pid_or_name)
            return pid_or_name
        elif isinstance(pid_or_name, str):
            bundle_id = pid_or_name
            app_infos = list(self.installation.iter_installed(app_type=None))
            ps = instruments.app_process_list(app_infos)
            for p in ps:
                if p['bundle_id'] == bundle_id:
                    instruments.app_kill(p['pid'])
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
        instruments = self.connect_instruments()
        return instruments.app_launch(bundle_id,
                                           args=args,
                                           kill_running=kill_running)

    def app_install(self, file_or_url: Union[str, typing.IO]):
        """
        Args:
            file_or_url: local path or url

        Returns:
            bundle_id

        Raises:
            ServiceError

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
        with tempfile.TemporaryDirectory() as tmpdir:
            if is_url:
                url = file_or_url
                filepath = os.path.join(tmpdir, url.split("/")[-1])
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
                raise RuntimeError(
                    "Local path {} not exist".format(file_or_url))

            conn = self.start_service(LockdownService.AFC)
            afc = Sync(conn)

            ipa_tmp_dir = "PublicStaging"
            if not afc.exists(ipa_tmp_dir):
                afc.mkdir(ipa_tmp_dir)
            ir = IPAReader(filepath)
            bundle_id = ir.get_bundle_id()
            ir.close()

            print("Copying {!r} to device...".format(filepath), end=" ")
            sys.stdout.flush()
            target_path = ipa_tmp_dir + "/" + bundle_id + ".ipa"

            filesize = os.path.getsize(filepath)
            with open(filepath, 'rb') as f:
                preader = ProgressReader(f, filesize)
                afc.push_content(target_path, preader)
            preader.finish()
            print("DONE.")

            print("Installing {!r}".format(bundle_id))
            inst = self.installation
            inst.send_packet({
                'Command': 'Install',
                'ClientOptions': {
                    'CFBundleIdentifier': bundle_id,
                },
                'PackagePath': target_path
            })
            while True:
                progress = inst.recv_packet()
                if progress.get("Status") == 'Complete':
                    print("Complete")
                    return bundle_id
                if 'Error' in progress:
                    logger.error("%s", progress['Error'])
                    logger.error("%s", progress.get("ErrorDescription"))
                    raise ServiceError(progress['Error'])
                print("- {Status} ({PercentComplete}%)".format(**progress))

    def app_uninstall(self, bundle_id: str) -> bool:
        """
        Note: It seems always return True
        """
        ins = self.installation
        ins.send_packet({
            "Command": "Uninstall",
            "ApplicationIdentifier": bundle_id
        })
        print("Uninstalling {!r}".format(bundle_id))
        while True:
            data = ins.recv_packet()
            if data.get("Status") == 'Complete':
                print("Complete")
                return True
            if 'Error' in data:
                logger.error("%s", data['Error'])
                logger.error("%s", data.get("ErrorDescription"))
                return False
            print("- {Status} ({PercentComplete}%)".format(**data))

    def _connect_testmanagerd_lockdown(self):
        if self.major_version() >= 14:
            conn = self.start_service(
                LockdownService.TestmanagerdLockdownSecure)
        else:
            conn = self.start_service(LockdownService.TestmanagerdLockdown)
            if isinstance(conn._sock, ssl.SSLSocket):
                conn._sock = conn._dup_sock
        return DTXService(conn)

    def connect_instruments(self) -> ServiceInstruments:
        """ start service for instruments """
        if self.major_version() >= 14:
            conn = self.start_service(
                LockdownService.InstrumentsRemoteServerSecure)
        else:
            conn = self.start_service(LockdownService.InstrumentsRemoteServer)
            # When SSL-handshake done, goback to original socket
            if isinstance(conn._sock, ssl.SSLSocket):
                conn._sock = conn._dup_sock
        return ServiceInstruments(conn)

    @property
    def instruments(self) -> ServiceInstruments:
        return self.connect_instruments()

    def _launch_wda(self,
                    bundle_id: str,
                    session_identifier: uuid.UUID,
                    logger: logging.Logger = logging,
                    quit_event: threading.Event = None) -> int:  # pid

        app_info = self.installation.lookup(bundle_id)
        sign_identity = app_info.get("SignerIdentity", "")
        logger.info("SignIdentity: %r", sign_identity)

        app_container = app_info['Container']

        xctest_path = "/tmp/WebDriverAgentRunner-" + str(session_identifier).upper() + ".xctestconfiguration" # yapf: disable
        xctest_content = bplist.objc_encode(bplist.XCTestConfiguration({
            "testBundleURL": bplist.NSURL(None, "file://" + app_info['Path'] + "/PlugIns/WebDriverAgentRunner.xctest"),
            "sessionIdentifier": session_identifier,
        })) # yapf: disable

        fsync = self.app_sync(bundle_id)
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
        logger.debug("AppContainer: %s", app_container)
        app_env = {
            'CA_ASSERT_MAIN_THREAD_TRANSACTIONS': '0',
            'CA_DEBUG_TRANSACTIONS': '0',
            'DYLD_FRAMEWORK_PATH': app_path + '/Frameworks:',
            'DYLD_LIBRARY_PATH': app_path + '/Frameworks',
            'NSUnbufferedIO': 'YES',
            'OS_ACTIVITY_DT_MODE': 'YES',
            'SQLITE_ENABLE_THREAD_ASSERTIONS': '1',
            'WDA_PRODUCT_BUNDLE_IDENTIFIER': '',
            'XCTestConfigurationFilePath': xctestconfiguration_path,
            'XCODE_DBG_XPC_EXCLUSIONS': 'com.apple.dt.xctestSymbolicator',
            # '__XCODE_BUILT_PRODUCTS_DIR_PATHS': '/tmp/derivedDataPath/Build/Products/Release-iphoneos',
            # '__XPC_DYLD_FRAMEWORK_PATH': '/tmp/derivedDataPath/Build/Products/Release-iphoneos',
            # '__XPC_DYLD_LIBRARY_PATH': '/tmp/derivedDataPath/Build/Products/Release-iphoneos',
            # iOS 11
            'DYLD_INSERT_LIBRARIES': '/Developer/usr/lib/libMainThreadChecker.dylib',
            'MJPEG_SERVER_PORT': '',
            'USE_PORT': '',
        } # yapf: disable

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
                    logger.debug("Output: %s", args[0].strip())
                    if "Using singleton test manager" in args[0]:
                        logger.info("WebDriverAgent start successfully")

        conn.register_callback(Event.NOTIFICATION, _callback)
        if quit_event:
            conn.register_callback(Event.FINISHED, lambda _: quit_event.set())
        return pid

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

    def xctest(self, bundle_id="com.facebook.*.xctrunner", logger=None):
        """
        Launch xctrunner and wait until quit
        """
        if not logger:
            logger = setup_logger(level=logging.INFO)
        
        bundle_id = self._fnmatch_find_bundle_id(bundle_id)
        logger.info("BundleID: %s", bundle_id)

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

        pid = self._launch_wda(bundle_id, session_identifier, logger)

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

        # index: 1558
        product_version = self.get_value("ProductVersion")
        logger.info("ProductVersion: %s", product_version)
        # return int(version.split(".")[0]) >= 12

        if self.major_version() >= 12:
            identifier = '_IDE_authorizeTestSessionWithProcessID:'
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

        # wait for quit
        # on windows threading.Event.wait can't handle ctrl-c
        while not quit_event.wait(.1):
            pass
        logger.warning("xctrunner quited")


Device = BaseDevice