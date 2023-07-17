#!/usr/bin/env python
import os
import shutil
from loguru import logger
from transport.core import Model
from transport.core.model import FootprintFile
from transport.emis import Emissions
import h5py
from typing import List, Type
from types import SimpleNamespace
from pandas import Timedelta, Timestamp, DataFrame, read_hdf, isnull
from gridtools import Grid
from numpy import array, nan, inf
from dataclasses import asdict
from tqdm import tqdm


def check_migrate(source, dest):
    if os.path.exists(dest):
        return True
    elif os.path.exists(source):
        shutil.copy(source, dest)
        return True
    return False


class LumiaFootprintFile(h5py.File):
    maxlength : Timedelta = inf
    __slots__ = ['shift_t', 'origin', 'timestep', 'grid']

    def __init__(self, *args, maxlength:Timedelta=inf, **kwargs):
        super().__init__(*args, mode='r', **kwargs)
        self.shift_t = 0

        try :
            self.origin = Timestamp(self.attrs['origin'])
            self.timestep = Timedelta(seconds=abs(self.attrs['run_loutstep']))
            #self.timestep = Timedelta(seconds=abs(self.attrs['loutstep']))
            if self.maxlength != inf :
                self.maxlength /= self.timestep
            assert self['latitudes'].dtype in ['f4', 'f8']
            self.grid = Grid(latc=self['latitudes'][:], lonc=self['longitudes'][:])

        except AssertionError :
            self.grid = Grid(
                #lon0=self.attrs['outlon0'], dlon=self.attrs['dxout'], nlon=len(self['longitudes'][:]),
                #lat0=self.attrs['outlat0'], dlat=self.attrs['dyout'], nlat=len(self['latitudes'][:])
                lon0=self.attrs['run_outlon0'], dlon=self.attrs['run_dxout'], nlon=len(self['longitudes'][:]),
                lat0=self.attrs['run_outlat0'], dlat=self.attrs['run_dyout'], nlat=len(self['latitudes'][:])
            )

        except KeyError:
            logger.warning(f"Coordinate variables (latitudes and longitudes) not found in file {self.filename}. Is the file empty?")

    @property
    def footprints(self) -> List[str]:
        return [k for k in self.keys() if isinstance(self[k], h5py.Group)]

    def align(self, grid: Grid, timestep: Timedelta, origin: Timestamp):
        assert Grid(latc=grid.latc, lonc=grid.lonc) == self.grid, f"Can't align the footprint file grid ({self.grid}) to the requested grid ({Grid(**asdict(grid))})"
        assert timestep == self.timestep, "Temporal grid mismatch"
        shift_t = (self.origin - origin)/timestep
        assert int(shift_t) - shift_t == 0
        self.shift_t = int(shift_t)

    def get(self, obsid) -> SimpleNamespace :
        itims = self[obsid]['itims'][:] 
        ilons = self[obsid]['ilons'][:]
        ilats = self[obsid]['ilats'][:]
        sensi = self[obsid]['sensi'][:]

        if Timestamp(self[obsid]['sensi'].attrs.get('runflex_version', '2000.1.1')) > Timestamp(2022, 9, 1):
            sensi *= 0.0002897

        # If the footprint is empty, return here:
        if len(itims) == 0:
            return SimpleNamespace(shift_t=0, itims=itims, ilats=ilats, ilons=ilons, sensi=sensi)

        # sometimes, the footprint will have non-zero sentivity for the time-step directly after the observation time. This is because FLEXPART calculates the concentration after releasing the particles, and before going to the next step. In this case, re-attribute the sensitivity to the previous time step.

        # Check if the time of the last time step is same as release time (it should be lower by 1 timestep normally)
        # if it's the case, decrement that time index by 1
        if self.origin + itims[-1] * self.timestep == Timestamp(self[obsid].attrs['release_end']):
            itims[-1] -= 1

        # Trim the footprint if needed
        sel = itims.max() - itims <= self.maxlength

        # Apply the time shift
        itims += self.shift_t

        # Exclude negative time steps
        if itims.min() < 0 :
            sel *= False

        return SimpleNamespace(
            name=obsid,
            shift_t=self.shift_t,
            itims=itims[sel], 
            ilons=ilons[sel], 
            ilats=ilats[sel], 
            sensi=sensi[sel])


