# coding: utf-8
# created: codeskyblue 2020/06/19
#

import re
import typing
import zipfile
from typing import Union
from cached_property import cached_property

from . import bplist
from . import plistlib2
from .exceptions import IPAError


class IPAReader(zipfile.ZipFile):
    def get_info_plist_info(self) -> zipfile.ZipInfo:
        re_infoplist = re.compile(r"^Payload/[^/]+\.app/Info.plist$")
        for zipinfo in self.filelist:
            if re_infoplist.match(zipinfo.filename):
                return zipinfo
        raise IPAError("Info.plist not found")

    def get_info_provision_info(self) -> zipfile.ZipInfo:
        re_provision_file = re.compile(r"^Payload/[^/]+\.app/embedded.mobileprovision$")
        for zipinfo in self.filelist:
            if re_provision_file.match(zipinfo.filename):
                return zipinfo
        raise IPAError("embedded.mobileprovision not found")

    def get_info_provision(self) -> dict:
        provision_xml_rx = re.compile(r'<\?xml.+</plist>', re.DOTALL)
        content = self.read(self.get_info_provision_info())
        match = provision_xml_rx.search(content.decode('unicode_escape'))
        if match:
            provision_xml_content = match.group().encode()
            data = plistlib2.readPlistFromBytes(provision_xml_content)
        else:
            raise IPAError('unable to parse embedded.mobileprovision file')
        return data

    def get_info_plist(self) -> dict:
        finfo = self.get_info_plist_info()
        with self.open(finfo, 'r') as fp:
            return bplist.load(fp)

    def get_bundle_id(self) -> str:
        """ return CFBundleIdentifier """
        return self.get_info_plist()['CFBundleIdentifier']

    def dump_info(self):
        data = self.get_info_plist()
        print("BundleID:", data['CFBundleIdentifier'])
        print("ShortVersion:", data['CFBundleShortVersionString'])


def parse_bundle_id(fpath: str) -> str:
    with open(fpath, "rb") as f:
        return IPAReader(f).get_bundle_id()


def main():
    # ir = IPAReader("../??.ipa")
    # print(ir.get_bundle_id())
    url = "???"  # FIXME(ssx): here need a public ipa package
    import httpio
    with httpio.open(url, block_size=-1) as fp:
        ir = IPAReader(fp)
        print(ir.get_bundle_id())


if __name__ == "__main__":
    main()
