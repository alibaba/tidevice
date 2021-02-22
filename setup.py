# coding: utf-8

import sys
import setuptools

if sys.version_info[:2] <= (3, 6):
    sys.exit("\n*** tidevice requires Python version 3.7+")

setuptools.setup(
    setup_requires=['pbr'], pbr=True, python_requires=">=3.7")
