![tidevice](assets/tidevice-logo.png)
## tidevice

[![PyPI](https://img.shields.io/pypi/v/tidevice)](https://pypi.org/project/tidevice/)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/tidevice)](https://pypistats.org/search/tidevice)

[English](README_EN.md)

该工具能够用于与iOS设备进行通信, 提供以下功能

- 截图
- 获取手机信息
- ipa包的安装和卸载
- 根据bundleID 启动和停止应用
- 列出安装应用信息
- 模拟Xcode运行XCTest，常用的如启动WebDriverAgent测试（此方法不依赖xcodebuild)
- 获取指定应用性能(CPU,MEM,FPS)
- 其他

支持运行在Mac，Linux，Windows上

## 安装
```bash
pip3 install -U tidevice
```

## 使用

### 查看版本号
```bash
$ tidevice version
0.1.0
```

### 列出连接设备
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

### 应用管理
```bash
# 安装应用
$ tidevice install example.ipa
$ tidevice install https://example.org/example.ipa

# 卸载应用
$ tidevice uninstall com.example.demo

# 启动应用
$ tidevice launch com.example.demo

# 停止应用
$ tidevice kill com.example.demo

# 查看已安装应用
$ tidevice applist
```

### 运行WebDriverAgent
> 请先确保手机上已经安装有[WebDriverAgent](https://github.com/appium/WebDriverAgent)应用

```bash
# 运行XCTEST
$ tidevice xctest -B com.facebook.wda.WebDriverAgent.Runner
[I 210127 11:40:23 _device:909] BundleID: com.facebook.wda.WebDriverAgent.Runner
[I 210127 11:40:23 _device:911] DeviceIdentifier: 12345678901234567890abcdefg
[I 210127 11:40:23 _device:773] SignIdentity: 'Apple Development: -Your-Developer-Name-'
[I 210127 11:40:23 _device:840] Launch 'com.facebook.wda.WebDriverAgent.Runner' pid: 239
[I 210127 11:40:23 _device:1003] ProductVersion: 12.4
[I 210127 11:40:24 _device:952] Start execute test plan with IDE version: 29
[I 210127 11:40:24 _device:875] WebDriverAgent start successfully

# 修改监听端口为8200
$ tidevice xctest -B com.facebook.wda.WebDriverAgent.Runner -e USB_PORT:8200
```

启动后你就可以使用Appium 或者 [facebook-wda](https://github.com/openatx/facebook-wda) 来运行iOS自动化了

*facebook-wda example code*

```python
import wda
c = wda.USBClient()
print(c.info)
```

### 挂载开发者镜像
这个步骤其实不太需要，因为如果tidevice的命令需要开发者镜像的时候，会自动去挂载的

```bash
# 先在本地路径查找 /Applications/Xcode.app/Contents/Developer/Platforms/iPhoneOS.platform/DeviceSupport/
# 如果没有会去网站 https://github.com/iGhibli/iOS-DeviceSupport 下载，下载到路径 ~/.tidevice/device-support/
$ tidevice developer
[I 210127 11:37:52 _device:518] ProductVersion: 12.4
[I 210127 11:37:52 _imagemounter:81] Pushing DeveloperDiskImage.dmg
[I 210127 11:37:52 _imagemounter:94] Push complete
[I 210127 11:37:53 _device:589] DeveloperImage mounted successfully
```

### 其他常用
```bash
# 重启
$ tidevice reboot

# 截图
$ tidevice screenshot screenshot.jpg

# 性能采集 (TODO)
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
[MIT](LICENSE)
