# tidevice

[中文文档](README_CN.md)

Command line tool to communicate with iOS device, support the following functions

- ipa install and uninstall
- launch and kill app
- list installed app info
- retrieve performance data
- screenshot
- simulate run xctest, eg: WebDriverAgent
- other

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

### Run XCTest
```bash
$ tidevice xctest -B com.facebook.wda.WebDriverAgent.Runner
```

### Other
```bash
# mount developer image (need more test)
$ tidevice developer

# reboot device
$ tidevice reboot

$ tidevice screenshot screenshot.jpg

# collect performance (not ready yet)
$ tidevice perf -o fps,mem,cpu -B com.example.demo
```

## DEVELOP
See [DEVELOP](DEVELOP.md)

## Thanks
- C implementation <https://github.com/libimobiledevice>
- Python implement of libimobiledevice: <https://github.com/iOSForensics/pymobiledevice>
- Apple Device Images: <https://github.com/iGhibli/iOS-DeviceSupport>
- <https://github.com/troybowman/dtxmsg>
- <https://github.com/troybowman/ios_instruments_client>
- Binary of libimobiledevice for Windows <http://docs.quamotion.mobi/docs/imobiledevice/>
- [使用纯 python 实现 Instruments 协议，跨平台 (win,mac,linux) 获取 iOS 性能数据](https://testerhome.com/topics/27159)

## LICENSE
[MIT](LICENSE.md)
