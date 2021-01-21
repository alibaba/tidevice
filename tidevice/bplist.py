# Alternatives
# - https://github.com/cclgroupltd/ccl-bplist
# - https://github.com/xa4a/bpylist2
# - https://github.com/xa4a/bpylist2/blob/master/bpylist/archiver.py

import copy
import uuid
import pprint
import datetime
from typing import Any, Union, List
from .plistlib2 import (InvalidFileException,
                        load, dump, loads, dumps,
                        FMT_BINARY, FMT_XML, UID) # yapf: disable

class DecodeNotSupportedError(Exception):
    pass


class InvalidNSKeyedArchiverFormat(Exception):
    """ Not a valid format NSKeyedArchiver """
    pass


class DTSysmonTapMessage:
    """ Usally point to a NSDictionary """
    pass


class NSIgnore:
    """ Just don't parse it """
    pass


class NSBaseObject(object):
    @staticmethod
    def encode(objects: list, value: Any):
        raise NotImplementedError()


class NSError(Exception):
    def __init__(self, code, domain, user_info):
        self.code = code  # eg: 1
        self.domain = domain  # eg: DTXMessage
        self.user_info = user_info  # eg: {'NSLocalizedDescription': 'Unable to invoke -[<D'}

    def __str__(self):
        return "NSError(CODE:{} DOMAIN:{} INFO:{})".format(
            self.code, self.domain,
            pprint.pformat(self.user_info))  #['NSLocalizedDescription'])

    def __repr__(self):
        return str(self)

    @staticmethod
    def decode(objects: list, ns_info: dict):
        code = ns_info['NSCode']
        domain = _parse_object(objects, ns_info['NSDomain'])
        user_info = _parse_object(objects, ns_info['NSUserInfo'])
        return NSError(code, domain, user_info)


class NSNull(NSBaseObject):
    """
    NSNull() always return the same instance
    """

    _instance = None

    def __new__(cls):
        if not NSNull._instance:
            NSNull._instance = super().__new__(cls)
        return NSNull._instance

    def __bool__(self):
        return False
        
    @staticmethod
    def encode(objects: list, value: Union[int, str]):
        ns_info = {}
        objects.append(ns_info)
        ns_info['$class'] = UID(len(objects))
        objects.append({
            "$classname": "NSNull",
            "$classes": ["NSNull", "NSObject"],
        })


class NSObject(NSBaseObject):
    @staticmethod
    def encode(objects: list, value: Union[int, str]):
        if not isinstance(value, (int, str)):
            raise ValueError("NSObject not supported encode value", value,
                             type(value))
        objects.append(value)


class NSSet(NSBaseObject, set):
    @staticmethod
    def encode(objects, value: set):
        ns_objs = []
        ns_info = {
            "NS.objects": ns_objs,
        }
        objects.append(ns_info)
        for v in value:
            uid = _encode_any(objects, v)
            ns_objs.append(uid)

        ns_info['$class'] = UID(len(objects))
        objects.append({
            "$classname": "NSSet",
            "$classes": ["NSSet", "NSObject"],
        })


class NSArray(NSBaseObject, list):
    @staticmethod
    def encode(objects: list, value: List[Any]):
        ns_objs = []
        ns_info = {
            "NS.objects": ns_objs,
        }
        objects.append(ns_info)

        for v in value:
            uid = _encode_any(objects, v)
            ns_objs.append(uid)

        ns_info["$class"] = UID(len(objects))
        objects.append({
            "$classname": "NSArray",
            "$classes": ["NSArray", "NSObject"],
        })


class NSDictionary(NSBaseObject, dict):
    @staticmethod
    def encode(objects: list, value: dict):
        ns_keys = []
        ns_objs = []

        ns_info = {
            "NS.keys": ns_keys,
            "NS.objects": ns_objs,
        }
        objects.append(ns_info)

        for k, v in value.items():
            ns_keys.append(UID(len(objects)))
            objects.append(k)

            uid = _encode_any(objects, v)
            ns_objs.append(uid)

        ns_info["$class"] = UID(len(objects))
        objects.append({
            "$classname": "NSDictionary",
            "$classes": ["NSDictionary", "NSObject"],
        })


