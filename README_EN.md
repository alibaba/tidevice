![tidevice](assets/tidevice-logo.png)
# tidevice

[![PyPI](https://img.shields.io/pypi/v/tidevice)](https://pypi.org/project/tidevice/)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/tidevice)](https://pypistats.org/search/tidevice)

[中文文档](README.md)

Command line tool to communicate with iOS device, support the following functions

- screenshot
- get device info
- ipa install and uninstall
- launch and kill app
- list installed app info
- retrieve performance data
- simulate run xctest, eg: WebDriverAgent
- other

Support platform: Mac, Linux, Windows

## Install
```bash
pip3 install -U tidevice
```

## Usage

### Show version number
```bash
$ tidevice version
0.1.0
```

### List connected devices
```bash
$ tidevice list
List of apple devices attached
00008030-001A35E40212345678 codeskyblue的iPhoneSE

$ tidevice list --json
[
    {
        "udid": "00008030-001A35E40212345678",
        "name": "codeskyblue的iPhoneSE"
    }
]
```

### App management
```bash
$ tidevice install example.ipa
$ tidevice install https://example.org/example.ipa

$ tidevice uninstall com.example.demo

$ tidevice launch com.example.demo

$ tidevice kill com.example.demo

# show installed app list
$ tidevice applist
```

### Run WebDriverAgent
> Please make sure your iPhone already have [WebDriverAgent](https://github.com/appium/WebDriverAgent) installed

```bash
$ tidevice xctest -B com.facebook.wda.WebDriverAgent.Runner
[I 210127 11:40:23 _device:909] BundleID: com.facebook.wda.WebDriverAgent.Runner
[I 210127 11:40:23 _device:911] DeviceIdentifier: 12345678901234567890abcdefg
[I 210127 11:40:23 _device:773] SignIdentity: 'Apple Development: -Your-Developer-Name-'
[I 210127 11:40:23 _device:840] Launch 'com.facebook.wda.WebDriverAgent.Runner' pid: 239
[I 210127 11:40:23 _device:1003] ProductVersion: 12.4
[I 210127 11:40:24 _device:952] Start execute test plan with IDE version: 29
[I 210127 11:40:24 _device:875] WebDriverAgent start successfully

# Change WDA listen port to 8200
$ tidevice xctest -B com.facebook.wda.WebDriverAgent.Runner -e USB_PORT:8200
```

Then you can connect with Appium or [facebook-wda](https://github.com/openatx/facebook-wda)

*facebook-wda example code*

```python
import wda
c = wda.USBClient()
print(c.info)
```

### Mount DeveloperDiskImage
```bash
# Find in /Applications/Xcode.app/Contents/Developer/Platforms/iPhoneOS.platform/DeviceSupport/
# If not found, download from https://github.com/iGhibli/iOS-DeviceSupport
$ tidevice developer
[I 210127 11:37:52 _device:518] ProductVersion: 12.4
[I 210127 11:37:52 _imagemounter:81] Pushing DeveloperDiskImage.dmg
[I 210127 11:37:52 _imagemounter:94] Push complete
[I 210127 11:37:53 _device:589] DeveloperImage mounted successfully
```

### Other
```bash
# reboot device
$ tidevice reboot

$ tidevice screenshot screenshot.jpg

# TODO(ssx): collect performance
# $ tidevice perf -o fps,mem,cpu -B com.example.demo
```

## DEVELOP
See [DEVELOP](DEVELOP.md)

## Thanks
- C implementation <https://github.com/libimobiledevice>
- <https://github.com/facebook/idb>
- Python implement of libimobiledevice: <https://github.com/iOSForensics/pymobiledevice>
- Apple Device Images: <https://github.com/iGhibli/iOS-DeviceSupport>
- <https://github.com/anonymous5l/iConsole>
- <https://github.com/troybowman/dtxmsg>
- <https://github.com/troybowman/ios_instruments_client>
- Binary of libimobiledevice for Windows <http://docs.quamotion.mobi/docs/imobiledevice/>
- [使用纯 python 实现 Instruments 协议，跨平台 (win,mac,linux) 获取 iOS 性能数据](https://testerhome.com/topics/27159)

## LICENSE
[MIT](LICENSE.md)
