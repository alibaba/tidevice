# coding: utf-8
#

from tidevice._usbmux import Usbmux
from tidevice import Device
from pprint import pprint

def main():
    u = Usbmux()
    
    # List devices
    devices = u.device_list()
    pprint(devices)

    buid = u.read_system_BUID()
    print("BUID:", buid)

    d = Device()
    dev_pkey = d.get_value("DevicePublicKey", no_session=True)
    print("DevicePublicKey:", dev_pkey)
    
    wifi_address = d.get_value("WiFiAddress", no_session=True)
    print("WiFi Address:", wifi_address)

    with d.create_inner_connection() as s:
        ret = s.send_recv_packet({
            "Request": "GetValue",
            "Label": "example",
        })
        pprint(ret['Value'])

    # print("Values", values)


if __name__ == "__main__":
    main()