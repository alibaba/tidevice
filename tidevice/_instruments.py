# coding: utf-8
# codeskyblue 2020/06

"""
instruments连接建立之后，传输的消息为 DTXMessage

DTXMessage = (DTXMessageHeader + DTXPayload)
- DTXMessageHeader 主要用来对数据进行封包传输，以及说明是否需要应答

DTXPayload = (DTXPayloadHeader + DTXPayloadBody)

- DTXPayloadHeader 中的flags字段规定了 DTXPayloadBody 的数据类型
- DTXPayloadBody 可以是任何数据类型 (None, (None, None), List) 都有可能
"""

import enum
import io
import logging
import queue
import struct
import threading
import typing
import weakref
from collections import defaultdict, namedtuple
from typing import Any, Iterator, List, Optional, Tuple, Union

from retry import retry

from . import bplist
from . import struct2 as ct
from ._proto import LOG, InstrumentsService
from ._safe_socket import PlistSocketProxy
from .exceptions import MuxError, ServiceError

logger = logging.getLogger(LOG.xctest)

DTXMessageHeader = ct.Struct("DTXMessageHeader",
    ct.UInt32("magic", 0x1F3D5B79),
    ct.UInt32("header_length", 0x20),
    ct.UInt16("fragment_id", 0),
    ct.UInt16("fragment_count", 1),
    ct.UInt32("payload_length"),
    ct.UInt32("message_id"),
    ct.UInt32("conversation_index", 0), # 1: reply_message
    ct.UInt32("channel"),
    ct.UInt32("expects_reply", 0)) # yapf: disable

DTXPayloadHeader = ct.Struct("DTXPayloadHeader",
    ct.U32("flags"),
    ct.U32("aux_length"),
    ct.U64("total_length")) # yapf: disable

DTXMessage = namedtuple(
    "DTXMessage",
    ['payload', 'header', 'message_id', 'channel_id', 'flags', 'result'])


class DTXPayload:
    @staticmethod
    def parse(payload: Union[bytes, bytearray]) -> typing.Tuple[int, Any]:
        """ returns (flags, result) """
        h = DTXPayloadHeader.parse(payload[:0x10])

        flags = h.flags
        compression_flags = (flags & 0xFF000) >> 12
        if compression_flags:
            # compress_flags = 0x01, flags will be 0x1003
            # this happens on iOS 10.x
            flags &= 0xFF
            #raise MuxError(
            #    "message is compressed (compression type 0x%x\n), we donot know how to decompress yet"
            #    % compression_flags)

        if flags == 0x00:
            assert h.total_length == 0
            return flags, None
        elif flags == 0x02:
            plr = BinReader(payload[0x10:])
            aux_data = plr.read_exactly(h.aux_length)
            sel_data = plr.read_exactly(h.total_length - h.aux_length)

            try:
                args = unpack_aux_message(aux_data) if aux_data else None
                retobj = bplist.objc_decode(sel_data) if sel_data else None
                return flags, (retobj, args)
            except bplist.InvalidFileException as e:
                return flags, (None, None)

        elif flags in (0x01, 0x03, 0x04):
            assert h.total_length + 0x10 == len(payload)
            return flags, bplist.objc_decode(payload[0x10:])
        elif flags == 0x05:
            assert h.total_length == 0
            return flags, None
        else:
            return flags, "Unknown data"
            # pass
            # raise MuxError("Unknown flags", flags)
    
    @staticmethod
    def build(identifier: str, args: Union[list, "AUXMessageBuffer"] = []) -> bytes:
        """ 最常用的一种调用方法 flags: 0x02
        Args:
            identifier: usally function name

        For example:
            build("setConfig:", [{"bm": 0}])
        """
        sel_data = bplist.objc_encode(identifier)
        if isinstance(args, AUXMessageBuffer):
            aux_data = args.get_bytes()
        elif not args:
            aux_data = b""
        else:
            aux = AUXMessageBuffer()
            for arg in args:
                aux.append_obj(arg)
            aux_data = aux.get_bytes()
        
        pheader = DTXPayloadHeader.build({
            "flags": 0x02, #, | (0x1000 if expects_reply else 0),
            "aux_length": len(aux_data),
            "total_length": len(aux_data) + len(sel_data),
        }) # yapf: disable
        return pheader + aux_data + sel_data
    
    def build_empty() -> bytes:
        """ flags: 0x00 """
        return b'\00' * 16

    @staticmethod
    def build_other(flags, body: Any = None) -> bytes:
        """
        payload = header(flags+length) + body
        Args:
            flags (uint32):
                - 0x00: null
                - 0x02: function call, include method and arguments
                - 0x03: object
                - 0x04: object
                - 0x05: null
            body_or_identifier, args: only used in flags(0x02)
        
        Returns:
            bytes
        """
        if flags == 0x00 or flags == 0x05:
            return DTXPayloadHeader.build({
                "flags": flags,
                "aux_length": 0,
                "total_length": 0,
            })
        elif flags == 0x03 or flags == 0x04:
            body = bplist.objc_encode(body)
            pheader = DTXPayloadHeader.build({
                "flags": flags,
                "aux_length": 0,
                "total_length": len(body)
            })
            return pheader + body
        else:
            raise MuxError("Unknown flags", flags)


