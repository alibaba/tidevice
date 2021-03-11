### Layer 1: **usbmuxd**

```
# Client send to unix:/var/run/usbmuxd
00000000: A9 01 00 00 01 00 00 00  08 00 00 00 01 00 00 00  ................
00000010: ...body...

- 0x00-0x04 (A9 01 00 00): length
- 0x04-0x08 (01 00 00 00): protocol version (always 1)
- 0x08-0x0B (08 00 00 00): message type 8(Plist)
- 0x0B-0x10 (01 00 00 00): tag, the received message must contains the same tag

# Usbmuxd replys with
00000000: 6C 03 00 00 01 00 00 00  08 00 00 00 01 00 00 00  l...............
00000010: ...body...

- 0x00-0x04 (6C 03 00 00): length
- 0x04-0x08 (01 00 00 00): protocol version
- 0x08-0x0B (08 00 00 00): message type 8(Plist)
- 0x0B-0x10 (01 00 00 00): tag, same as request
```

Example of python code

```python
import struct
import socket

socket.socket(AF_INET)
```

### Layer 2: **Plist Message**
tbd

### Layer 3: **DTX Message**
tbd