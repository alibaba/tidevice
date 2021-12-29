# -*- coding:utf-8 -*-
# ========================================
# Author: Chris
# Mail: chris.huang@batechworks.com
# Data: 2021/12/27
# ========================================
from .__main__ import init_um
from .__main__ import _udid2device


def get_udid_list():
    um = init_um()
    udids = []
    for device in um.device_list():
        udids.append(device.udid)
    return udids


def device_info(udid):
    init_um()
    d = _udid2device(udid=udid)
    return d.get_value()


def app_list(udid):
    init_um()
    d = _udid2device(udid)
    for info in d.installation.iter_installed():
        yield info
