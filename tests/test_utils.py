#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Created on Fri Jan 13 2023 10:52:44 by codeskyblue
"""

from tidevice._utils import semver_compare


def test_semver_compare():
    for ver1, ver2, expect in (("1.0", "1.0", 0),
                               ("1.1", "1.1.0", 0),
                               ("1.1", "1.2", -1),
                               ("1.2.0", "1.0", 1),
                               ("2.0", "1.0", 1),
                               ("2.0", "3.0.1", -1)):
        assert semver_compare(ver1, ver2) == expect