class XCTestConfiguration(NSBaseObject):
    _default = {
        # 'testBundleURL': UID(3), # NSURL(None, file:///private/var/containers/Bundle/.../WebDriverAgentRunner-Runner.app/PlugIns/WebDriverAgentRunner.xctest)
        # 'sessionIdentifier': UID(8), # UUID
        'aggregateStatisticsBeforeCrash': {
            'XCSuiteRecordsKey': {}
        },
        'automationFrameworkPath': '/Developer/Library/PrivateFrameworks/XCTAutomationSupport.framework',
        'baselineFileRelativePath': None,
        'baselineFileURL': None,
        'defaultTestExecutionTimeAllowance': None,
        'disablePerformanceMetrics': False,
        'emitOSLogs': False,
        'formatVersion': 2,  # store in UID
        'gatherLocalizableStringsData': False,
        'initializeForUITesting': True,
        'maximumTestExecutionTimeAllowance': None,
        'productModuleName': "WebDriverAgentRunner",  # set to other value is also OK
        'randomExecutionOrderingSeed': None,
        'reportActivities': True,
        'reportResultsToIDE': True,
        'systemAttachmentLifetime': 2,
        'targetApplicationArguments': [],  # maybe useless
        'targetApplicationBundleID': None,
        'targetApplicationEnvironment': None,
        'targetApplicationPath': None,
        'testApplicationDependencies': {},
        'testApplicationUserOverrides': None,
        'testBundleRelativePath': None,
        'testExecutionOrdering': 0,
        'testTimeoutsEnabled': False,
        'testsDrivenByIDE': False,
        'testsMustRunOnMainThread': True,
        'testsToRun': None,
        'testsToSkip': None,
        'treatMissingBaselinesAsFailures': False,
        'userAttachmentLifetime': 1
    }

    def __init__(self, kv: dict):
        # self._kv = kv
        assert 'testBundleURL' in kv and isinstance(kv['testBundleURL'], NSURL)
        assert 'sessionIdentifier' in kv and isinstance(
            kv['sessionIdentifier'], uuid.UUID)

        self._kv = copy.deepcopy(self._default)
        self._kv.update(kv)

    def __str__(self):
        return "XCTestConfiguration(" + pprint.pformat(self._kv) + ")"

    def __repr__(self):
        return self.__str__()

    def __eq__(self, other):
        return self._kv == other._kv

    def __setitem__(self, key: str, val: Any):
        assert isinstance(key, str)
        self._kv[key] = val

    @staticmethod
    def encode(objects: list, value):
        ns_info = {}
        objects.append(ns_info)
        ns_info['$class'] = UID(len(objects))
        objects.append({
            '$classes': ["XCTestConfiguration", 'NSObject'],
            '$classname': "XCTestConfiguration"
        })
        for (k, v) in value._kv.items():
            if k not in ['formatVersion'] and isinstance(v, (bool, int)):
                ns_info[k] = v
            else:
                ns_info[k] = _encode_any(objects, v)

    @staticmethod
    def decode(objects: list, ns_info: dict):
        info = ns_info.copy()
        info.pop("$class")
        for key in info.keys():
            idx = info[key]
            if isinstance(idx, UID):
                info[key] = _parse_object(objects, idx.data)
        return XCTestConfiguration(info)


class DTActivityTraceTapMessage(NSBaseObject):
    def __init__(self, tap_message: dict):
        self._tap_message = tap_message

    def __str__(self):
        return "DTActivityTraceTapMessage - " + pprint.pformat(
            self._tap_message)

    @staticmethod
    def decode(objects: list, ns_info: dict):
        tap_message = _parse_object(objects, ns_info['DTTapMessagePlist'])
        return DTActivityTraceTapMessage(tap_message)


class NSString(NSBaseObject, str):
    @staticmethod
    def decode(objects: list, ns_info: dict) -> str:
        return NSString(ns_info['NS.string'])


