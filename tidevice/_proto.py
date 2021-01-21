# coding: utf-8
# codeskyblue 2020/06/03
#

__all__ = [
    'Color', 'AFC_MAGIC', 'AFC', 'AFCStatus', 'LOCKDOWN_PORT', 'PROGRAM_NAME',
    'SYSMON_PROC_ATTRS', 'SYSMON_SYS_ATTRS', 'MODELS', 'LockdownService',
    "UsbmuxReplyCode", "InstrumentsService"
]

import enum


class Color(enum.Enum):
    END = '\033[0m'
    BOLD = '\033[1m'

    # Foreground
    BLACK = '\33[30m'
    RED = '\33[31m'
    GREEN = '\33[32m'
    YELLOW = '\33[33m'
    BLUE = '\33[34m'
    VIOLET = '\33[35m'
    BEIGE = '\33[36m'
    WHITE = '\33[37m'

    # Background
    BG_GREEN = '\033[42m'

    @staticmethod
    def wrap_text(text, *colors):
        prefix = ''.join([c.value for c in colors])
        return prefix + text + Color.END.value


SYSMON_PROC_ATTRS = [
    "memVirtualSize",  # vss
    "cpuUsage",
    "ctxSwitch",  # the number of context switches by process each second
    "intWakeups",  # the number of threads wakeups by process each second
    "physFootprint",  # real memory
    "memResidentSize",  # rss
    "memAnon",  # anonymous memory
    "pid"
]

SYSMON_SYS_ATTRS = [
    "vmExtPageCount", "vmFreeCount", "vmPurgeableCount", "vmSpeculativeCount",
    "physMemSize"
]

LOCKDOWN_PORT = 62078
PROGRAM_NAME = "tidevice"

AFC_MAGIC = b"CFA6LPAA"


