# coding: utf-8
#

import os
import shutil
from typing import List

from ._safe_socket import PlistSocket
from ._utils import get_app_dir, logger
from .exceptions import MuxError


class ImageMounter(PlistSocket):
    SERVICE_NAME = "com.apple.mobile.mobile_image_mounter"

    def prepare(self):
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
        
    # def is_developer_mounted(self) -> bool:
    #     return len(self.lookup()) > 0
    
    def _check_error(self, ret: dict):
        if 'Error' in ret:
            raise MuxError(ret['Error'])

    def mount(self, image_path: str, image_signature: str, image_type="Developer"):
        assert os.path.isfile(image_path)
        assert os.path.isfile(image_signature)

        with open(image_signature, 'rb') as f:
            signature_content = f.read()

        ret = self.send_recv_packet({
            "Command": "ReceiveBytes",
            "ImageSignature": signature_content,
            "ImageSize": os.path.getsize(image_path),
            "ImageType": image_type,
        })
        self._check_error(ret)
        assert ret['Status'] == 'ReceiveBytesAck'

        # Send data through SSL
        logger.info("Pushing DeveloperDiskImage.dmg")
        chunk_size = 1<<14
        with open(image_path, "rb") as src:
            while True:
                chunk = src.read(chunk_size)
                if not chunk:
                    break
                self.sendall(chunk)

        ret = self.recv_packet()
        self._check_error(ret)
        
        assert ret['Status'] == 'Complete'
        logger.info("Push complete")

        self.send_packet({
            "Command": "MountImage",
            "ImagePath": "/private/var/mobile/Media/PublicStaging/staging.dimag",
            "ImageSignature": signature_content, # FIXME(ssx): ...
            "ImageType": image_type,
        })
        ret = self.recv_packet()
        if 'DetailedError' in ret:
            if 'is already mounted at /Developer' in ret['DetailedError']:
                raise MuxError("DeveloperImage is already mounted")
        self._check_error(ret)