class NSUUID(NSBaseObject, uuid.UUID):
    @staticmethod
    def encode(objects: list, value: uuid.UUID):
        ns_info = {
            "NS.uuidbytes": value.bytes,
        }
        objects.append(ns_info)
        ns_info['$class'] = UID(len(objects))
        objects.append({
            '$classes': ['NSUUID', 'NSObject'],
            '$classname': 'NSUUID'
        })

    @staticmethod
    def decode(objects: list, ns_info: dict) -> uuid.UUID:
        return uuid.UUID(bytes=ns_info['NS.uuidbytes'])


class NSURL(NSBaseObject):
    def __init__(self, base, relative):
        self._base = base
        self._relative = relative

    def __eq__(self, other) -> bool:
        return self._base == other._base and self._relative == other._relative

    def __str__(self):
        return "NSURL({}, {})".format(self._base, self._relative)

    def __repr__(self):
        return self.__str__()

    @staticmethod
    def encode(objects: list, value):
        ns_info = {}
        objects.append(ns_info)

        ns_info['NS.base'] = _encode_any(objects, value._base)
        ns_info['NS.relative'] = _encode_any(objects, value._relative)

        ns_info['$class'] = UID(len(objects))
        objects.append({
            '$classes': ['NSURL', 'NSObject'],
            '$classname': 'NSURL'
        })

    @staticmethod
    def decode(objects: list, ns_info: dict):
        base = _parse_object(objects, ns_info['NS.base'])
        relative = _parse_object(objects, ns_info['NS.relative'])
        return NSURL(base, relative)


# DTActivityTraceTapMessage
# NotImplementedError: 'DTActivityTraceTapMessage' decode not supported
#   ns_info: {'$class': UID(6), 'DTTapMessagePlist': UID(2)}
#   ns_objects: [   '$null',
#     {'$class': UID(6), 'DTTapMessagePlist': UID(2)},
#     {'$class': UID(5), 'NS.keys': [UID(3)], 'NS.objects': [UID(4)]},
#     'k',
#     0,
#     {   '$classes': ['NSMutableDictionary', 'NSDictionary', 'NSObject'],
#         '$classname': 'NSMutableDictionary'},
#     {   '$classes': ['DTActivityTraceTapMessage', 'DTTapMessage', 'NSObject'],
#         '$classname': 'DTActivityTraceTapMessage'}]


class XCActivityRecord(NSBaseObject, dict):
    _keys = ('activityType', 'attachments', 'finish', 'start', 'title', 'uuid')

    def __repr__(self):
        attrs = []
        for key in self._keys:
            attrs.append('{}={}'.format(key, self[key]))

        return 'XCActivityRecord({})'.format(', '.join(attrs))

    @staticmethod
    def decode(objects: list, ns_info: dict):
        ret = XCActivityRecord()
        for key in XCActivityRecord._keys:
            ret[key] = _parse_object(objects, ns_info[key])
        return ret


# NotImplementedError: 'NSException' decode not supported
#   ns_info: {'$class': UID(8),
#  'NS.name': UID(6),
#  'NS.reason': UID(7),
#  'NS.userinfo': UID(0)}
#   ns_objects: [   '$null',
#     {'$class': UID(10), 'NSCode': 1, 'NSDomain': UID(2), 'NSUserInfo': UID(3)},
#     'DTXMessage',
#     {'$class': UID(9), 'NS.keys': [UID(4)], 'NS.objects': [UID(5)]},
#     'DTXExceptionKey',
#     {   '$class': UID(8),
#         'NS.name': UID(6),
#         'NS.reason': UID(7),
#         'NS.userinfo': UID(0)},
#     'DTXMessageInvocationException',
#     'Unable to invoke -[<XCIDESession: 0x101527c20> (socket 4) created '
#     '2020年6月12日 星期五 中国标准时间 16:32:21 '
#     '_IDE_initiateControlSessionWithProtocolVersion:] - it does not respond to '
#     'the selector',
#     {'$classes': ['NSException', 'NSObject'], '$classname': 'NSException'},
#     {'$classes': ['NSDictionary', 'NSObject'], '$classname': 'NSDictionary'},
#     {'$classes': ['NSError', 'NSObject'], '$classname': 'NSError'}]
class NSException(NSBaseObject):
    def __init__(self, name, reason, userinfo):
        self._name = name
        self._reason = reason
        self._userinfo = userinfo

    def __str__(self):
        return "NSException(name={} reason={} userinfo={}".format(
            self._name, self._reason, self._userinfo)

    def __repr__(self):
        return str(self)

    @staticmethod
    def decode(objects: list, ns_info: dict):
        name = _parse_object(objects, ns_info['NS.name'])
        reason = _parse_object(objects, ns_info['NS.reason'])
        userinfo = _parse_object(objects, ns_info['NS.userinfo'])
        return NSException(name, reason, userinfo)


