# coding: utf-8
# codeskyblue 2020/06/03
#

__all__ = [
    'BaseError', 'MuxError', 'MuxReplyError', 'MuxVersionError', 'MuxServiceError', 'ServiceError',
    'SocketError', 'DownloadError', 'DeveloperImageError',
    'IPAError'
]

from ._proto import UsbmuxReplyCode


class BaseError(OSError):
    pass


class MuxError(BaseError):
    """ Mutex error """
    pass


class MuxReplyError(MuxError):
    def __init__(self, number: int):
        self.reply_code = UsbmuxReplyCode(number)
        super().__init__(self.reply_code)


class MuxVersionError(MuxError):
    """ usbmuxd version not match """


class ServiceError(MuxError):
    """ Service error """


class MuxServiceError(ServiceError):
    pass


class SocketError(MuxError):
    """ Socket timeout error """


class IPAError(BaseError):
    """ IPA error """


class DownloadError(BaseError):
    """ Download error """

class DeveloperImageError(BaseError):
    """ Developer image error """