#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Created on Sun Jun 19 2022 22:54:34 by codeskyblue
"""

import unittest
import tidevice


class DeviceTest(unittest.TestCase):
    def testNew(self):
        d = tidevice.Device