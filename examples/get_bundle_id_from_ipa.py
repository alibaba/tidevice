# coding: utf-8

from tidevice._ipautil import IPAReader

ir = IPAReader("./testExample.ipa")
print(ir.get_bundle_id())