class AFC(enum.IntEnum):
    OP_INVALID = 0x00000000
    OP_STATUS = 0x00000001
    OP_DATA = 0x00000002  # Data
    OP_READ_DIR = 0x00000003  # ReadDir
    OP_READ_FILE = 0x00000004  # ReadFile
    OP_WRITE_FILE = 0x00000005  # WriteFile
    OP_WRITE_PART = 0x00000006  # WritePart
    OP_TRUNCATE = 0x00000007  # TruncateFile
    OP_REMOVE_PATH = 0x00000008  # RemovePath
    OP_MAKE_DIR = 0x00000009  # MakeDir
    OP_GET_FILE_INFO = 0x0000000a  # GetFileInfo
    OP_GET_DEVINFO = 0x0000000b  # GetDeviceInfo
    OP_WRITE_FILE_ATOM = 0x0000000c  # WriteFileAtomic (tmp file+rename)
    OP_FILE_OPEN = 0x0000000d  # FileRefOpen
    OP_FILE_OPEN_RES = 0x0000000e  # FileRefOpenResult
    OP_READ = 0x0000000f  # FileRefRead
    OP_WRITE = 0x00000010  # FileRefWrite
    OP_FILE_SEEK = 0x00000011  # FileRefSeek
    OP_FILE_TELL = 0x00000012  # FileRefTell
    OP_FILE_TELL_RES = 0x00000013  # FileRefTellResult
    OP_FILE_CLOSE = 0x00000014  # FileRefClose
    OP_FILE_SET_SIZE = 0x00000015  # FileRefSetFileSize (ftruncate)
    OP_GET_CON_INFO = 0x00000016  # GetConnectionInfo
    OP_SET_CON_OPTIONS = 0x00000017  # SetConnectionOptions
    OP_RENAME_PATH = 0x00000018  # RenamePath
    OP_SET_FS_BS = 0x00000019  # SetFSBlockSize (0x800000)
    OP_SET_SOCKET_BS = 0x0000001A  # SetSocketBlockSize (0x800000)
    OP_FILE_LOCK = 0x0000001B  # FileRefLock
    OP_MAKE_LINK = 0x0000001C  # MakeLink
    OP_SET_FILE_TIME = 0x0000001E  # set st_mtime
    OP_GET_FILE_HASH_RANGE = 0x0000001F  # GetFileHashWithRange

    O_RDONLY = 0x00000001  #/**< r   O_RDONLY
    O_RW = 0x00000002  #/**< r+  O_RDWR   | O_CREAT
    O_WRONLY = 0x00000003  #/**< w   O_WRONLY | O_CREAT  | O_TRUNC
    O_WR = 0x00000004  #/**< w+  O_RDWR   | O_CREAT  | O_TRUNC
    O_APPEND = 0x00000005  #/**< a   O_WRONLY | O_APPEND | O_CREAT
    O_RDAPPEND = 0x00000006  #/**< a+  O_RDWR   | O_APPEND | O_CREAT

    HARDLINK = 1
    SYMLINK = 2

    LOCK_SH = 1 | 4  #/**< shared lock
    LOCK_EX = 2 | 4  #/**< exclusive lock
    LOCK_UN = 8 | 4  #/**< unlock

    # #// Status
    # ST_SUCCESS                = 0
    # ST_UNKNOWN_ERROR          = 1
    # ST_OP_HEADER_INVALID      = 2
    # ST_NO_RESOURCES           = 3
    # ST_READ_ERROR             = 4
    # ST_WRITE_ERROR            = 5
    # ST_UNKNOWN_PACKET_TYPE    = 6
    # ST_INVALID_ARG            = 7
    # ST_OBJECT_NOT_FOUND       = 8
    # ST_OBJECT_IS_DIR          = 9
    # ST_PERM_DENIED            =10
    # ST_SERVICE_NOT_CONNECTED  =11
    # ST_OP_TIMEOUT             =12
    # ST_TOO_MUCH_DATA          =13
    # ST_END_OF_DATA            =14
    # ST_OP_NOT_SUPPORTED       =15
    # ST_OBJECT_EXISTS          =16
    # ST_OBJECT_BUSY            =17
    # ST_NO_SPACE_LEFT          =18
    # ST_OP_WOULD_BLOCK         =19
    # ST_IO_ERROR               =20
    # ST_OP_INTERRUPTED         =21
    # ST_OP_IN_PROGRESS         =22
    # ST_INTERNAL_ERROR         =23

    # ST_MUX_ERROR              =30
    # ST_NO_MEM                 =31
    # ST_NOT_ENOUGH_DATA        =32
    # ST_DIR_NOT_EMPTY          =33


@enum.unique
class AFCStatus(enum.IntEnum):
    SUCCESS = 0
    UNKNOWN_ERROR = 1
    OP_HEADER_INVALID = 2
    NO_RESOURCES = 3
    READ_ERROR = 4
    WRITE_ERROR = 5
    UNKNOWN_PACKET_TYPE = 6
    INVALID_ARG = 7
    OBJECT_NOT_FOUND = 8
    OBJECT_IS_DIR = 9
    PERM_DENIED = 10
    SERVICE_NOT_CONNECTED = 11
    OP_TIMEOUT = 12
    TOO_MUCH_DATA = 13
    END_OF_DATA = 14
    OP_NOT_SUPPORTED = 15
    OBJECT_EXISTS = 16
    OBJECT_BUSY = 17
    NO_SPACE_LEFT = 18
    OP_WOULD_BLOCK = 19
    IO_ERROR = 20
    OP_INTERRUPTED = 21
    OP_IN_PROGRESS = 22
    INTERNAL_ERROR = 23

    MUX_ERROR = 30
    NO_MEM = 31
    NOT_ENOUGH_DATA = 32
    DIR_NOT_EMPTY = 33