# XCActivityRecord
# ns_info: {'$class': UID(10),
#  'activityType': UID(7),
#  'attachments': UID(8),
#  'finish': UID(0),
#  'start': UID(4),
#  'title': UID(6),
#  'uuid': UID(2)}
#   ns_objects: [   '$null',
#     {   '$class': UID(10),
#         'activityType': UID(7),
#         'attachments': UID(8),
#         'finish': UID(0),
#         'start': UID(4),
#         'title': UID(6),
#         'uuid': UID(2)},
#     {   '$class': UID(3),
#         'NS.uuidbytes': b"\xca0\xba\xb9\xf1^O\x18\xbd\xa8'X\xc2\xbbAG"},
#     {'$classes': ['NSUUID', 'NSObject'], '$classname': 'NSUUID'},
#     {'$class': UID(5), 'NS.time': 613636438.841612},
#     {'$classes': ['NSDate', 'NSObject'], '$classname': 'NSDate'},
#     'Start Test at 2020-06-12 14:33:58.841',
#     'com.apple.dt.xctest.activity-type.internal',
#     {'$class': UID(9), 'NS.objects': []},
#     {'$classes': ['NSArray', 'NSObject'], '$classname': 'NSArray'},
#     {   '$classes': ['XCActivityRecord', 'NSObject'],
#         '$classname': 'XCActivityRecord'}]

NoneType = type(None)

_ENCODE_MAP = {
    dict: NSDictionary,
    list: NSArray,
    set: NSSet,
    str: NSObject,
    int: NSObject,
    bool: NSObject,
    uuid.UUID: NSUUID,
    NoneType: NoneType,
    NSNull: NSNull,  # NSNull is a class, not null
    NSURL: NSURL,
    XCTestConfiguration: XCTestConfiguration,
}

_DECODE_MAP = {
    "NSDictionary": dict,
    "NSMutableDictionary": dict,
    "NSArray": list,
    "NSMutableArray": list,
    "NSSet": set,
    "NSMutableSet": set,
    "NSDate": datetime.datetime,
    "NSError": NSError,
    "NSUUID": uuid.UUID,
    "XCTestConfiguration": XCTestConfiguration,
    "NSNull": NSNull,
    "NSURL": NSURL,
    "DTActivityTraceTapMessage": DTActivityTraceTapMessage,
    "XCActivityRecord": XCActivityRecord,
    "NSException": NSException,
    "NSMutableString": NSString,
    # Ignored
    "DTSysmonTapMessage": NSIgnore,
    "DTTapHeartbeatMessage": NSIgnore,
    "DTTapStatusMessage": NSIgnore,
    "XCTAttachment": NSIgnore,
    "XCTCapabilities": NSIgnore,
}


def _encode_any(objects: list, value: Any) -> UID:
    _type = type(value)
    _class = _ENCODE_MAP.get(_type)
    if not _class:
        raise ValueError("encode not support type: {}".format(_type))
    if _class == NoneType:
        return UID(0)

    uid = UID(len(objects))
    _class.encode(objects, value)
    return uid


