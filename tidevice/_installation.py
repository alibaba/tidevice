# coding: utf-8
# created: codeskyblue 2020/06/11
#
# ideviceinstaller -i .... ipa
# Copying 'WebDriverAgentRunner-Runner-resign.ipa' to device... DONE.
# Installing 'com.facebook.WebDriverAgentRunner.xctrunner'
#  - CreatingStagingDirectory (5%)
#  - ExtractingPackage (15%)
#  - InspectingPackage (20%)
#  - TakingInstallLock (20%)
#  - PreflightingApplication (30%)
#  - InstallingEmbeddedProfile (30%)
#  - VerifyingApplication (40%)
#  - CreatingContainer (50%)
#  - InstallingApplication (60%)
#  - PostflightingApplication (70%)
#  - SandboxingApplication (80%)
#  - GeneratingApplicationMap (90%)
#  - Complete

import logging
from typing import Optional

from ._proto import LOG
from ._safe_socket import PlistSocketProxy
from .exceptions import ServiceError

logger = logging.getLogger(LOG.main)


class Installation(PlistSocketProxy):
    SERVICE_NAME = "com.apple.mobile.installation_proxy"

    def install(self, bundle_id: str, target_path: str):
        """
        Args:
            bundle_id (str): package bundle id
            target_path(str): AppleFileSystem path
        
        Raises:
            ServiceError
        """
        self.send_packet({
            'Command': 'Install',
            'ClientOptions': {
                'CFBundleIdentifier': bundle_id,
            },
            'PackagePath': target_path
        })
        while True:
            progress = self.recv_packet()
            if progress.get("Status") == 'Complete':
                print("Complete")
                return bundle_id
            if 'Error' in progress:
                logger.error("%s", progress['Error'])
                logger.error("%s", progress.get("ErrorDescription"))
                raise ServiceError(progress['Error'])
            print("- {Status} ({PercentComplete}%)".format(**progress))

    def uninstall(self, bundle_id: str) -> bool:
        self.send_packet({
            "Command": "Uninstall",
            "ApplicationIdentifier": bundle_id
        })
        print("Uninstalling {!r}".format(bundle_id))
        while True:
            data = self.recv_packet()
            if data.get("Status") == 'Complete':
                print("Complete", flush=True)
                return True
            if 'Error' in data:
                logger.error("%s", data['Error'])
                logger.error("%s", data.get("ErrorDescription"))
                return False
            print("- {Status} ({PercentComplete}%)".format(**data), flush=True)

    def lookup(self, bundle_id: str) -> Optional[dict]:
        """
        Returns:
            LookupResult(dict) or None
        
        Protocol response:
        {'Status': 'Complete',
         'LookupResult': {
            'com.facebook.WebDriverAgentRunner.xctrunner': {
                'ApplicationType': 'User',
                'CFBundleIdentifier': 'com.facebook.WebDriverAgentRunner.xctrunner',
                'CFBundlePackageType': 'APPL',
                'CFBundleDisplayName': 'WebDriverAgentRunner-Runner',
                'CFBundleSignature': '????',
                'CFBundleInfoDictionaryVersion': '6.0',
                'CFBundleSupportedPlatforms': ['iPhoneOS'],
                'CFBundleNumericVersion': 16809984,
                'CFBundleName': 'WebDriverAgentRunner-Runner',
                'CFBundleShortVersionString': '1.0',
                'CFBundleExecutable': 'WebDriverAgentRunner-Runner',
                'CFBundleAllowMixedLocalizations': True,
                'CFBundleVersion': '1',
                'CFBundleDevelopmentRegion': 'en',
                'Container': '/private/var/mobile/Containers/Data/Application/7CA19F56-4CA2-40F5-A785-954174BD3AEF',
                'Path': '/private/var/containers/Bundle/Application/0A608C62-FBE7-43C0-B083-78F27AC5FF8E/WebDriverAgentRunner-Runner.app',
                'SignerIdentity': 'Apple Development: Shengxiang Sun (2YZG5Q7P9P)',
                'EnvironmentVariables': {'CFFIXED_USER_HOME': '/private/var/mobile/Containers/Data/Application/7CA19F56-4CA2-40F5-A785-954174BD3AEF',
                    'TMPDIR': '/private/var/mobile/Containers/Data/Application/7CA19F56-4CA2-40F5-A785-954174BD3AEF/tmp',
                    'HOME': '/private/var/mobile/Containers/Data/Application/7CA19F56-4CA2-40F5-A785-954174BD3AEF'},
                'BuildMachineOSBuild': '19E211',
                'MinimumOSVersion': '8.0',
                'LSRequiresIPhoneOS': True,
                'ProfileValidated': True,
                'SequenceNumber': 1624,
                'IsDemotedApp': False,
                'IsUpgradeable': True,
                'UIDeviceFamily': [1, 2],
                'UIRequiresFullScreen': True,
                'UIBackgroundModes': ['continuous'],
                'UIRequiredDeviceCapabilities': ['armv7'],
                'UISupportedInterfaceOrientations': ['UIInterfaceOrientationPortrait',
                    'UIInterfaceOrientationLandscapeLeft',
                    'UIInterfaceOrientationLandscapeRight'],
                'NSBluetoothAlwaysUsageDescription': 'Access is necessary for automated testing.',
                'NFCReaderUsageDescription': 'Access is necessary for automated testing.',
                'NSSiriUsageDescription': 'Access is necessary for automated testing.',
                'NSCameraUsageDescription': 'Access is necessary for automated testing.',
                'NSRemindersUsageDescription': 'Access is necessary for automated testing.',
                'NSHealthClinicalHealthRecordsShareUsageDescription': 'Access is necessary for automated testing.',
                'NSHealthUpdateUsageDescription': 'Access is necessary for automated testing.',
                'NSMotionUsageDescription': 'Access is necessary for automated testing.',
                'NSPhotoLibraryAddUsageDescription': 'Access is necessary for automated testing.',
                'NSHealthShareUsageDescription': 'Access is necessary for automated testing.',
                'NSAppleMusicUsageDescription': 'Access is necessary for automated testing.',
                'NSSpeechRecognitionUsageDescription': 'Access is necessary for automated testing.',
                'NSLocationUsageDescription': 'Access is necessary for automated testing.',
                'NSCalendarsUsageDescription': 'Access is necessary for automated testing.',
                'NSMicrophoneUsageDescription': 'Access is necessary for automated testing.',
                'NSLocationWhenInUseUsageDescription': 'Access is necessary for automated testing.',
                'NSFaceIDUsageDescription': 'Access is necessary for automated testing.',
                'NSLocationAlwaysAndWhenInUseUsageDescription': 'Access is necessary for automated testing.',
                'NSHomeKitUsageDescription': 'Access is necessary for automated testing.',
                'NSPhotoLibraryUsageDescription': 'Access is necessary for automated testing.',
                'NSAppTransportSecurity': {'NSAllowsArbitraryLoads': True},
                'Entitlements': {
                    'keychain-access-groups': ['M75PC2L4UP.com.facebook.WebDriverAgentRunner.xctrunner'],
                    'application-identifier': 'M75PC2L4UP.com.facebook.WebDriverAgentRunner.xctrunner',
                    'get-task-allow': True,
                    'com.apple.developer.team-identifier': 'M75PC2L4UP'},
                'DTPlatformVersion': '13.4',
                'DTSDKBuild': '17E218',
                'DTXcodeBuild': '11E605b',
                'DTPlatformName': 'iphoneos',
                'DTCompiler': 'com.apple.compilers.llvm.clang.1_0',
                'DTSDKName': 'iphoneos13.4.internal',
                'DTPlatformBuild': '17E218',
                'DTXcode': '1150'}
            }
        }
        """
        self.psock.send_packet({
            "Command": "Lookup",
            "ClientOptions": {
                "BundleIDs": [bundle_id]
            }
        })
        ret = self.psock.recv_packet()
        # Most used attributes
        # ApplicationType
        # CFBundleDisplayName
        # CFBundleExecutable
        # Path
        assert ret['Status'] == 'Complete'
        return ret['LookupResult'].get(bundle_id)

    def iter_installed(self, app_type: Optional[str] = "User", attrs: Optional[list]=None):
        """
        Args:
            app_type (str): one of ['User', 'System']
            attrs: list
        
        Example attrs:
            ['ApplicationType',
            'CFBundleDisplayName',
            'CFBundleExecutable',
            "CFBundleIdentifier",
            'CFBundleName',
            'CFBundleShortVersionString',
            'CFBundleVersion',
            'Container',
            'Entitlements',
            'EnvironmentVariables',
            'MinimumOSVersion',
            'Path',
            'ProfileValidated',
            'SBAppTags',
            'SignerIdentity',
            'UIDeviceFamily',
            'UIRequiredDeviceCapabilities']
        
        Example protocol response:
            {'Status': 'BrowsingApplications',
            'CurrentAmount': 9,
            'CurrentIndex': 0,
            'CurrentList': [{'ApplicationType': 'User',
                            'CFBundleDisplayName': 'Demo应用',
                            'CFBundleIdentifier': 'com.example.demo',
                            等等
                            },...]
        }
        """
        options = {}
        if app_type:
            options["ApplicationType"] = app_type
        if attrs:
            options['ReturnAttributes'] = attrs
        # options['ShowLaunchProhibitedApps'] = True 

        self.psock.send_packet({
            "Command": "Browse",
            "ClientOptions": options,
        })
        # })
        while True:
            data = self.psock.recv_packet()
            if data['Status'] == 'Complete':
                break
            for appinfo in data['CurrentList']:
                yield appinfo