class Event(str, enum.Enum):
    NOTIFICATION = ":notification:"
    FINISHED = ":finished:"
    OTHER = ":other:"


class BinReader(io.BytesIO):
    def read_u32(self) -> int:
        (val, ) = struct.unpack("I", self.read(4))
        return val

    def read_u64(self) -> int:
        (val, ) = struct.unpack("Q", self.read(8))
        return val

    def read_exactly(self, n: int) -> bytes:
        data = self.read(n)
        if len(data) != n:
            raise MuxError("read expect length: 0x%X, got: 0x%x" %
                           (n, len(data)))
        return data


# class AUXMessage
def unpack_aux_message(data: bytes) -> list:
    """ Parse aux message array
    
    Returns:
        list of data
    """
    if len(data) < 16:
        raise MuxError("aux data is too small to unpack")

    args = []
    br = BinReader(data)
    br.read(16)  # ignore first 16 magic bytes
    while True:
        typedata = br.read(4)
        if not typedata:
            break
        _type = struct.unpack("I", typedata)[0]
        if _type == 2:
            _len = br.read_u32()
            archived_data = br.read(_len)
            val = bplist.objc_decode(archived_data)
            args.append(val)
        elif _type in [3, 5]:
            val = br.read_u32()
            args.append(val)
        elif _type in [4, 6]:
            val = br.read_u64()
            args.append(val)
        elif _type == 10:
            # Ignore
            pass
        else:
            raise MuxError("Unknown type", hex(_type))
    return args


class AUXMessageBuffer(object):
    def __init__(self):
        self._buf = bytearray()

    def _extend(self, b: bytes):
        self._buf.extend(b)

    def get_bytes(self) -> bytearray:
        """
        the final serialized array must start with a magic qword,
        followed by the total length of the array data as a qword,
        followed by the array data itself.
        """
        out = bytearray()
        out.extend(struct.pack("QQ", 0x01F0, len(self._buf)))
        out.extend(self._buf)
        return out

    def append_u32(self, n: int):
        self._extend(struct.pack("III", 10, 3, n))

    def append_u64(self, n: int):
        """
        0000: 10 00 00 00 04 00 00 00 xx xx xx xx
        """
        self._extend(struct.pack("IIQ", 10, 4, n))

    def append_null(self):
        self._extend(struct.pack("III", 10, 2, 0))

    def append_obj(self, obj):
        self._extend(struct.pack("II", 10, 2))
        if isinstance(obj, (bytes, bytearray)):
            buf = obj
        else:
            buf = bplist.objc_encode(obj)
        self._extend(struct.pack("I", len(buf)))
        self._extend(buf)

    # def append(self, v):
    #     if type(v) is int: # note that: isinstance(True, int) == True
    #         self.append_u32(v)
    #     else:
    #         self.append_obj(v)