class Observations(DataFrame):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    @classmethod
    def read(cls, filename: str) -> "Observations":
        return cls(read_hdf(filename))

    @property
    def _constructor(self):
        """
        Ensures that the parent's (DataFrame) methods return an instance of Observations and not DataFrame
        """
        return Observations
    
    def write(self, filename: str) -> None:
        self.to_hdf(filename, key='observations')

    def gen_filenames(self) -> None:
        fnames = self.code.str.lower() + self.height.map('.{:.0f}m.'.format) + self.time.dt.strftime('%Y-%m.hdf')
        self.loc[:, 'footprint'] = fnames

    def find_footprint_files(self, archive: str, local: str=None) -> None:
        # 2) Append file names, both for local and archive
        if local is None:
            local = archive
        fnames_archive = archive + '/' + self.footprint
        fnames_local = local + '/' + self.footprint

        # 3) retrieve the files from archive if needed:
        exists = array([check_migrate(arc, loc) for (arc, loc) in tqdm(zip(fnames_archive, fnames_local), desc='Migrate footprint files', total=len(fnames_local), leave=False)])
        self.loc[:, 'footprint'] = fnames_local

        if not exists.any():
            logger.error("No valid footprints found. Exiting ...")
            raise RuntimeError("No valid footprints found")

        # Create the file names:
        #fnames = path + '/' + self.code.str.lower() + self.height.map('.{:.0f}m.'.format) + self.time.dt.strftime('%Y-%m.hdf')
        #self.loc[:, 'footprint'] = fnames
        #exists = array([os.path.exists(f) for f in fnames])
        self.loc[~exists, 'footprint'] = nan

    def gen_obsid(self) -> None:
        # Construct the obs ids:
        obsids = self.code + self.height.map('.{:.0f}.'.format) + self.time.dt.strftime('%Y%m%d-%H%M%S')
        self.loc[~isnull(self.footprint), 'obsid'] = obsids

    def check_footprint_files(self, cls: Type[FootprintFile]) -> None:
        # Check in the files which footprints are actually present:
        fnames = self.footprint.drop_duplicates().dropna()
        footprints = []
        for fname in fnames:
            with cls(fname) as fpf:
                footprints.extend(fpf.footprints)
        self.loc[~self.obsid.isin(footprints), 'footprint'] = nan


    def check_footprints(self, archive: str, cls: Type[FootprintFile], local: str=None) -> None:
        """
        Search for/lumia/transport/multitracer.py the footprint corresponding to the observations
        """
        # 1) Create the footprint file names
        self.gen_filenames()
        self.find_footprint_files(archive, local)
        if 'obsid' not in self:
            self.gen_obsid()
        self.check_footprint_files(cls)


class MultiTracer(Model):
    _footprint_class = LumiaFootprintFile

    @property
    def footprint_class(self):
        return self._footprint_class


if __name__ == '__main__':
    import sys
    from argparse import ArgumentParser, REMAINDER

    p = ArgumentParser()
    p.add_argument('--setup', action='store_true', default=False, help="Setup the transport model (copy footprints to local directory, check the footprint files, ...)")
    p.add_argument('--forward', '-f', action='store_true', default=False, help="Do a forward run")
    p.add_argument('--adjoint', '-a', action='store_true', default=False, help="Do an adjoint run")
    p.add_argument('--footprints', '-p', help="Path where the footprints are stored")
    p.add_argument('--check-footprints', action='store_true', help='Determine which footprint file correspond to each observation')
    p.add_argument('--copy-footprints', default=None, help="Path where the footprints should be copied during the run (default is to read them directly from the path given by the '--footprints' argument")
    p.add_argument('--adjtest', '-t', action='store_true', default=False, help="Perform and adjoint test")
    p.add_argument('--serial', '-s', action='store_true', default=False, help="Run on a single CPU")
    p.add_argument('--tmp', default='/tmp', help='Path to a temporary directory where (big) files can be written')
    p.add_argument('--ncpus', '-n', default=os.cpu_count())
    p.add_argument('--max-footprint-length', type=Timedelta, default='14D')
    p.add_argument('--verbosity', '-v', default='INFO')
    p.add_argument('--obs', required=True)
    p.add_argument('--emis')#, required=True)
    p.add_argument('args', nargs=REMAINDER)
    args = p.parse_args(sys.argv[1:])

    # Set the verbosity in the logger (loguru quirks ...)
    logger.remove()
    logger.add(sys.stderr, level=args.verbosity)

    obs = Observations.read(args.obs)

    # Set the max time limit for footprints:
    LumiaFootprintFile.maxlength = args.max_footprint_length

    if args.check_footprints or 'footprint' not in obs.columns:
        obs.check_footprints(args.footprints, LumiaFootprintFile, local=args.copy_footprints)

    model = MultiTracer(parallel=not args.serial, ncpus=args.ncpus, tempdir=args.tmp)
    emis = Emissions.read(args.emis)
    if args.forward:
        obs = model.run_forward(obs, emis)
        obs.write(args.obs)

    elif args.adjoint :
        adj = model.run_adjoint(obs, emis)
        adj.write(args.emis)

    elif args.adjtest :
        model.adjoint_test(obs, emis)
