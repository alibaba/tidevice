![tidevice](assets/tidevice-logo.png)
## tidevice

[![PyPI](https://img.shields.io/pypi/v/tidevice)](https://pypi.org/project/tidevice/)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/tidevice)](https://pypistats.org/search/tidevice)

[English](README_EN.md)

QQ交流群: _134535547_  (进群答案: 自己猜吧，不行就问gpt)

该工具能够用于与iOS设备进行通信, 提供以下功能

- 截图
- 获取手机信息
- ipa包的安装和卸载
- 根据bundleID 启动和停止应用
- 列出安装应用信息
- 模拟Xcode运行XCTest，常用的如启动WebDriverAgent测试（此方法不依赖xcodebuild)
- 获取指定应用性能(CPU,MEM,FPS)
- 获取指定应用功耗(CPU,GPU,network,display,location)
- 文件操作
- Crash日志操作
- 其他

支持运行在Mac，Linux，Windows上

## 赞助商
[![霍格沃兹测试开发学社](https://testing-studio.com/img/icon.png)](https://qrcode.testing-studio.com/f?from=tidevice&url=https://testing-studio.com/)

霍格沃兹测试开发学社：中国软件测试开发高端教育品牌，产品由国内顶尖软件测试开发技术专家携手打造。为企业与个人提供专业的技能培训与咨询、测试工具与测试平台、测试外包与测试众包服务。领域涵盖App/Web自动化测试、接口自动化测试、性能测试、安全测试、持续交付/DevOps、测试左移、测试右移、精准测试、测试平台开发、测试管理等方向，[**联系我们**](https://qrcode.testing-studio.com/f?from=tidevice&url=https://ceshiren.com/t/topic/23806)


## 安装

Python 3.6+

```bash
pip3 install -U "tidevice[openssl]"   # Recommend
```

如果上面的命令提示安装失败，就试试下面的命令。（不过这种方法安装，配对功能就没有了，因为没有办法进行签名）

```bash
pip3 install -U tidevice
```

> Windows电脑需要安装并启动Itunes

## 使用

> 使用--trace选项可以查看socket数据流

### 手机配置
iOS 16的手机需要手工开启开发者选项。
开启方法：设置->隐私与安全性->开发者模式 （打开），然后会提示重启 （点击 重新启动） -> 启动后会弹窗 是否打开“开发者模式”？（点击打开）


### 查看版本号
```bash
$ tidevice version
0.1.0
```

### 配对
```bash
$ tidevice pair
# 配对设备

$ tidevice unpair
# 取消配对设备
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

# 指定设备安装
$ tidevice --udid $UDID install https://example.org/example.ipa

# 卸载应用
$ tidevice uninstall com.example.demo

# 启动应用
$ tidevice launch com.example.demo

# 停止应用
$ tidevice kill com.example.demo

# 查看已安装应用
$ tidevice applist

# 查看运行中的应用
$ tidevice ps
$ tidevice ps --json output as json
```

### Run XCTest
> 请先确保手机上已经安装有[WebDriverAgent](https://github.com/appium/WebDriverAgent)应用

```bash
# 运行XCTEST
$ tidevice xcuitest -B com.facebook.wda.WebDriverAgent.Runner
[I 210127 11:40:23 _device:909] BundleID: com.facebook.wda.WebDriverAgent.Runner
[I 210127 11:40:23 _device:911] DeviceIdentifier: 12345678901234567890abcdefg
[I 210127 11:40:23 _device:773] SignIdentity: 'Apple Development: -Your-Developer-Name-'
[I 210127 11:40:23 _device:840] Launch 'com.facebook.wda.WebDriverAgent.Runner' pid: 239
[I 210127 11:40:23 _device:1003] ProductVersion: 12.4
[I 210127 11:40:24 _device:952] Start execute test plan with IDE version: 29
[I 210127 11:40:24 _device:875] WebDriverAgent start successfully

# 修改监听端口为8200, 并显示调试日志
$ tidevice xcuitest -B com.facebook.wda.WebDriverAgent.Runner -e USE_PORT:8200 --debug
```

### Relay
```
# 转发请求到手机，类似于iproxy
$ tidevice relay 8100 8100

# 转发并把传输的内容用hexdump的方法print出来
$ tidevice relay -x 8100 8100
```

### 运行WebDriverAgent
目前已知的几个问题

- 不支持运行企业证书签名的WDA
- 数据线可能导致wda连接中断。作者用的数据线(推荐): <https://item.jd.com/44473991638.html>

wdaproxy这个命令会同时调用xctest和relay，另外当wda退出时，会自动重新启动xctest

```bash
# 运行 XCTest 并在PC上监听8200端口转发到手机8100服务
$ tidevice wdaproxy -B com.facebook.wda.WebDriverAgent.Runner --port 8200
...logs...
```

启动后你就可以使用Appium 或者 [facebook-wda](https://github.com/openatx/facebook-wda) 来运行iOS自动化了

*facebook-wda example code*

```python
import wda
c = wda.Client("http://localhost:8200")
print(c.info)
```

*Appium* 需要下面几个配置需要设置一下
```
"usePrebuiltWDA": "false",
"useXctestrunFile": "false",
"skipLogCapture": "true"
```

需要在Windows上运行Appium+iOS自动化可以参考下面的帖子 <https://testerhome.com/topics/29230>
Ref issue [#46](https://github.com/alibaba/taobao-iphone-device/issues/46)

### 运行XCTest UITest
这个不是Unit Tests，而是UITests。具体可以看这里的解释说明 <https://fbidb.io/docs/test-execution>

以这个项目为例: https://github.com/FeiHuang93/XCTest-Demo
应用分为执行测试的应用 testXCTestUITests 和 被测应用 testXCTest

执行方法

```bash
$ tidevice xcuitest --bundle-id philhuang.testXCTestUITests.xctrunner --target-bundle-id philhuang.testXCTest
# ... 省略一部分不重要的信息 ...
[I 210301 15:37:07 _device:887] logProcess: 2021-03-01 15:37:07.924620+0800 testXCTestUITests-Runner[81644:13765443] Running tests...
[I 210301 15:37:07 _device:984] Test runner ready detected
[I 210301 15:37:07 _device:976] Start execute test plan with IDE version: 29
[I 210301 15:37:07 _device:887] logProcess: Test Suite 'All tests' started at 2021-03-01 15:37:08.009
    XCTestOutputBarrier
[I 210301 15:37:07 _device:887] logProcess: Test Suite 'testXCTestUITests.xctest' started at 2021-03-01 15:37:08.010
    XCTestOutputBarrierTest Suite 'testXCTestUITests' started at 2021-03-01 15:37:08.010
[I 210301 15:37:07 _device:887] logProcess: XCTestOutputBarrier
[I 210301 15:37:07 _device:887] logProcess: Test Case '-[testXCTestUITests testExample]' started.
    XCTestOutputBarrier
[I 210301 15:37:07 _device:887] logProcess:     t =     0.00s Start Test at 2021-03-01 15:37:08.010
[I 210301 15:37:07 _device:887] logProcess:     t =     0.00s Set Up
[I 210301 15:37:07 _device:887] logProcess: 2021-03-01 15:37:08.010828+0800 testXCTestUITests-Runner[81644:13765443] testExample start
[I 210301 15:37:07 _device:887] logProcess:     t =     0.00s     Open philhuang.testXCTest
[I 210301 15:37:07 _device:887] logProcess:     t =     0.00s         Launch philhuang.testXCTest
[I 210301 15:37:08 _device:887] logProcess:     t =     0.04s             Wait for accessibility to load
[I 210301 15:37:08 _device:887] logProcess:     t =     0.04s             Setting up automation session
[I 210301 15:37:08 _device:887] logProcess:     t =     0.10s             Wait for philhuang.testXCTest to idle
[I 210301 15:37:09 _device:887] logProcess:     t =     1.13s Tear Down
[I 210301 15:37:09 _device:887] logProcess: Test Case '-[testXCTestUITests testExample]' passed (1.337 seconds).
[I 210301 15:37:09 _device:887] logProcess: XCTestOutputBarrier
[I 210301 15:37:09 _device:887] logProcess: Test Suite 'testXCTestUITests' passed at 2021-03-01 15:37:09.349.
    	 Executed 1 test, with 0 failures (0 unexpected) in 1.337 (1.339) seconds
    XCTestOutputBarrier
[I 210301 15:37:09 _device:887] logProcess: Test Suite 'testXCTestUITests.xctest' passed at 2021-03-01 15:37:09.350.
    	 Executed 1 test, with 0 failures (0 unexpected) in 1.337 (1.340) seconds
[I 210301 15:37:09 _device:887] logProcess: XCTestOutputBarrier
[I 210301 15:37:09 _device:887] logProcess: Test Suite 'All tests' passed at 2021-03-01 15:37:09.352.
    	 Executed 1 test, with 0 failures (0 unexpected) in 1.337 (1.343) seconds
    XCTestOutputBarrier
[I 210301 15:37:09 _device:887] logProcess: XCTestOutputBarrier
[I 210301 15:37:09 _device:1059] xctrunner quited
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

# 下载所有镜像到本地
$ tidevice developer --download-all
```

# 查看设备信息
```bash
$ tidevice info

# 查看设备电源信息
$ tidevice info --domain com.apple.mobile.battery --json
{
    "BatteryCurrentCapacity": 53,
    "BatteryIsCharging": true,
    "ExternalChargeCapable": true,
    "ExternalConnected": true,
    "FullyCharged": false,
    "GasGaugeCapability": true,
    "HasBattery": true
}
```

Known domains are:

```text
com.apple.disk_usage
com.apple.disk_usage.factory
com.apple.mobile.battery
com.apple.iqagent
com.apple.purplebuddy
com.apple.PurpleBuddy
com.apple.mobile.chaperone
com.apple.mobile.third_party_termination
com.apple.mobile.lockdownd
com.apple.mobile.lockdown_cache
com.apple.xcode.developerdomain
com.apple.international
com.apple.mobile.data_sync
com.apple.mobile.tethered_sync
com.apple.mobile.mobile_application_usage
com.apple.mobile.backup
com.apple.mobile.nikita
com.apple.mobile.restriction
com.apple.mobile.user_preferences
com.apple.mobile.sync_data_class
com.apple.mobile.software_behavior
com.apple.mobile.iTunes.SQLMusicLibraryPostProcessCommands
com.apple.mobile.iTunes.accessories
com.apple.mobile.internal
com.apple.mobile.wireless_lockdown
com.apple.fairplay
com.apple.iTunes
com.apple.mobile.iTunes.store
com.apple.mobile.iTunes
```

### 文件操作
```bash

# 查看相册内容
$ tidevice fsync /DCIM/

# 查看T3出行Documents中的内容
$ tidevice fsync -B com.t3go.passenger ls /Documents/

# 下载目录（也支持文件）
$ tidevice pull /Documents ./TmpDocuments/

# 其他操作 rm cat pull push stat tree rmtree mkdir
$ tidevice fsync -h

# 支持查看 /Documents 的App
# com.apple.iMovie iMovie
# com.apple.mobilegarageband 库乐队
# com.apple.clips 可立拍
# com.t3go.passenger T3出行
# com.dji.golite DJI Fly
# com.duokan.reader 多看阅读
```

### Crash日志操作
```bash
usage: tidevice crashreport [-h] [--list] [--keep] [--clear] [output_directory]

positional arguments:
  output_directory  The output dir to save crash logs synced from device (default: None)

optional arguments:
  -h, --help        show this help message and exit
  --list            list all crash files (default: False)
  --keep            copy but do not remove crash reports from device (default: False)
  --clear           clear crash files (default: False)
```

### 其他常用
```bash
# 重启
$ tidevice reboot

# 截图
$ tidevice screenshot screenshot.jpg

# 输出日志 same as idevicesyslog
$ tidevice syslog
```

### 性能采集
使用命令行可以直接看到结果，不过最好还是用接口获取

```bash
# 性能采集
$ tidevice perf -B com.example.demo --json

cpu {"timestamp": 1671173334888, "pid": 18717, "value": 0.0, "sys_value": 53.26736370425692, "count": 6}
memory {"pid": 18717, "timestamp": 1671173334888, "value": 10.20428466796875}
gpu {"device": 0, "renderer": 0, "tiler": 0, "value": 0, "timestamp": 1671173331745}
fps {"fps": 0, "value": 0, "timestamp": 1671173331745}
network {"connection-detected": {"Local": "[fe80::5cd8:6aff:fe80:78c3]:54658", "Remote": "[::]:0", "InterfaceIndex": 10, "Pid": -2, "RecvBufferSize": 131072, "RecvBufferUsed": 0, "SerialNumber": 14, "Protocol": "tcp6"}, "timestamp": 1671173331756}
network {"interface-detection": {"InterfaceIndex": 10, "Name": "anpi0"}, "timestamp": 1671173331767}
network {"interface-detection": {"InterfaceIndex": 14, "Name": "en0"}, "timestamp": 1671173331767}
network {"connection-update": {"RxPackets": 2, "RxBytes": 72, "TxPackets": 3, "TxBytes": 163, "RxDups": null, "RxOOO": null, "TxRetx": null, "MinRTT": 0.039375, "AvgRTT": 0.042, "ConnectionSerial": 56, "Time": 2}, "timestamp": 1671173335754}
...
```

```bash
# 功耗采集
# 每一秒打印一行JSON，至于里面什么单位不太懂
$ tidevice energy com.example.demo
{"energy.overhead": 490.0, "kIDEGaugeSecondsSinceInitialQueryKey": 1209, "energy.version": 1, "energy.gpu.cost": 0, "energy.cpu.cost": 62.15080582703523, "energy.networkning.overhead": 500, "energy.appstate.cost": 8, "energy.location.overhead": 0, "energy.thermalstate.cost": 0, "energy.networking.cost": 501.341030606293, "energy.cost": 767.8212481980341, "energy.display.cost": 214.3294117647059, "energy.cpu.overhead": 0, "energy.location.cost": 0, "energy.gpu.overhead": 0, "energy.appstate.overhead": 0, "energy.display.overhead": 0, "energy.inducedthermalstate.cost": -1}
```

How to get app performance in python

```python
import time
import tidevice
from tidevice._perf import DataType

t = tidevice.Device()
perf = tidevice.Performance(t, [DataType.CPU, DataType.MEMORY, DataType.NETWORK, DataType.FPS, DataType.PAGE, DataType.SCREENSHOT, DataType.GPU])
#  tidevice version <= 0.4.16:
#  perf = tidevice.Performance(t)

def callback(_type: tidevice.DataType, value: dict):
    print("R:", _type.value, value)


perf.start("com.apple.Preferences", callback=callback)
time.sleep(10)
perf.stop()
```


## DEVELOP
See [DEVELOP](DEVELOP.md)

Python code style(ZH): https://zh-google-styleguide.readthedocs.io/en/latest/google-python-styleguide/python_style_rules/#comments

## Alternatives
- <https://github.com/danielpaulus/go-ios>
- Go implemented: <https://github.com/electricbubble/gidevice>
- https://github.com/SonicCloudOrg/sonic-ios-bridge
- https://github.com/doronz88/pymobiledevice3 这个库用到的服务很全，还是Python的，参考起来更方便

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