class DTXService(PlistSocketProxy):

    def prepare(self):
        super().prepare()
    
        self._last_message_id = 0
        self._last_channel_id = 0
        self._channels = {}  # map channel str to channel code

        self._reply_queues = defaultdict(queue.Queue)
        self._handlers = {}
        self._quitted = threading.Event()
        self._stop_event = threading.Event()

        #self.recv_dtx_message()  # ignore _notifyOfPublishedCapabilities
        capabilities = {
            "com.apple.private.DTXBlockCompression": 2,  # version
            "com.apple.private.DTXConnection": 1,  # version
        }
        payload = DTXPayload.build('_notifyOfPublishedCapabilities:', [capabilities])
        self.send_dtx_message(channel=0, payload=payload)
        self._dtx_message_pool = {}
        self._drain_background()  # 开启接收线程
        weakref.finalize(self, self._stop_event.set)

    def _next_message_id(self) -> int:
        self._last_message_id += 1
        return self._last_message_id

    def _next_channel_id(self) -> int:
        self._last_channel_id += 1
        return self._last_channel_id

    def make_channel(self, identifier: str) -> int:
        """
        returns channel id
        """
        if hasattr(identifier, "value"): # enum.Enum type
            identifier = identifier.value

        if identifier in self._channels:
            return self._channels[identifier]

        channel_id = self._next_channel_id()
        args = [channel_id, identifier]
        aux = AUXMessageBuffer()
        aux.append_u32(channel_id)
        aux.append_obj(identifier)
        result = self.call_message(0, '_requestChannelWithCode:identifier:', aux)
        if result:
            raise MuxError("makeChannel error", result)

        self._channels[identifier] = channel_id
        return channel_id

    def iter_message(self, identifier: Union[str, Event]) -> Iterator[DTXMessage]:
        """
        Subscribe dtx message

        Usage example:
            for m in self.iter_message(Event.NOTIFICATION):
                if m.channel_id = 0xFFFFFFFF:
                    print(m.result)
        """
        q = queue.Queue()
        self.register_callback(identifier, lambda m: q.put(m))
        for m in iter(q.get, None):
            yield m

    def register_callback(self, identifier, func: typing.Callable):
        """ call function when server called

        Args:
            func(data: DTXMessage)
        """
        self._handlers[identifier] = func

    def call_message(
        self,
        channel: Union[int, str],
        identifier: str,
        aux: Union[AUXMessageBuffer, list] = [],
        expects_reply: bool = True
    ) -> Union[None, tuple, Any]:
        """ send message and wait for reply
        Returns could be None, tuple or single value"""
        if isinstance(channel, str):
            channel = self.make_channel(channel)
        payload = DTXPayload.build(identifier, aux)
        _id = self.send_dtx_message(channel,
                                    payload=payload,
                                    expects_reply=expects_reply)
        if expects_reply:
            return self.wait_reply(_id).result

    def send_dtx_message(self,
                         channel: int,
                         payload: Union[bytes, bytearray],
                         expects_reply: bool = False,
                         message_id: Optional[int] = None) -> int:
        """
        when identifier is None, args will be ignored
        when message_id is set, conversation_index will set to 1,
            which means this message is a reply
        
        Returns:
            message_id
        """
        if self.psock.closed:
            raise ServiceError("SocketConnectionInvalid")
        if message_id is None:
            conversation_index = 0
            _message_id = self._next_message_id()
        else:
            conversation_index = 1
            _message_id = message_id

        mheader = DTXMessageHeader.build(
            message_id=_message_id,
            payload_length=len(payload),
            channel=channel,
            expects_reply=1 if expects_reply else 0,
            conversation_index=conversation_index)

        data = bytearray()
        data.extend(mheader)
        data.extend(payload)
        logger.debug("SEND DTXMessage: channel:%d expect_reply:%d data_length:%d, data...", channel, int(expects_reply), len(data))
        self.psock.sendall(data)
        return _message_id

    def recv_part_dtx_message(self) -> typing.Optional[int]:
        """
        DTXMessage contains one or more fragmenets
        This fragments may received in different orders

        Returns:
            None or message_id
        """
        data = self.psock.recvall(0x20)
        h = DTXMessageHeader.parse(data)
        if h.magic != 0x1F3D5B79:
            raise MuxError("bad header magic: 0x%x\n" % h.magic)

        if h.header_length != 0x20:
            raise MuxError("header length expect 0x20, got 0x%x".format(
                h.header_length))
        
        if h.fragment_id == 0:
            # when reading multiple message fragments
            # only the 0th fragment contains a message header
            # but the 0th payload is empty
            self._dtx_message_pool[h.message_id] = (h, bytearray())
            if h.fragment_count > 1:
                return None
        _, payload = self._dtx_message_pool[h.message_id]
        rawdata = self.psock.recvall(h.payload_length)
        payload.extend(rawdata)
        
        if h.fragment_id == h.fragment_count - 1:
            return h.message_id
        else:
            return None

    def recv_dtx_message(self) -> Tuple[Any, bytearray]:
        """
        前32个字节(两行) 为DTXMessage的头部 (包含了消息的类型和请求的channel)
        后面是携带的payload

        Returns:
            DTXMessageHeader, payload
        
        Raises:
            MuxError

        Returns:
            retobj  contains the return value for the method invoked by send_message()
            aux     usually empty, except in specific situations (see _notifyOfPublishedCapabilities)
        
        # Refs: https://github.com/troybowman/dtxmsg/blob/master/dtxmsg_client.cpp

        数据解析说明
        >> 全部数据
        00000000: 79 5B 3D 1F 20 00 00 00  00 00 01 00 2C 1C 00 00  y[=. .......,...
        00000010: 02 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00  ................
        00000020: 02 00 00 00 71 1B 00 00  1C 1C 00 00 00 00 00 00  ....q...........
        00000030: F0 1B 00 00 00 00 00 00  61 1B 00 00 00 00 00 00  ........a.......  
        00000040: 0A 00 00 00 02 00 00 00  55 1B 00 00 62 70 6C 69  ........U...bpli
        00000050: 73 74 30 30 D4 00 01 00  02 00 03 00 04 00 05 00  st00............
        00000060: 06 01 2F 01 30 58 24 76  65 72 73 69 6F 6E 58 24  ../.0X$versionX$
        00000070: 6F 62 6A 65 63 74 73 59 

        >> 前32个字节
        00000000: 79 5B 3D 1F 20 00 00 00  00 00 01 00 2C 1C 00 00  y[=. .......,...
        00000010: 02 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00
        \\\\
        struct DTXMessageHeader {
            u32 magic  # 79 5B 3D 1F
            u32 cb # 20 00 00 00      # sizeof(DTXMessageHeader)
            u16 fragmentId # 00 00
            u16 fragmentCount # 01 00
            u32 length # 2C 1C 00 00  # 不包括MessageHeader自身的长度

            u32 messageId # 02 00 00 00
            u32 conversationIndex # 00 00 00 00 # 1 indicate a reply message
            u32 channelCode # 00 00 00 00
            u32 expectReply # 00 00 00 00    # 1 or 0
        }
        
        00000020: 02 00 00 00 71 1B 00 00  1C 1C 00 00 00 00 00 00
        \\\\
        # 紧跟在MessageHeader的后面
        struct payloadHeader {
            u32 flags # 02 00 00 00 # 02(包含两个值), 00(empty), 01,03,04(只有一个值)
            u32 auxiliaryLength # 71 1B 00 00
            u64 totalLength # 1C 1C 00 00 00 00 00 00
        }
        

        >> Body 部分
        00000030: F0 1B 00 00 00 00 00 00  61 1B 00 00 00 00 00 00  ........a.......
        \\\\
        # 前面8个字节 0X1BF0 据说是Magic word
        # 后面的 0x1B61 是整个序列化数据的长度
        # 解析的时候可以直接跳过这部分

        # 序列化的数据部分, 使用OC的NSKeyedArchiver序列化
        # 0A,00,00,00: 起始头
        # 02,00,00,00: 2(obj) 3(u32) 4(u64) 5(u32) 6(u64)
        # 55,1B,00,00: 序列化的数据长度
        00000040: 0A 00 00 00 02 00 00 00  55 1B 00 00 62 70 6C 69  ........U...bpli
        .....

        # 最后面还跟了一个NSKeyedArchiver序列化后的数据，没有长度字段

                          objectsY
        
        ## 空数据Example, 仅用来应答收到的意思。其中的messageId需要跟请求的messageId保持一致
        00000000: 79 5B 3D 1F 20 00 00 00  00 00 01 00 10 00 00 00  y[=. ...........
        00000010: 03 00 00 00 01 00 00 00  00 00 00 00 00 00 00 00  ................
        00000020: 00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00  ................
        """
        while True:
            message_id = self.recv_part_dtx_message()
            if message_id is None:
                continue
            mheader, payload = self._dtx_message_pool.pop(message_id)
            assert mheader.conversation_index in [0, 1, 2]
            assert mheader.expects_reply in [0, 1]
            return (mheader, payload)

    def _call_handlers(self, event_name: Event, data: Any = None) -> bool:
        """
        Returns:
            return handle func return
        """
        func = self._handlers.get(event_name)
        if func:
            return func(data)

    def _reply_null(self, m: DTXMessage):
        """ null reply means message received """
        self.send_dtx_message(m.channel_id,
                              payload=DTXPayload.build_empty(),
                              message_id=m.message_id)
        return True

    def _handle_dtx_message(self, m: DTXMessage) -> bool:
        assert m.header.expects_reply == 1

        if m.channel_id == 0xFFFFFFFF and m.flags == 0x05:
            return self._reply_null(m)

        if m.flags == 0x02:
            identifier, args = m.result
            if identifier == '_requestChannelWithCode:identifier:':
                return self._reply_null(m)

            # if identifier == "_XCT_logDebugMessage:":
            #     logger.debug("logDebugMessage: %s", args)
            #     self._reply_null(m)

            if self._call_handlers(identifier, m):
                return True
        # else:
        if self._call_handlers(Event.OTHER, m):
            return True

    def wait_reply(self, message_id: int, timeout=30.0) -> DTXMessage:
        """
        Raises:
            MuxError, ServiceError

        Refs: https://www.tornadoweb.org/en/stable/guide/async.html#asynchronous
        """
        try:
            ret = self._reply_queues[message_id].get(timeout=timeout)
            if ret is None:
                raise MuxError("connection closed")
            return ret
        except queue.Empty:
            raise ServiceError("wait reply timeout")

    def _drain_background(self):
        threading.Thread(name="DTXMessage", target=self._drain, daemon=True).start()

    def _drain(self):
        try:
            while not self._stop_event.is_set():
                try:
                    self._drain_single_message()
                except MuxError as e:
                    # logger.warning("unexpected error: %s", e)
                    break
                except OSError:
                    if self._stop_event.is_set():
                        break
                    raise
                except:
                    if not self._stop_event.is_set():
                        raise
                    break
        except:
            if not self._stop_event.is_set():
                logger.exception("drain error")
        finally:
            logger.debug("dtxm socket closed")
            # notify all quited
            self._quitted.set()
            for q in self._reply_queues.values():
                q.put(None)  # None means closed
            self._call_handlers(Event.NOTIFICATION, None)
            self._call_handlers(Event.OTHER, None)
            self._call_handlers(Event.FINISHED, None)
            # print("all quited")

    def _drain_single_message(self):
        mheader, payload = self.recv_dtx_message()
        flags, result = DTXPayload.parse(payload)
        dtxm = DTXMessage(payload=payload,
                          header=mheader,
                          message_id=mheader.message_id,
                          channel_id=mheader.channel,
                          flags=flags,
                          result=result)
        
        logger.debug("RECV DTXMessage: expects_reply:%d flags:%d conv:%d %s", mheader.expects_reply, dtxm.flags, mheader.conversation_index, dtxm.result)

        if mheader.conversation_index == 1:  # reply from server
            self._reply_queues[mheader.message_id].put(dtxm)
        elif mheader.conversation_index == 0:
            # handle request
            if mheader.expects_reply == 0:  # notification from server
                if self._call_handlers(Event.NOTIFICATION, dtxm):
                    return
                if dtxm.flags == 0x02 and dtxm.result[
                        0] == '_notifyOfPublishedCapabilities:':
                    # 公共方法消息，直接忽略
                    return
                logger.debug(
                    "Ignore notification from server: %d, 0x%x, %s",
                    dtxm.message_id, dtxm.flags, dtxm.result)
            else:
                handled = self._handle_dtx_message(dtxm)
                if not handled:
                    #logger.debug("server request not handled: %s", dtxm.result) # too many logs
                    self._reply_null(dtxm)
        elif mheader.conversation_index == 2:
            # usally NSError message
            pass

    def close(self):
        """ stop background """
        self._stop_event.set()
        self.psock.close()

    def wait(self):
        while not self._quitted.wait(.1):
            pass


