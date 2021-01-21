# coding: utf-8
# codeskyblue 2020/06/10

import pkg_resources
from ._proto import PROGRAM_NAME
try:
    __version__ = pkg_resources.get_distribution(PROGRAM_NAME).version
except pkg_resources.DistributionNotFound:
    __version__ = "unknown"