def objc_encode(value: Any) -> bytes:
    objects = ['$null']
    _encode_any(objects, value)
    pdata = {
        "$version": 100000,
        "$archiver": "NSKeyedArchiver",
        "$top": {
            "root": UID(1),
        },
        "$objects": objects
    }
    return dumps(pdata, fmt=FMT_BINARY)


def _parse_object(objects: list, index: Union[int, UID]) -> Any:
    if isinstance(index, UID):
        index = index.data

    if index == 0:
        return None

    obj = objects[index]
    if not isinstance(obj, dict):
        return obj

    ns_info = obj
    class_idx = ns_info['$class']
    class_name = objects[class_idx]["$classname"]
    _type = _DECODE_MAP.get(class_name)
    if not _type:
        raise DecodeNotSupportedError(
            class_name, "ns_info: {}\n  ns_objects: {}".format(
                pprint.pformat(ns_info), pprint.pformat(objects, indent=4)))

    if hasattr(_type, "decode") and callable(_type.decode):
        return _type.decode(objects, ns_info)
    elif _type == dict:
        value = {}
        ns_keys = ns_info['NS.keys']
        ns_objs = ns_info['NS.objects']
        for i in range(len(ns_keys)):
            key = objects[ns_keys[i].data]
            obj_idx = ns_objs[i].data
            value[key] = _parse_object(objects, obj_idx)
        return value
    elif _type == list:
        value = []
        for uid in ns_info["NS.objects"]:
            value.append(_parse_object(objects, uid))
        return value
    elif _type == set:
        value = set()
        for uid in ns_info["NS.objects"]:
            value.add(_parse_object(objects, uid))
        return value
    elif _type == datetime.datetime:
        time_since = datetime.datetime(2001, 1, 1)
        value = time_since + datetime.timedelta(seconds=ns_info['NS.time'])
        return value
    elif _type == NSError:
        code = 1
        code = ns_info['NSCode']
        domain = _parse_object(objects, ns_info['NSDomain'])
        user_info = _parse_object(objects, ns_info['NSUserInfo'])
        return NSError(code, domain, user_info)
    elif _type == DTSysmonTapMessage:  # FIXME: some do not have key DTTapMessagePlist
        return _parse_object(objects, ns_info["DTTapMessagePlist"])
    elif issubclass(_type, uuid.UUID):
        return NSUUID.decode(objects, ns_info)
    elif _type == NSIgnore:
        return None
    elif _type == NSNull:
        return NSNull()
    else:
        raise RuntimeError("decode not finished yet")


def objc_decode(data: Union[bytes, dict]) -> Any:
    if isinstance(data, (bytes, bytearray)):
        data = loads(data)
    if not isinstance(data,
                      dict) or data.get('$archiver') != 'NSKeyedArchiver':
        raise InvalidNSKeyedArchiverFormat()

    assert data['$version'] == 100000
    objects = data["$objects"]
    root_index = data["$top"]['root'].data

    return _parse_object(objects, root_index)


def test_objc_encode_decode():
    # yapf: disable
    for value in (
        "hello world",
        {"hello": "world"}, [1, 2, 3],
        {"hello": [1, 2, 3]},
        set([1, 2, 3]),
        {"hello": set([1, 2, 3])},
        uuid.uuid4(),
        NSNull(),
        NSURL(None, "file://abce"),
        {"none-type": None},
        {"hello": {"level2": "hello"}},
        {"hello": {
            "level2": "hello",
            "uuid": uuid.uuid4(),
            "level3": [1, 2, 3],
            "ns-uuid-null": [uuid.uuid4(), NSNull()]}},
        # set([1, {"a": 2}, 3]), # not supported, since dict is not hashable
    ):
        bdata = objc_encode(value)

        try:
            pdata = objc_decode(bdata)
            print("TEST: {:20s}".format(str(value)), end="\t")
            assert pdata == value
            print("[OK]")
        except Exception as e:
            print("Value:", value)
            pprint.pprint(loads(bdata))
            raise

        # data = loads(bdata)
        # pdata = objc_decode(data)
        # assert pdata == value
    # yapf: enable
    # TODO
    # NSDate decode


if __name__ == "__main__":
    test_objc_encode_decode()
