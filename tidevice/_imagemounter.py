# coding: utf-8
#

import os
import shutil
import time
import typing
import zipfile
from typing import List

import retry
import requests

from ._safe_socket import PlistSocketProxy
from ._utils import get_app_dir, logger
from .exceptions import MuxError, MuxServiceError

_REQUESTS_TIMEOUT = 30.0


@retry.retry(exceptions=requests.ReadTimeout, tries=5, delay=.5)
def _urlretrieve(url, local_filename):
    """ download url to local """
    logger.info("Download %s -> %s", url, local_filename)

    try:
        tmp_local_filename = local_filename + f".download-{int(time.time()*1000)}"
        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'}
        with requests.get(url, headers=headers, stream=True, timeout=_REQUESTS_TIMEOUT) as r:
            r.raise_for_status()
            with open(tmp_local_filename, 'wb') as f:
                shutil.copyfileobj(r.raw, f, length=16<<20)
                f.flush()
            os.rename(tmp_local_filename, local_filename)
            logger.info("%r download successfully", local_filename)
    finally:
        if os.path.isfile(tmp_local_filename):
            os.remove(tmp_local_filename)
            

def get_developer_image_url_list(version: str) -> typing.List[str]:
    """ return url list which may contains mirror url """
    # https://github.com/JinjunHan/iOSDeviceSupport
    github_repo = "JinjunHan/iOSDeviceSupport"
    zip_name = f"{version}.zip"

    # the code.aliyun slowlly
    # gitee requires login
    # aliyun_url = f"https://code.aliyun.com/hanjinjun/iOSDeviceSupoort/raw/master/DeviceSupport/{zip_name}"
    origin_url = f"https://github.com/{github_repo}/raw/master/DeviceSupport/{zip_name}"
    mirror_url = origin_url.replace("https://github.com", "https://tool.appetizer.io")
    return (mirror_url, origin_url)

def cache_developer_image(version: str) -> str:
    """
    download developer image from github to local
    return image_zip_path
    """
    _alias = {
        "12.5": "12.4",
    }
    if version in _alias:
        version = _alias[version]
        logger.info("Use alternative developer image %s", version)

    # $HOME/.tidevice/device-support/12.2.zip
    local_device_support = get_app_dir("device-support")
    image_zip_path = os.path.join(local_device_support, version+".zip")
    if not zipfile.is_zipfile(image_zip_path):
        urls = get_developer_image_url_list(version)

        err = None
        for url in urls:
            try:
                _urlretrieve(url, image_zip_path)
                if zipfile.is_zipfile(image_zip_path):
                    err = None
                    break
                err = Exception("image file not zip")
            except requests.HTTPError as e:
                err = e
                if e.response.status_code == 404:
                    break
            except requests.RequestException as e:
                err = e
        if err:
            raise err
    return image_zip_path


class ImageMounter(PlistSocketProxy):
    SERVICE_NAME = "com.apple.mobile.mobile_image_mounter"

    def prepare(self):
        """
        Note: LookupImage might stuck and no response
        """
        return super().prepare()
    
    def lookup(self, image_type="Developer") -> List[bytes]:
        """
        Check image signature
        """
        ret = self.send_recv_packet({
            "Command": "LookupImage",
            "ImageType": image_type,
        })
        if 'Error' in ret:
            raise MuxError(ret['Error'])
        return ret.get('ImageSignature', [])
        
    def is_developer_mounted(self) -> bool:
        """
        Check if developer image mounted

        Raises:
            MuxError("DeviceLocked")
        """
        return len(self.lookup()) > 0
    
    def _check_error(self, ret: dict):
        if 'Error' in ret:
            raise MuxError(ret['Error'])

    def mount(self,
                image_path: str,
                image_signature_path: str):
        """ Mount developer disk image from local files """
        assert os.path.isfile(image_path), image_path
        assert os.path.isfile(image_signature_path), image_signature_path
        
        logger.debug("image path: %s, %s", image_path, image_signature_path)
        with open(image_signature_path, 'rb') as f:
            signature_content = f.read()
        
        image_size = os.path.getsize(image_path)

        with open(image_path, "rb") as image_reader:
            return self.mount_fileobj(image_reader, image_size, signature_content)
        
    def mount_fileobj(self,
                image_reader: typing.IO,
                image_size: int,
                signature_content: bytes,
                image_type: str = "Developer"):

        ret = self.send_recv_packet({
            "Command": "ReceiveBytes",
            "ImageSignature": signature_content,
            "ImageSize": image_size,
            "ImageType": image_type,
        })
        self._check_error(ret)
        assert ret['Status'] == 'ReceiveBytesAck'

        # Send data through SSL
        logger.info("Pushing DeveloperDiskImage.dmg")
        chunk_size = 1<<14

        while True:
            chunk = image_reader.read(chunk_size)
            if not chunk:
                break
            self.psock.sendall(chunk)

        ret = self.psock.recv_packet()
        self._check_error(ret)
        
        assert ret['Status'] == 'Complete'
        logger.info("Push complete")

        self.psock.send_packet({
            "Command": "MountImage",
            "ImagePath": "/private/var/mobile/Media/PublicStaging/staging.dimag",
            "ImageSignature": signature_content, # FIXME(ssx): ...
            "ImageType": image_type,
        })
        ret = self.psock.recv_packet()
        if 'DetailedError' in ret:
            if 'is already mounted at /Developer' in ret['DetailedError']:
                raise MuxError("DeveloperImage is already mounted")
        self._check_error(ret)
