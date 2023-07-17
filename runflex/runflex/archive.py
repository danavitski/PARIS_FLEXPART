#!/usr/bin/env python
import sys
from typing import List
from pathlib import Path
from loguru import logger
from pandas import DataFrame
import os
from subprocess import Popen, PIPE
from tqdm import tqdm
from multiprocessing import RLock
import tempfile
from io import FileIO


lock = RLock()


class Rclone:
    def __init__(self, address: str, max_attempts: int = 3, logfile : FileIO = sys.stdout):
        """
        :param address: location of the rclone repo
        :param max_attempts: Max number of download attempts
        """
        self.address = address
        self.max_attempts = max_attempts
        self.logfile = logfile

    def get(self, files_list: DataFrame, dest: Path, attempts_nb: int = 0, info: str = None) -> bool:
        """
        :param files_list: list of files to be downloaded
        :param dest: folder where the files need to be put
        :param attempts_nb: current number of attempts (for recursive use)
        :param info: optional message to be added to the progress bar
        :return:
        """

        # If no address has been provided, still check if the files are there
        if not self.address:
            return self.check(list(files_list.file), dest)

        # Download files one month at a time.
        # Do not pre-check the files presence, as rclone does this better.
        for files in files_list.groupby(files_list.time.dt.month):
            month = files[1].time.iloc[0].strftime('%Y/%-m')

            # Add the current month to the progress bar text
            if info is not None :
                msg = info + '; ' + month
            else :
                msg = month

            # retrieve the files:
            self.retrieve(files[1].file.values, dest, month, info=msg)

        # Check if files are there, and repeat if not.
        while not self.check(files_list.file.values, dest):
            if attempts_nb == self.max_attempts :
                return False
            return self.get(files_list, dest, attempts_nb + 1)
        return True

    def retrieve(self, files: List[str], dest: Path, source: str = '', info: str = ''):
        """
        :param files: list of files to be retrieved
        :param dest: destination directory
        :param source: source directory
        :param info: optional text added to the progress bar
        :return:
        """

        #with Lock(self.lockfile) as _:
        with lock :
            with tempfile.NamedTemporaryFile(delete=False) as fid:
                fid.writelines((file+'\n').encode() for file in files)

            msg = f'Downloading meteo from {self.address}'
            if info is not None :
                msg += f' ({info})'

            # adapted from https://gist.github.com/wholtz/14b3a3479fe9c70eefb2418f091d2103
            cmd = f'rclone copy -P {os.path.join(self.address, source)} --include-from {fid.name} {dest}'
            logger.info(cmd)
            tqdm.get_lock()
            if isinstance(self.logfile, str):
                self.logfile = open(self.logfile, 'a')

            with tqdm(total=100, desc=msg, unit="%", file=self.logfile) as pbar:
                with Popen(cmd.split(), stdout=PIPE, bufsize=1, universal_newlines=True) as proc:
                    for line in proc.stdout:
                        line = line.strip()
                        if line.startswith('Transferred:') and line.endswith('%'):
                            percent = float(line.split(',')[1].split('%')[0])
                            pbar.n = percent
                            pbar.refresh()

            if self.logfile != sys.stdout:
                self.logfile.close()

            # rename the temporary file, just for cleanliness
            Path(fid.name).unlink(missing_ok=True)

    @staticmethod
    def check(files: List[str], dest: Path) -> bool:
        files_missing = any(not Path(dest).joinpath(f).exists() for f in files)
        return not files_missing
