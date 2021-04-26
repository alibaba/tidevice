# coding: utf-8
# codeskyblue 2020/06/03
#

__all__ = [
    'MuxError', 'MuxReplyError', 'MuxVersionError', 'MuxServiceError', 'ServiceError',
    'IPAError'
]

from ._proto import UsbmuxReplyCode


class MuxError(Exception):
    """ Mutex error """
    pass


class IPAError(Exception):
    pass


class MuxReplyError(MuxError):
    def __init__(self, number: int):
        self.reply_code = UsbmuxReplyCode(number)
        super().__init__(self.reply_code)


class MuxVersionError(MuxError):
    pass


class ServiceError(MuxError):
    pass


class MuxServiceError(ServiceError):
    pass
