![tidevice](assets/tidevice-logo.png)
## tidevice

[![PyPI](https://img.shields.io/pypi/v/tidevice)](https://pypi.org/project/tidevice/)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/tidevice)](https://pypistats.org/search/tidevice)

[English](README_EN.md)

该工具能够用于与iOS设备进行通信, 提供以下功能

- ipa包的安装和卸载
- 根据bundleID 启动和停止应用
- 列出安装应用信息
- 获取指定应用性能(CPU,MEM,FPS)
- 截图
- 模拟Xcode运行XCTest，如启动WebDriverAgent测试（改方法不依赖xcodebuild)
- 其他

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

### 运行XCTest
```bash
# 运行XCTEST
$ tidevice xctest -B com.facebook.wda.WebDriverAgent.Runner
```

### 其他常用
```bash
# 挂载开发者镜像
$ tidevice developer

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
- <https://github.com/troybowman/dtxmsg>
- <https://github.com/troybowman/ios_instruments_client>
- Binary of libimobiledevice for Windows <http://docs.quamotion.mobi/docs/imobiledevice/>
- [使用纯 python 实现 Instruments 协议，跨平台 (win,mac,linux) 获取 iOS 性能数据](https://testerhome.com/topics/27159)

## LICENSE
[MIT](LICENSE)
