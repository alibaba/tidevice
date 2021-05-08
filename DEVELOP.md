# DEVELOP
Doc for developers

Clone code to local

```bash
git clone --depth 5 https://github.com/alibaba/tidevice
```

## Certificate
[各种安全证书间的关系及相关操作](https://www.jianshu.com/p/96df7de54375)

## Inspect usbmuxd data
Not finished yet.

```
cd scripts
sudo ./run-usbmuxd-proxy.sh
```

The captured data will be stored in `usbmuxd-dumpdata`

## Pair
1. Retrieve **Device Public Key** from device
2. Generate **Host Key**

## View DeveloperDiskImage Content
For example

```bash
hdiutil mount /Applications/Xcode.app/Contents/Developer/Platforms/iPhoneOS.platform/DeviceSupport/14.0/DeveloperDiskImage.dmg
tree /Volumes/DeveloperDiskImage
```

## How to Package WDA.ipa
Build `WebDriverAgentRunnerUITests-Runner.app` with the following command. `.app` should located in `/tmp/derivedDataPath/Release-iphoneos`

```bash
$ xcodebuild build-for-testing -scheme WebDriverAgentRunner -sdk iphoneos -configuration Release -derivedDataPath /tmp/derivedDataPath
$ cd /tmp/derivedDataPath
$ cd Build/Products/Release-iphoneos # path might be different

# Created folder `Payload` and put `.app` into it
# then compressed to zip, change extention name to `.ipa`. That's all.
$ mkdir Payload && mv *.app Payload
$ zip -r WDA.ipa Payload

# test if ipa is fine
$ tidevice parse WDA.ipa
$ tidevice install WDA.ipa # install to device
```

## Publish package to Pypi using Github Actions
Ref: https://packaging.python.org/guides/publishing-package-distribution-releases-using-github-actions-ci-cd-workflows/


## References
- https://www.theiphonewiki.com/wiki/Usbmux
- C implementation <https://github.com/libimobiledevice>
- Python implement of libimobiledevice: <https://github.com/iOSForensics/pymobiledevice>
- Apple Device Images: <https://github.com/iGhibli/iOS-DeviceSupport>
- <https://github.com/troybowman/dtxmsg>
- <https://github.com/troybowman/ios_instruments_client>
- Binary of libimobiledevice for Windows <http://docs.quamotion.mobi/docs/imobiledevice/>
- https://pypi.org/project/hexdump/
