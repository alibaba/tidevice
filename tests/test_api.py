# -*- coding:utf-8 -*-
# ========================================
# Author: Chris
# Mail: chris.huang@batechworks.com
# Data: 2021/12/27
# ========================================
import pytest
from random import choice
import tidevice.api as api


@pytest.fixture(scope='module')
def udid():
    return choice(api.get_udid_list())


def test_api_01():
    for udid in api.get_udid_list():
        print(udid)


def test_api_02(udid):
    device = api.device_info(udid)
    print(device)


def test_api_03(udid):
    apps = api.app_list(udid)
    for app in apps:
        print(app)
