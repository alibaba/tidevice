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
    def get_infoplist_zipinfo(self) -> zipfile.ZipInfo:
        re_infoplist = re.compile(r"^Payload/[^/]+\.app/Info.plist$")
        for zipinfo in self.filelist:
            if re_infoplist.match(zipinfo.filename):
                return zipinfo
        raise IPAError("Info.plist not found")

    def get_mobileprovision_zipinfo(self) -> zipfile.ZipInfo:
        re_provision_file = re.compile(r"^Payload/[^/]+\.app/embedded.mobileprovision$")
        for zipinfo in self.filelist:
            if re_provision_file.match(zipinfo.filename):
                return zipinfo
        raise IPAError("embedded.mobileprovision not found")

    def get_mobileprovision(self) -> dict:
        """
        mobileprovision usally contains keys
            AppIDName, ApplicationIdentifierPrefix, CreationDate,
            Platform, IsXcodeManaged, DeveloperCertificates,
            Entitlements, ExpirationDate, Name, ProvisionedDevices,
            TeamIdentifier, TeamName,
            TimeToLive, UUID, Version
        """
        provision_xml_rx = re.compile(br'<\?xml.+</plist>', re.DOTALL)
        content = self.read(self.get_mobileprovision_zipinfo())
        match = provision_xml_rx.search(content)
        if match:
            xml_content = match.group()
            data = plistlib2.loads(xml_content)
            return data
        else:
            raise IPAError('unable to parse embedded.mobileprovision file')

    def get_infoplist(self) -> dict:
        finfo = self.get_infoplist_zipinfo()
        with self.open(finfo, 'r') as fp:
            return bplist.load(fp)

    def get_bundle_id(self) -> str:
        """ return CFBundleIdentifier """
        return self.get_infoplist()['CFBundleIdentifier']

    def dump_info(self):
        data = self.get_infoplist()
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
