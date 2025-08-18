# coding: utf-8
# codeskyblue 2020/06/10

try:
    from importlib.metadata import version, PackageNotFoundError
except ImportError:
    import pkg_resources
    def version(name):
        return pkg_resources.get_distribution(name).version
    PackageNotFoundError = pkg_resources.DistributionNotFound

from ._proto import PROGRAM_NAME
try:
    __version__ = version(PROGRAM_NAME)
except PackageNotFoundError:
    __version__ = "unknown"
