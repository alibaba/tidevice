import pathlib

from genericpath import isdir
from ._sync import Sync
import logging
from ._proto import LOG


logger = logging.getLogger(LOG.main)

# Ref: https://github.com/libimobiledevice/libimobiledevice/blob/master/tools/idevicecrashreport.c

class CrashManager(object):
    def __init__(self, move_conn, copy_conn, output_dir, filter_on=False):
        self._afc = None
        self._move_coon = move_conn
        self._copy_conn = copy_conn
        self._output_dir = output_dir
        self._filter_on = filter_on
        
        self._flush()
        self._afc = Sync(self._copy_conn)
    
    def _flush(self):
        ack = b'ping\x00'
        assert ack == self._move_coon.recvall(len(ack))

    def preview(self):
        logger.info("List of crash logs:")
        r = self._afc.listdir("/")
        if str(r) != "['']":
            self._afc.treeview("/")
        else:
            logger.info("No crash logs found")

    def copy(self):
        self._afc.pull("/", self._output_dir)
        logger.info("Crash file copied to '{}' from device".format(self._output_dir))

    def move(self):
        self._afc.pull("/", self._output_dir)
        self._afc.rmtree("/")
        logger.info("Crash file moved to '{}' from device".format(self._output_dir))

    def delete(self):
        self._remove_file("/")
        logger.info("Crash file purged from device")

    def _remove_file(self, dir_path):
        files = self._afc.listdir(dir_path)
        for file in files:
            if dir_path == "/":
                file = "/{}".format(file)
            else:
                file = "{}/{}".format(dir_path, file)
            file_st = self._afc.stat(file)
            
            if file_st.is_dir():
                self._remove_file(file)
            else:
                self._afc.remove(file)
        self._afc.rmdir(dir_path)
