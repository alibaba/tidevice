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
- retrieve energy data
- simulate run xctest, eg: WebDriverAgent
- file operation
- crash log operation
- other

Support platform: Mac, Linux, Windows

## Install
Python 3.6+

```bash
pip3 install -U "tidevice[openssl]"   # Recommend
```

The extra *openssl*, contains device pair support. If can install it, try

```bash
pip3 install -U tidevice
```

> Windows need to install and launch iTunes

## Usage

### Show version number
```bash
$ tidevice version
0.1.0
```

### Pair
```bash
$ tidevice pair
# pair device

$ tidevice unpair
# unpair device
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

# Specify device udid to install
$ tidevice --udid $UDID install https://example.org/example.ipa

$ tidevice uninstall com.example.demo

$ tidevice launch com.example.demo

$ tidevice kill com.example.demo

# show installed app list
$ tidevice applist

# show running app list
$ tidevice ps
$ tidevice ps --json output as json
```

### Run XCTest
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

# Change WDA listen port to 8200 and show debug log
$ tidevice xctest -B com.facebook.wda.WebDriverAgent.Runner -e USE_PORT:8200 --debug
```

### Relay
```
# proxy local tcp request to phone, alternative: iproxy
$ tidevice relay 8100 8100

# relay and show traffic data with hexdump
$ tidevice relay -x 8100 8100
```

### Run WebDriverAgent
command:`wdaproxy` invoke `xctest` and `relay`, with watchers to keep xctest always running

```bash
# 运行 XCTest 并在PC上监听8200端口转发到手机8100服务
$ tidevice wdaproxy -B com.facebook.wda.WebDriverAgent.Runner --port 8200
...logs...
```

Then you can connect with Appium or [facebook-wda](https://github.com/openatx/facebook-wda)

*facebook-wda example code*

```python
import wda
c = wda.Client("http://localhost:8200")
print(c.info)
```

### Run UITests
Demo <https://github.com/FeiHuang93/XCTest-Demo>

- `philhuang.testXCTestUITests.xctrunner` is the test to launch
- `philhuang.testXCTest` is the app to test
 
 ```bash
$ tidevice xctest --bundle-id philhuang.testXCTestUITests.xctrunner --target-bundle-id philhuang.testXCTest
# ... ignore some not important part ...
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

### Mount DeveloperDiskImage
```bash
# Find in /Applications/Xcode.app/Contents/Developer/Platforms/iPhoneOS.platform/DeviceSupport/
# If not found, download from https://github.com/iGhibli/iOS-DeviceSupport
$ tidevice developer
[I 210127 11:37:52 _device:518] ProductVersion: 12.4
[I 210127 11:37:52 _imagemounter:81] Pushing DeveloperDiskImage.dmg
[I 210127 11:37:52 _imagemounter:94] Push complete
[I 210127 11:37:53 _device:589] DeveloperImage mounted successfully

# Download all developer image to local
$ tidevice developer --download-all
```

### Check device info
```bash
$ tidevice info

# check device power info
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

### File operation
```bash
# show photo dir
$ tidevice fsync /DCIM/

# inspect files in app iMovie
$ tidevice fsync -B com.apple.iMovie ls /Documents/

# download directory (also support pull single file)
$ tidevice pull /Documents ./TmpDocuments/

# 其他操作 rm cat pull push stat tree rmtree mkdir
$ tidevice fsync -h

# Supported inspect /Documents apps
# com.apple.iMovie iMovie
# com.apple.mobilegarageband 库乐队
# com.apple.clips 可立拍
# com.t3go.passenger T3出行
# com.dji.golite DJI Fly
# com.duokan.reader 多看阅读
```


### Crash log operation
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

### Other
```bash
# reboot device
$ tidevice reboot

$ tidevice screenshot screenshot.jpg

# same as idevicesyslog
$ tidevice syslog
```

### Performance
How to use in command line

```bash
$ tidevice perf -B com.example.demo
fps {'fps': 0, 'value': 0, 'timestamp': 1620725299495}
network {'timestamp': 1620725300511, 'downFlow': 55685.94921875, 'upFlow': 2300.96484375}
screenshot {'value': <PIL.PngImagePlugin.PngImageFile image mode=RGB size=231x500 at 0x1037CF760>, 'timestamp': 1620725301374}
fps {'fps': 58, 'value': 58, 'timestamp': 1620725873152}
cpu {'timestamp': 1620725873348, 'pid': 21243, 'value': 1.2141945711006428}
memory {'pid': 21243, 'timestamp': 1620725873348, 'value': 40.54920196533203}
```

### Energy
How to use in command line
```bash
$ tidevice energy com.example.demo
{"energy.overhead": 490.0, "kIDEGaugeSecondsSinceInitialQueryKey": 1209, "energy.version": 1, "energy.gpu.cost": 0, "energy.cpu.cost": 62.15080582703523, "energy.networkning.overhead": 500, "energy.appstate.cost": 8, "energy.location.overhead": 0, "energy.thermalstate.cost": 0, "energy.networking.cost": 501.341030606293, "energy.cost": 767.8212481980341, "energy.display.cost": 214.3294117647059, "energy.cpu.overhead": 0, "energy.location.cost": 0, "energy.gpu.overhead": 0, "energy.appstate.overhead": 0, "energy.display.overhead": 0, "energy.inducedthermalstate.cost": -1}
```

Example with python

```python
import time
import tidevice

t = tidevice.Device()
perf = tidevice.Performance(t)


def callback(_type: tidevice.DataType, value: dict):
    print("R:", _type.value, value)


perf.start("com.apple.Preferences", callback=callback)
time.sleep(10)
perf.stop()
```

## Alternative
- https://github.com/danielpaulus/go-ios
- https://github.com/electricbubble/gidevice
- https://github.com/SonicCloudOrg/sonic-ios-bridge

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
