#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Created on Mon Jan 25 2021 10:42:05 by codeskyblue
"""

import pytest
import os


curdir = os.path.dirname(os.path.abspath(__file__))


@pytest.fixture
def wda_filepath():
    return os.path.join(curdir, "testdata/WebDriverAgentRunner.ipa")