#!/usr/bin/env python

from omegaconf import OmegaConf
from runflex import prefix
from runflex.utilities import getfile
from runflex.archive import Rclone
from pandas import Timedelta
import tempfile


class TempDir:
    def __init__(self):
        self.paths = {}

    def get(self, path):
        # Ensures that a new directory is not created each time
        if path not in self.paths :
            self.paths[path] = tempfile.TemporaryDirectory(prefix='runflex', dir=path)
        return self.paths[path].name


tempdir = TempDir()


OmegaConf.register_new_resolver("prefix", lambda x: prefix.joinpath(x))
OmegaConf.register_new_resolver("file", lambda x: getfile(x))
OmegaConf.register_new_resolver("rclone", lambda x: Rclone(x))
OmegaConf.register_new_resolver('dt', lambda x: Timedelta(x))
OmegaConf.register_new_resolver('tmp', lambda x: tempdir.get(x))
# OmegaConf.register_new_resolver('tmp', lambda x: tempfile.TemporaryDirectory(prefix='runflex', dir=x).name)
