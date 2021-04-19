# coding: utf-8
#
# Run with the following command
# ::Install
# pip3 install imageio pytest facebook-wda
#
# ::Usage
# py.test -v scripts/uitest_screenrecord.py -s

import contextlib
import io
import socket
import threading

import imageio
import pytest
import tidevice
import wda


@pytest.fixture
def c() -> wda.Client:
    _c = wda.USBClient()
    _c.unlock()
    yield _c


class SocketBuffer:
    """ Since I can't find a lib that can buffer socket read and write, so I write a one """
    def __init__(self, sock: socket.socket):
        self._sock = sock
        self._buf = bytearray()
    
    def _drain(self):
        _data = self._sock.recv(1024)
        if _data is None:
            raise IOError("socket closed")
        self._buf.extend(_data)
        return len(_data)

    def read_until(self, delimeter: bytes) -> bytes:
        """ return without delimeter """
        while True:
            index = self._buf.find(delimeter)
            if index != -1:
                _return = self._buf[:index]
                self._buf = self._buf[index+len(delimeter):]
                return _return
            self._drain()
    
    def read_bytes(self, length: int) -> bytes:
        while length > len(self._buf):
            self._drain()

        _return, self._buf = self._buf[:length], self._buf[length:]
        return _return
    
    def write(self, data: bytes):
        return self._sock.sendall(data)


@contextlib.contextmanager
def make_screenrecord(c: wda.Client, t: tidevice.Device, output_video_path: str):
    _old_fps = c.appium_settings()['mjpegServerFramerate']
    _fps = 10
    c.appium_settings({"mjpegServerFramerate": _fps})

    # Read image from WDA mjpeg server
    pconn = t.create_inner_connection(9100) # default WDA mjpeg server port
    sock = pconn.get_socket()
    buf = SocketBuffer(sock)
    buf.write(b"GET / HTTP/1.0\r\nHost: localhost\r\n\r\n")
    buf.read_until(b'\r\n\r\n')
    print("screenrecord is ready to begin")

    wr = imageio.get_writer(output_video_path, fps=_fps)

    def _drain(stop_event, done_event):
        while not stop_event.is_set():
            # read http header
            length = None
            while True:
                line = buf.read_until(b'\r\n')
                if line.startswith(b"Content-Length"):
                    length = int(line.decode('utf-8').split(": ")[1])
                    break
            while True:
                if buf.read_until(b'\r\n') == b'':
                    break

            imdata = buf.read_bytes(length)
            im = imageio.imread(io.BytesIO(imdata))
            wr.append_data(im)
        done_event.set()
    
    stop_event = threading.Event()
    done_event = threading.Event()
    threading.Thread(target=_drain, args=(stop_event, done_event), daemon=True).start()
    yield
    stop_event.set()
    done_event.wait()
    wr.close()
    c.appium_settings({"mjpegServerFramerate": _old_fps})
    print("Output file:", output_video_path)


def test_main(c: wda.Client):
    t = tidevice.Device()
    with make_screenrecord(c, t, "output.mp4"):
        app = c.session("com.apple.Preferences")
        app(label="蓝牙").click()
        c.sleep(1)
    
    
