#
# Thanks to: https://github.com/msabramo/requests-unixsocket
#

from urllib.parse import splitport, unquote, urlparse

import requests
import urllib3
from requests.adapters import HTTPAdapter
from ._usbmux import Usbmux
from ._device import Device

try:
    import http.client as httplib
except ImportError:
    import httplib

DEFAULT_SCHEME = "http+usbmux://"

_usbmux = Usbmux()


# The following was adapted from some code from docker-py
# https://github.com/docker/docker-py/blob/master/docker/transport/unixconn.py
class UsbmuxHTTPConnection(httplib.HTTPConnection, object):
    def __init__(self, usbmux_socket_url, timeout=60):
        """Create an HTTP connection to a unix domain socket
        :param usbmux_socket_url: A URL with a scheme of 'http+unix' and the
        netloc is a percent-encoded path to a unix domain socket. E.g.:
        'usbmux://539c5fffb18f2be0bf7f771d68f7c327fb68d2d9/status'
        """
        super(UsbmuxHTTPConnection, self).__init__('127.0.0.1',
                                                   timeout=timeout)
        self.usbmux_socket_url = usbmux_socket_url
        self.timeout = timeout
        self.sock = None

    def __del__(self):  # base class does not have d'tor
        if self.sock:
            self.sock.close()

    def connect(self):
        netloc = unquote(urlparse(self.usbmux_socket_url).netloc)
        udid, port = splitport(netloc)
        if not port:
            port = 8100  # WDA Default port
        if not udid:
            udid = _usbmux.get_single_device_udid()

        _device = Device(udid)
        # _device = _usbmux.device(udid)
        conn = _device.create_inner_connection(int(port))
        conn._finalizer.detach() # prevent auto release socket
        self.sock = conn.get_socket()
        self.sock.settimeout(self.timeout)


class UsbmuxHTTPConnectionPool(urllib3.connectionpool.HTTPConnectionPool):
    def __init__(self, socket_path, timeout=60):
        super(UsbmuxHTTPConnectionPool, self).__init__('127.0.0.1',
                                                       timeout=timeout)
        self.socket_path = socket_path
        self.timeout = timeout

    def _new_conn(self):
        return UsbmuxHTTPConnection(self.socket_path, self.timeout)


class UsbmuxAdapter(HTTPAdapter):
    def __init__(self, timeout=60, pool_connections=25, *args, **kwargs):
        super(UsbmuxAdapter, self).__init__(*args, **kwargs)
        self.timeout = timeout
        self.pools = urllib3._collections.RecentlyUsedContainer(
            pool_connections, dispose_func=lambda p: p.close())

    def get_connection(self, url, proxies=None):
        proxies = proxies or {}
        proxy = proxies.get(urlparse(url.lower()).scheme)

        if proxy:
            raise ValueError('%s does not support specifying proxies' %
                             self.__class__.__name__)

        with self.pools.lock:
            pool = self.pools.get(url)
            if pool:
                return pool

            pool = UsbmuxHTTPConnectionPool(url, self.timeout)
            self.pools[url] = pool

        return pool

    def request_url(self, request, proxies):
        return request.path_url

    def close(self):
        self.pools.clear()


class Session(requests.Session):
    def __init__(self, url_scheme=DEFAULT_SCHEME, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mount(url_scheme, UsbmuxAdapter())
