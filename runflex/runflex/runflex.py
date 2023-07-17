#!/usr/bin/env python

# General imports
import shutil
from loguru import logger
from argparse import ArgumentParser
from netCDF4 import Dataset
from pathlib import Path

# Pyflex
from runflex.observations import Observations
from runflex.manager import QueueManager
from runflex.compile import Flexpart
from runflex.config import OmegaConf, getfile

# Types
from omegaconf import DictConfig
from typing import List, Union


class LumiaFootprintFile(Dataset):

    @property
    def footprints(self) -> List[str]:
        return list(self.groups.keys())


def read_conf(**kwargs) -> DictConfig:
    """
    Store the configuration of the run as a omegaconf object:
    """
    conf = OmegaConf.load(getfile('defaults.yaml'))

    if kwargs.get('rc', None):
        conf.merge_with(OmegaConf.load(kwargs['rc']))
    else:
        conf.merge_with(OmegaConf.create())

    # keywords can be overwritten using "--setkey key: value" command
    if kwargs.get('setkey', None):
        for kv in kwargs['setkey']:
            k, v = kv.split(':', maxsplit=1)
            for kk in k.split('.')[::-1]:
                v = {kk.lower(): v}
            conf.merge_with(v)

    # Most used rc-keys have shortcut arguments:
    # First, make sure no section is missing:
    for sect in ['observations', 'paths', 'run']:
        if sect not in conf:
            conf[sect] = {}

    # Mapping:
    kwargs = {k: v for (k, v) in kwargs.items() if v is not None}

    conf_override = dict()
    conf_override['observations'] = {k: kwargs[k] for k in ['obs', 'start', 'end', 'sites', 'nobs'] if k in kwargs}
    conf_override['paths'] = {k: kwargs[k] for k in ['build', 'makefile', 'extras', 'src'] if k in kwargs}
    conf_override['run'] = {k: kwargs[k] for k in ['serial', 'ncpus', 'cleanup', 'recompute'] if k in kwargs}
    conf.merge_with(conf_override)

    return conf


def compile(conf: DictConfig) -> Flexpart:
    """
    Compile flexpart.
    """
    flexpart = Flexpart(
        build=conf.paths.build,
        src=conf.paths.src,
        makefile=conf.paths.get('makefile', None),
        extras=conf.paths.get('extras', None)
    )
    flexpart.compile()
    return flexpart


def load_obs(conf: DictConfig) -> Observations:
    if 'file' in conf.observations:
        obs = Observations.read(conf.observations.file)
    elif 'coordinates' in conf.observations:
        obs = Observations.from_coordinates(conf.observations.coordinates)

    obs = obs.select(time_range=(conf.observations.get('start', '1900'), conf.observations.get('end', '2100')),
                     lat_range=conf.outgrid.y[:2],
                     lon_range=conf.outgrid.x[:2],
                     include=conf.observations.get('include', None),
                     exclude=conf.observations.get('exclude', None))

    # Select only the first n observations (for debug ...)
    if conf.observations.get('nobs', None):
        obs = obs.iloc[:conf.observations.nobs]

    # Setup kindz:
    if 'kindz' not in obs:
        kindz = conf.observations.release.kindz
        if isinstance(kindz, Union[int, float]):
            obs.loc[:, 'kindz'] = kindz
        elif isinstance(kindz, DictConfig):
            if 'threshold' in kindz:
                obs.loc[:, 'kindz'] = 1
                obs.loc[obs.alt >= kindz.threshold, 'kindz'] = 2
            elif '1' in kindz:
                obs.loc[:, 'kindz'] = 2
                obs.loc[obs.code.isin(kindz[1]), 'kindz'] = 1
            elif '2' in kindz:
                obs.loc[:, 'kindz'] = 1
                obs.loc[obs.code.isin(kindz[2]), 'kindz'] = 2

    # Setup release height:
    if 'release_heigh' not in obs:
        obs.loc[obs.kindz == 1, 'release_height'] = obs.height.loc[obs.kindz == 1]
        alt_corr = conf.observations.get('altitude_correction', 1)
        obs.loc[obs.kindz == 2, 'release_height'] = (obs.height + alt_corr * (obs.alt - obs.height)).loc[obs.kindz == 2]

    return obs


def handle_missing(obs, path: Path, display: bool = False) -> List[bool]:
    missing = obs.check_footprints(path, LumiaFootprintFile)
    if any(missing):
        if display:
            print(obs.loc[missing].to_string())
    else:
        logger.info("All footprints have been computed")
    return missing


def calc_footprints(conf: DictConfig) -> Union[Observations, QueueManager]:
    # Load the observations:
    obs = load_obs(conf)
    outpth = conf.paths.output

    # Cleanup can remove anything that is in paths.run, so disabled by default
    if conf.run.cleanup:
        shutil.rmtree(conf.paths.run, ignore_errors=True)

    # If it's a continuation (default True), check which footprints already exist:
    if conf.run.recompute:
        missing = handle_missing(obs, outpth)
        obs = obs.loc[missing]
        if not any(missing):
            return obs

    # Compute the footprints :
    queue = QueueManager(conf, obs, serial=conf.run.get('serial', False))
    queue.dispatch()

    if conf.postprocess.get('lumia', False):
        handle_missing(obs, outpth)

    return queue


###########################################################
# Define parser:
parser = ArgumentParser()
p_compile = parser.add_argument_group('Compile')
p_footprints = parser.add_argument_group('Compute footprints')

# Global arguments :
# Rc-file and rc-file overloads:
parser.add_argument('--rc', help='Main configuration file (yaml format)', type=Path)
parser.add_argument('--setkey', action='append', help="use to override some rc-keys")
parser.add_argument('--verbosity', '-v', default='INFO')

# FLEXPART compilation :
p_compile.add_argument('--compile', action='store_true')
p_compile.add_argument('--src', help='Main source path')
p_compile.add_argument('--build', help='Build directory (where the code should be compiled, and the executable stored', type=Path)
p_compile.add_argument('--makefile', help='Path to the makefile', type=Path)
p_compile.add_argument('--extras', help='extra source code path (files in it overwrite the ones in the path given by "--src" (or by path.src in the rc-file)', type=Path)

# FLEXPART run options:
# Obs selection:
p_footprints.add_argument('--footprints', action='store_true')
p_footprints.add_argument('--obs', help="Observation file (csv or tar.gz format)", type=Path)
p_footprints.add_argument('--start', help="Set a minimum date for the footprints to be computed", type=str)
p_footprints.add_argument('--end', help="Set a maximum date for the footprints to be computed", type=str)
p_footprints.add_argument('--only', action='append', help="run only this site (add several times the argument for several sites)")
p_footprints.add_argument('--nobs', default=None, help="Use this to limit the number of observations (i.e. for test purposes)", type=int)

# FLEXPART run footprints options
p_footprints.add_argument('--serial', '-i', action='store_true', default=False)
p_footprints.add_argument('--ncpus', '-n', help='Number of parallell processes', default=None, type=int)
p_footprints.add_argument('--cleanup', action='store_true', help="Ensure that the rundir is clear from previous runs (set to False by default as this will erase anything in the scratch dir, even if it doesn't belong to runflex!)")
p_footprints.add_argument('--recompute', action='store_false', help='Use --recompute to force runflex to recompute any already existing footprints')
