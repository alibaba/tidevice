#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Created on Mon Jan 25 2021 10:38:39 by codeskyblue
"""

import pytest
from tidevice._ipautil import IPAReader, IPAError


@pytest.mark.skip("ipa file removed from git")
def test_get_infoplist(wda_filepath: str):
    ir = IPAReader(wda_filepath)
    assert ir.get_bundle_id() == "com.facebook.WebDriverAgentRunner.xctrunner"

    data = ir.get_mobileprovision()
    assert "Version" in data
    assert data['Version'] == 1

