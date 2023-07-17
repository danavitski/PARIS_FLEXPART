#!/usr/bin/env python
import sys

from pandas import Timedelta, Timestamp, date_range, DataFrame
from dataclasses import dataclass
from datetime import datetime
from loguru import logger
import os
from pathlib import Path
import glob
from numpy import array, argsort
from runflex.archive import Rclone
import io


@dataclass(kw_only=True)
class Meteo:
    path : Path
    archive : Rclone
    tres : Timedelta
    prefix : str = 'EA'
    task_id : int = None
    logfile : io.FileIO = sys.stdout

    def __post_init__(self):
        self.path = Path(self.path)

    def __setattr__(self, key, value):
        if key in ['tres', 'path']:
            try :
                value = self.__annotations__[key](value)
            except (TypeError, ValueError) as e:
                logger.critical(f"Can't convert value {key} (value {value}) to {type} ")
                raise e
        super().__setattr__(key, value)

    def check_unmigrate(self, start: Timestamp, end: Timestamp) -> bool:

        # Generate the list of files
        files = self.gen_filelist(start, end)

        # Attempt to clone files from archive:
        info = None if self.task_id is None else f'task {self.task_id}'
        self.archive.logfile = self.logfile
        success = self.archive.get(files, self.path, info=info)

        # touch all the files so that they don't get removed:
        _ = [Path(f).touch() for f in str(self.path) + '/' + files.file if Path(f).exists()]

        return success

    def gen_filelist(self, start: Timestamp, end: Timestamp) -> DataFrame:
        """
        Generate a list of meteo files that FLEXPART will need.
        """
        times = date_range(start - self.tres, end + self.tres, freq=self.tres)
        return DataFrame.from_dict({'time': times, 'file': [f'{self.prefix}{tt:%y%m%d%H}' for tt in times]})

    def write_AVAILABLE(self, filepath: str) -> None:
        fmt = f'{self.prefix}????????'
        flist = glob.glob(os.path.join(self.path, fmt))
        times = [datetime.strptime(os.path.basename(f), f'{self.prefix}%y%m%d%H') for f in flist]
        with open(filepath, 'w') as fid :
            fid.writelines(['\n']*3)
            for tt in sorted(times) :
                fid.write(tt.strftime(f'%Y%m%d %H%M%S      {self.prefix}%y%m%d%H         ON DISC\n'))

    def cleanup(self, threshold: Timedelta = Timedelta(0), nfilesmin : int = None):
        """
        Remove old meteo files. The one with the oldest last access time will be removed in priority
        :param threshold: Age threshold below which the files won't be removed
        :param nfilesmin: Minimum number of files to keep.
        """

        # At least one of the two options need to be set
        if threshold.total_seconds() == 0 and nfilesmin is None :
            logger.warning("Meteo cleanup required, but no restraining factor requested. Skipping the cleanup")
            return

        files = array([_ for _ in self.path.glob(f'{self.prefix}????????')])
        atime = array([datetime.fromtimestamp(_.stat().st_atime) for _ in files])
        age = datetime.now() - atime

        # if a min number of files is requested, remove them from the pool of
        # "deletable" files.
        if nfilesmin and nfilesmin > len(files):
            files = files[argsort(age)][nfilesmin:]
            age = age[argsort(age)][nfilesmin:]

        # Remove the remaining files
        _ = [f.unlink() for f in files[age > threshold]]
