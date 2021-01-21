# coding: utf-8
# codeskyblue 2020/06/03
# 

from ._proto import UsbmuxReplyCode

class MuxError(Exception):
    """ Mutex error """
    pass


class MuxReplyError(MuxError):
    def __init__(self, number: int):
        self.reply_code = UsbmuxReplyCode(number)
        super().__init__(self.reply_code)


class MuxVersionError(MuxError):
    pass


class MuxServiceError(MuxError):
    pass


class ServiceError(MuxError):
    pass


class IPAError(Exception):
    pass