MODELS = {
    "iPhone5,1": "iPhone 5",
    "iPhone5,2": "iPhone 5",
    "iPhone5,3": "iPhone 5c",
    "iPhone5,4": "iPhone 5c",
    "iPhone6,1": "iPhone 5s",
    "iPhone6,2": "iPhone 5s",
    "iPhone7,1": "iPhone 6 Plus",
    "iPhone7,2": "iPhone 6",
    "iPhone8,1": "iPhone 6s",
    "iPhone8,2": "iPhone 6s Plus",
    "iPhone8,4": "iPhone SE",
    "iPhone9,1": "iPhone 7",  # Global
    "iPhone9,2": "iPhone 7 Plus",  # Global
    "iPhone9,3": "iPhone 7",  # GSM
    "iPhone9,4": "iPhone 7 Plus",  # GSM
    "iPhone10,1": "iPhone 8",  # Global
    "iPhone10,2": "iPhone 8 Plus",  # Global
    "iPhone10,3": "iPhone X",  # Global
    "iPhone10,4": "iPhone 8",  # GSM
    "iPhone10,5": "iPhone 8 Plus",  # GSM
    "iPhone10,6": "iPhone X",  # GSM
    "iPhone11,8": "iPhone XR",
    "iPhone11,2": "iPhone XS",
    "iPhone11,4": "iPhone XS Max",
    "iPhone11,6": "iPhone XS Max",
    "iPhone11,8": "iPhone XR",
    "iPhone12,1": "iPhone 11",
    "iPhone12,3": "iPhone 11 Pro",
    "iPhone12,5": "iPhone 11 Pro Max",
    "iPhone12,8": "iPhone SE 2nd",
    # simulator
    "i386": "iPhone Simulator",
    "x86_64": "iPhone Simulator",
}


class UsbmuxMessageType(str, enum.Enum):
    Attached = "Attached"
    Detached = "Detached"


class LockdownService(str, enum.Enum):
    # hdiutil mount /Applications/Xcode.app/Contents/Developer/Platforms/iPhoneOS.platform/DeviceSupport/14.0/DeveloperDiskImage.dmg
    # tree /Volumes/DeveloperDiskImage/Library/Lockdown
    MobileLockdown = 'com.apple.mobile.lockdown'

    # Ref: https://github.com/anonymous5l/iConsole/blob/master/wifiSync.go
    MobileWirelessLockdown = "com.apple.mobile.wireless_lockdown"

    MobileScreenshotr = "com.apple.mobile.screenshotr"  # 截图服务
    MobileHouseArrest = "com.apple.mobile.house_arrest"  # 访问文件内的沙箱
    AFC = "com.apple.afc"  # 访问系统资源

    InstrumentsRemoteServer = "com.apple.instruments.remoteserver"
    InstrumentsRemoteServerSecure = "com.apple.instruments.remoteserver.DVTSecureSocketProxy"  # for iOS 14.0
    TestmanagerdLockdown = "com.apple.testmanagerd.lockdown"
    TestmanagerdLockdownSecure = "com.apple.testmanagerd.lockdown.secure"  # for iOS 14.0


class InstrumentsService(str, enum.Enum):
    DeviceInfo = 'com.apple.instruments.server.services.deviceinfo'
    ProcessControl = "com.apple.instruments.server.services.processcontrol"
    DeviceApplictionListing = "com.apple.instruments.server.services.device.applictionListing"
    GraphicsOpengl = "com.apple.instruments.server.services.graphics.opengl"  # 获取FPS
    Sysmontap = "com.apple.instruments.server.services.sysmontap"  # 获取性能数据用
    XcodeNetworkStatistics = 'com.apple.xcode.debug-gauge-data-providers.NetworkStatistics'  # 获取单进程网络数据
    Networking = 'com.apple.instruments.server.services.networking'  # 全局网络数据 instruments 用的就是这个
    MobileNotifications = 'com.apple.instruments.server.services.mobilenotifications'  # 监控应用状态


class UsbmuxReplyCode(int, enum.Enum):
    OK = 0
    BadCommand = 1
    BadDevice = 2
    ConnectionRefused = 3
    BadVersion = 6


if __name__ == "__main__":
    print(Color.wrap_text("Hello", Color.RED))
    print(AFC.GET_DEVINFO)