class ServiceInstruments(DTXService):
    _SERVICE_DEVICEINFO = 'com.apple.instruments.server.services.deviceinfo'
    _SERVICE_PROCESS_CONTROL = "com.apple.instruments.server.services.processcontrol"

    def prepare(self):
        super().prepare()

    def app_launch(self,
                   bundle_id: str,
                   app_env: dict = {},
                   args: list = [],
                   kill_running: bool = False) -> int:
        """
        Raises:
            ServiceError
        """
        code = self.make_channel(self._SERVICE_PROCESS_CONTROL)
        method = "launchSuspendedProcessWithDevicePath:bundleIdentifier:environment:arguments:options:"
        app_path = ""  # not used, just pass empty string
        #app_args = []  # not used, just pass empty array

        options = {
            # don't suspend the process after starting it
            "StartSuspendedKey": 0,
            # kill the application if it is already running
            "KillExisting": kill_running,
            # I donot know much about it, when set to True, app will have a pid, but not show up
            # "ActivateSuspended": False,
        }
        args = [app_path, bundle_id, app_env, args, options]
        pid = self.call_message(code, method, args)
        if not isinstance(pid, int):
            raise ServiceError("app launch failed", pid)
        return pid

    def app_kill(self, pid: int):
        channel = self.make_channel(self._SERVICE_PROCESS_CONTROL)
        if channel < 1:
            raise MuxError("make Channel error")

        self.call_message(channel, "killPid:", [pid], expects_reply=False)

    def app_running_processes(self) -> typing.List[dict]:
        """
        Returns array of dict:
            {'isApplication': False,
            'name': 'timed',
            'pid': 58,
            'realAppName': '/usr/libexec/timed',
            'startDate': datetime.datetime(2020, 5, 25, 2, 22, 29, 603427)},
            {'isApplication': False,
            'name': 'bookassetd',
            'pid': 202,
            'realAppName': '/System/Library/PrivateFrameworks/BookLibrary.framework/Support/bookassetd',
            'startDate': datetime.datetime(2020, 5, 25, 7, 12, 30, 298572)}
        """
        identifier = self._SERVICE_DEVICEINFO
        retobj = self.call_message(identifier, "runningProcesses")
        return retobj

    def app_process_list(self, app_infos: List[dict]) -> Iterator[dict]:
        """
        Args:
            app_infos: value from self.instrumentation.app_list()
        Returns yield of
        {
            'isApplication': True,
            'name': 'timed',
            'pid': 58,
            'realAppName': '/usr/libexec/timed',
            'startDate': datetime.datetime(2020, 5, 25, 2, 22, 29, 603427)},
            'bundle_id': 'com.libexec.xxx',
            'display_name': "xxxxx",
        }
        """
        def exefile2appinfo(exe_abspath: str, app_infos: List[dict]):
            for info in app_infos:
                # info may not contain key "Path"
                # https://github.com/alibaba/taobao-iphone-device/issues/61
                path = info.get('Path', "") + "/" + info['CFBundleExecutable']
                if path.startswith("/private"):
                    path = path[len("/private"):]
                if exe_abspath == path:
                    return info
            return {}

        processes = self.app_running_processes()
        for p in processes:
            app_exepath = p['realAppName']
            info = exefile2appinfo(app_exepath, app_infos)
            p.update(info)
            p['bundle_id'] = p.get("CFBundleIdentifier", "")
            p['display_name'] = p.get('CFBundleDisplayName', '')
            yield p

    def app_list(self):
        """
        Avaliable keys
        - AppExtensionUUIDs: ["..."],
        - BundlePath: '/private/var/containers/Bundle/Application/E6xxx..../xx.app'
        - CFBundleIdentifier: "com.apple.xxx"
        - DisplayName: "计算器",
        - Placeholder: True
        - Restricted: 0
        - Type: User
        - Version: 1.2.3.4
        """
        code = self.make_channel(
            "com.apple.instruments.server.services.device.applictionListing")
        ret = self.call_message(
            code, "installedApplicationsMatching:registerUpdateToken:",
            [{}, ""])
        return ret

    def system_info(self) -> dict:
        """
        Returns:
            {'_deviceDescription': 'Build Version 17E262, iPhone ID '
                       '539c5fffb18f2be0bf7f771d68f7c327fb68d2d9',
            '_deviceDisplayName': '孙圣翔的 iPhone (v13.4.1)',
            '_deviceIdentifier': '539c5fffb18f2be0bf7f771d68f7c327fb68d2d9',
            '_deviceVersion': '17E262',
            '_productType': 'iPhone8,1',
            '_productVersion': '13.4.1',
            '_xrdeviceClassName': 'XRMobileDevice'}
        """
        identifier = "com.apple.instruments.server.services.deviceinfo"
        code = self.make_channel(identifier)
        return self.call_message(code, "systemInformation")

    def iter_opengl_data(self) -> Iterator[dict]:
        """
        Yield data
        {'CommandBufferRenderCount': 0,
        'CoreAnimationFramesPerSecond': 0,
        'Device Utilization %': 0,
        'IOGLBundleName': 'Built-In',
        'Renderer Utilization %': 0,
        'SplitSceneCount': 0,
        'TiledSceneBytes': 0,
        'Tiler Utilization %': 0,
        'XRVideoCardRunTimeStamp': 448363116,
        'agpTextureCreationBytes': 0,
        'agprefTextureCreationBytes': 0,
        'contextGLCount': 0,
        'finishGLWaitTime': 0,
        'freeToAllocGPUAddressWaitTime': 0,
        'gartMapInBytesPerSample': 0,
        'gartMapOutBytesPerSample': 0,
        'gartUsedBytes': 30965760,
        'hardwareWaitTime': 0,
        'iosurfaceTextureCreationBytes': 0,
        'oolTextureCreationBytes': 0,
        'recoveryCount': 0,
        'stdTextureCreationBytes': 0,
        'textureCount': 1382}
        """
        channel = self.make_channel(
            "com.apple.instruments.server.services.graphics.opengl")
        # print("Channel:", channel)

        # print("Start sampling")
        aux = AUXMessageBuffer()
        aux.append_obj(0)
        payload = DTXPayload.build("startSamplingAtTimeInterval:", [0])
        self.send_dtx_message(channel, payload)

        que = queue.Queue()
        self.register_callback(Event.OTHER, lambda m: que.put(m))

        n = 0
        try:
            for m in iter(que.get, None):
                if m.channel_id != 0xFFFFFFFF:
                    continue
                # self._reply_null(m)
                yield m.result
        finally:
            self.close()
    
    def iter_application_notification(self) -> Iterator[dict]:
        """ 监听应用通知
        Iterator data
            ('applicationStateNotification:',
                [{'appName': 'com.tencent.xin.WeChatNotificationServiceExtension',
                'displayID': 'com.tencent.xin.WeChatNotificationServiceExtension',
                'elevated_state': 2,
                'elevated_state_description': 'Background Task Suspended',
                'execName': 'Unknown',
                'mach_absolute_time': 403472780544,
                'pid': 329,
                'state': 2,
                'state_description': 'Background Task Suspended',
                'timestamp': datetime.datetime(2020, 10, 30, 3, 30, 53, 117418)}])
        
        state:
        - 1: Terminated
        - 2: Background Task Suspended
        - 4: Background Running
        - 8: Foreground Running
        """
        channel_id = self.make_channel(InstrumentsService.MobileNotifications)
        self.call_message(channel_id, 'setApplicationStateNotificationsEnabled:', [True], expects_reply=False)
        notification_channel_id = (1<<32) - channel_id
        try:
            for m in self.iter_message(Event.NOTIFICATION):
                if m.flags == 0x02 and m.channel_id == notification_channel_id:
                    yield m.result
        except GeneratorExit:
            self.close()

    def iter_cpu_memory(self) -> Iterator[dict]:
        """
        Close connection after iterator stop

        Iterator content eg:
            [{'CPUCount': 2,
            'EnabledCPUs': 2,
            'EndMachAbsTime': 2158497307470,
            'PerCPUUsage': [{'CPU_NiceLoad': 0.0,
                            'CPU_SystemLoad': -1.0,
                            'CPU_TotalLoad': 13.0,
                            'CPU_UserLoad': -1.0},
                            {'CPU_NiceLoad': 0.0,
                            'CPU_SystemLoad': -1.0,
                            'CPU_TotalLoad': 31.0,
                            'CPU_UserLoad': -1.0}],
            'StartMachAbsTime': 2158473307786,
            'SystemCPUUsage': {'CPU_NiceLoad': 0.0,
                                'CPU_SystemLoad': -1.0,
                                'CPU_TotalLoad': 44.0,
                                'CPU_UserLoad': -1.0},
            'Type': 33},
            {'EndMachAbsTime': 2158515468993,
            "cpuUsage", "ctxSwitch", "intWakeups", "physFootprint",
                "memResidentSize", "memAnon", "pid"
            'Processes': {0: [0.20891292720792148, # cpuUsage
                                335770139, # contextSwitch
                                120505483, # interruptWakeups
                                7913472,   # physical Footprint
                                869646336, # memory RSS
                                232210432, # memory Anon?
                                0],        # pid
                            1: [0.0005502246751775457,
                                691065,
                                6038,
                                12353840,
                                4177920,
                                12255232,
                                1]
                            }
            }]
        """
        config = {
            "bm": 0,
            "cpuUsage": True,
            "procAttrs": [
                "memVirtualSize", "cpuUsage", "ctxSwitch", "intWakeups",
                "physFootprint", "memResidentSize", "memAnon", "pid"
            ],
            "sampleInterval": 1000000000, # 1e9 ns == 1s
            "sysAttrs": [
                "vmExtPageCount", "vmFreeCount", "vmPurgeableCount",
                "vmSpeculativeCount", "physMemSize"
            ],
            "ur": 1000
        }

        channel_id = self.make_channel(InstrumentsService.Sysmontap)
        self.call_message(channel_id, "setConfig:", [config])
        self.call_message(channel_id, "start", [])

        # channel = self.make_channel(
        #     "com.apple.instruments.server.services.processcontrol")
        # aux = AUXMessageBuffer()
        # aux.append_obj(1)  # TODO: pid
        # payload = DTXPayload.build("startObservingPid:", aux)
        # self.send_dtx_message(channel, payload)
        notification_channel_id = (1<<32) - channel_id
        try:
            for m in self.iter_message(Event.NOTIFICATION):
                if m.flags == 0x01 and m.channel_id == notification_channel_id:
                    yield m.result
        except GeneratorExit:
            self.close() # 停止connection，防止消息不停的发过来，暂时不会别的方法
            # print("Stop channel")
            ## The following code is not working
            # self.call_message(channel_id, "stopSampling")
            # aux = AUXMessageBuffer()
            # aux.append_obj(channel_id)
            # self.send_dtx_message(channel_id, DTXPayload.build('_channelCanceled:', aux))

    def start_energy_sampling(self, pid: int):
        ch_network = InstrumentsService.XcodeEnergyStatistics
        return self.call_message(ch_network, 'startSamplingForPIDs:', [{pid}])

    def stop_energy_sampling(self, pid: int):
        ch_network = InstrumentsService.XcodeEnergyStatistics
        return self.call_message(ch_network, 'stopSamplingForPIDs:', [{pid}])

    def get_process_energy_stats(self, pid: int) -> Optional[dict]:
        """
        Returns dict:
            example:
            {
                "energy.overhead": -10,
                "kIDEGaugeSecondsSinceInitialQueryKey": 10,
                "energy.version": 1,
                "energy.gpu.cost": 0,
                "energy.cpu.cost": 0.10964105931592821,
                "energy.networkning.overhead": 0,
                "energy.appstate.cost": 8,
                "energy.location.overhead": 0,
                "energy.thermalstate.cost": 0,
                "energy.networking.cost": 0,
                "energy.cost": -9.890358940684072,
                "energy.display.cost": 0,
                "energy.cpu.overhead": 0,
                "energy.location.cost": 0,
                "energy.gpu.overhead": 0,
                "energy.appstate.overhead": 0,
                "energy.display.overhead": 0,
                "energy.inducedthermalstate.cost": -1
            }
        """
        ch_network = InstrumentsService.XcodeEnergyStatistics
        args = [{}, {pid}]
        ret = self.call_message(ch_network, 'sampleAttributes:forPIDs:', args)
        return ret.get(pid)

    def start_network_sampling(self, pid: int):
        ch_network = 'com.apple.xcode.debug-gauge-data-providers.NetworkStatistics'
        return self.call_message(ch_network, 'startSamplingForPIDs:', [{pid}])

    def stop_network_sampling(self, pid: int):
        ch_network = 'com.apple.xcode.debug-gauge-data-providers.NetworkStatistics'
        return self.call_message(ch_network, 'stopSamplingForPIDs:', [{pid}])

    def get_process_network_stats(self, pid: int) -> Optional[dict]:
        """
        经测试数据始终不是很准，用safari测试，每次刷新图片的时候，rx.bytes总是不动
        """
        ch_network = InstrumentsService.XcodeNetworkStatistics
        args = [{
            'net.bytes',
            'net.bytes.delta',
            'net.connections[]',
            'net.packets',
            'net.packets.delta',
            'net.rx.bytes',
            'net.rx.bytes.delta',
            'net.rx.packets',
            'net.rx.packets.delta',
            'net.tx.bytes',
            'net.tx.bytes.delta',
            'net.tx.packets',
            'net.tx.packets.delta'
        }, {pid}]
        ret = self.call_message(ch_network, 'sampleAttributes:forPIDs:', args)
        return ret.get(pid)
    
    def iter_network(self) -> Iterator[dict]:
        """
        system network

        yield of {
            "rx.bytes": ..,
            "tx.bytes": ..,
            "rx.packets": ..,
            "tx.packets": ..,
        }
        """
        channel_name = 'com.apple.instruments.server.services.networking'
        channel_id = self.make_channel(channel_name)

        noti_chan = (1<<32) - channel_id
        it = self.iter_message(Event.NOTIFICATION)
        self.call_message(channel_id, "startMonitoring")
        for data in it:
            if data.channel_id != noti_chan:
                continue
            (_type, values) = data.result
            if _type == 2:
                rx_packets, rx_bytes, tx_packets, tx_bytes = values[:4]
                yield {
                    "rx.packets": rx_packets,
                    "rx.bytes": rx_bytes,
                    "tx.packets": tx_packets,
                    "tx.bytes": tx_bytes,
                }

    def is_running_pid(self, pid: int) -> bool:
        aux = AUXMessageBuffer()
        aux.append_obj(pid)
        return self.call_message(self._SERVICE_DEVICEINFO, 'isRunningPid:', aux)

    def execname_for_pid(self, pid: int) -> str:
        aux = AUXMessageBuffer()
        aux.append_obj(pid)
        return self.call_message(self._SERVICE_DEVICEINFO, 'execnameForPid:', aux)
    
    def hardware_information(self) -> dict:
        """
        Return example: 
        {'numberOfPhysicalCpus': 2,
        'hwCPUsubtype': 1,
        'numberOfCpus': 2,
        'speedOfCpus': 0,
        'hwCPUtype': 16777228,
        'hwCPU64BitCapable': 1}
        """
        return self.call_message(self._SERVICE_DEVICEINFO, 'hardwareInformation')
    
    def network_information(self) -> dict:
        """
        Return example: 
        {'en0': 'Wi-Fi',
        'pdp_ip3': 'Cellular (pdp_ip3)',
        'pdp_ip2': 'Cellular (pdp_ip2)',
        'pdp_ip1': 'Cellular (pdp_ip1)',
        'pdp_ip0': 'Cellular (pdp_ip0)',
        'en2': 'Ethernet Adaptor (en2)',
        'pdp_ip4': 'Cellular (pdp_ip4)',
        'lo0': 'Loopback',
        'en1': 'Ethernet Adaptor (en1)'}
        """
        return self.call_message(self._SERVICE_DEVICEINFO, 'networkInformation')
