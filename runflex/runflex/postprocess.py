#!/usr/bin/env python
from netCDF4 import Dataset, chartostring, Group
from h5py import File
from pandas import DataFrame, Timestamp, Timedelta, TimedeltaIndex
import time
import os
from loguru import logger
from dataclasses import dataclass, field
from numpy.typing import NDArray
from typing import Union
from types import SimpleNamespace
from numpy import nonzero, meshgrid, array, int16, array_equal
import runflex
from runflex.utilities import checkpath
from git import Repo


@dataclass
class Release:
    data: NDArray
    origin: Timestamp
    dt: Timedelta
    release_attributes: dict = field(default_factory=dict)
    run_attributes: dict = field(default_factory=dict)
    coordinates: SimpleNamespace = SimpleNamespace(lon=None, lat=None, time=None)
    grid: SimpleNamespace = SimpleNamespace(lon=None, lat=None, time=None)
    specie: dict = field(default_factory=dict)
    nshift: int = 0

    @property
    def footprint(self) -> SimpleNamespace:
        data = self.data.reshape(-1)
        sel = nonzero(data)
        return SimpleNamespace(
            sensi=data[sel],
            ilat=self.grid.lat[sel],
            ilon=self.grid.lon[sel],
            itime=self.grid.time[sel] + self.nshift
        )

    def __post_init__(self):
        # Convert self.data in m2.s/mol:
        if self.specie['units'] == 's.m3/kg':
            self.data /= self.grid.height
            self.data *= 1000 * self.specie['weightmolar']
            self.specie['units'] = 's.m2/mol'

    def shift_origin(self, new_origin: Timestamp):
        """
        Use the beginning of the month as convention for the origin, by default (even if that leads to negative indices)
        """
        # Determine the number of time intervals there is between the two origins
        nshift = (self.origin - new_origin) / abs(self.dt)
        assert nshift - int(nshift) == 0
        self.nshift = int(nshift)
        self.coordinates.time += new_origin - self.origin
        self.origin = new_origin


class LumiaFile(File):
    def __init__(self, *args, origin: Timestamp, count: int = 0, wait: int = 1, **kwargs):
        # Open the file, but wait for it to be free if it's busy
        maxcount = 20
        try:
            super().__init__(*args, **kwargs)
        except (OSError, BlockingIOError) as e:
            if count < maxcount:
                logger.info(f"Waiting {wait} sec for the access to file {args[0]}")
                time.sleep(wait)
                count += 1
                wait += count
                self.__init__(*args, origin=origin, count=count, wait=wait, **kwargs)
            else:
                logger.error(f"Couldn't open file {args[0]} (File busy?)")
                raise e

        # Application attributes
        self.origin = origin
        self.attrs['origin'] = str(self.origin)

    def add(self, release: Release, background: Union[None, Group]) -> None:
        # Make sure that all data is on the same time coordinates
        # (only for non empty footprints)
        release.shift_origin(self.origin)

        # Store/check lat and lon:
        if 'latitudes' in self:
            assert array_equal(self['latitudes'][:], release.coordinates.lat)
            assert array_equal(self['longitudes'][:], release.coordinates.lon)
        else:
            self['latitudes'] = release.coordinates.lat
            self['latitudes'].attrs['units'] = 'degrees North'
            self['latitudes'].attrs['info'] = 'center of the grid cells'
            self['longitudes'] = release.coordinates.lon
            self['longitudes'].attrs['units'] = 'degrees East'
            self['longitudes'].attrs['info'] = 'center of the grid cells'

        # Store attributes:
        for k, v in release.run_attributes.items():
            k = f'run_{k}'
            if k not in self.attrs:
                self.attrs[k] = v
            elif v != self.attrs[k]:
                release.release_attributes[k] = v

        # FLEXPART "species"
        for k, v in release.specie.items():
            self.attrs[f'species_{k}'] = v

        # Write the release:
        # If a release with the same name is present, delete it
        obsid = release.release_attributes['name']
        if obsid in self:
            del self[obsid]

        # Store the release:
        gr = self.create_group(obsid)
        gr['ilons'] = release.footprint.ilon.astype(int16)
        gr['ilats'] = release.footprint.ilat.astype(int16)
        gr['itims'] = release.footprint.itime.astype(int16)
        gr['sensi'] = release.footprint.sensi
        gr['sensi'].attrs['units'] = release.specie['units']
        commit = Repo(runflex.prefix).head.object
        gr['sensi'].attrs['runflex_version'] = commit.committed_datetime.strftime('%Y.%-m.%-d')
        gr['sensi'].attrs['runflex_commit'] = f'{commit.hexsha} ({commit.committed_datetime})'
        for k, v in release.release_attributes.items():
            if isinstance(v, Timestamp):
                v = str(v)
            gr.attrs[f'release_{k}'] = v

        logger.info(f"Added release {obsid} to file {self.filename}")

        # Add background, if needed
        if background is not None :
            gr.create_group('background')
            for k, v in background.variables.items():
                gr['background'][k] = v[:]
                # Copy netcdf attributes:
                for attr in background[k].ncattrs():
                    gr['background'][k].attrs[attr] = getattr(background[k], attr)

            # Correct time origin: currently it refers to the *end* (most recent date) of the simulation,
            # as opposed to what happened with the footprint:
            gr['background']['time'][:] = gr['background']['time'][:] + (Timestamp(release.run_attributes['iedate'] + release.run_attributes['ietime']) - self.origin).total_seconds()
            gr['background']['time'].attrs['units'] = f'seconds since {self.origin}'
            gr['background']['time'].attrs['calendar'] = 'proleptic_gregorian'

class GridTimeFile:
    def __init__(self, *args, **kwargs):
        self.ds = Dataset(*args, **kwargs)
        self.dt = Timedelta(seconds=self.ds.loutstep)
        self.start = Timestamp(self.ds.ibdate + self.ds.ibtime)
        self.end = Timestamp(self.ds.iedate + self.ds.ietime)
        self.coordinates = SimpleNamespace(
            lon=self['longitude'][:].data,
            lat=self['latitude'][:].data,
            time=array([self.end + Timedelta(seconds=_) - self.dt / 2 for _ in self['time'][:].data])
        )
        self.species = vars(self['spec001_mr'])
        self.params = vars(self.ds)
        self.releases = DataFrame.from_dict(dict(
            name=[t.strip() for t in chartostring(self['RELCOM'][:])],
            lat1=self['RELLAT1'][:].data,
            lat2=self['RELLAT2'][:].data,
            lon1=self['RELLNG1'][:].data,
            lon2=self['RELLNG2'][:].data,
            z1=self['RELZZ1'][:].data,
            z2=self['RELZZ2'][:].data,
            kindz=self['RELKINDZ'][:].data,
            start=[self.end + Timedelta(seconds=_) for _ in self['RELSTART'][:]],
            end=[self.end + Timedelta(seconds=_) for _ in self['RELEND'][:]],
            npart=self['RELPART'][:],
            mass=self['RELXMASS'][0, :],

        ))

        nt = len(self.coordinates.time)
        nlat = len(self.coordinates.lat)
        nlon = len(self.coordinates.lon)
        grid = meshgrid(range(nt), range(nlat), range(nlon), indexing='ij')
        height = self['height'][:].data
        assert len(height == 1), logger.critical("This script is only adapted for single-layer footprints")
        self.grid = SimpleNamespace(
            time=grid[0].reshape(-1),
            lat=grid[1].reshape(-1),
            lon=grid[2].reshape(-1),
            height=height
        )

    def __enter__(self):
        self.ds.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.ds.__exit__(exc_type, exc_val, exc_tb)

    def get(self, release_name: str) -> Release:
        irl = list(self.releases.name).index(release_name)
        return Release(
            data=self['spec001_mr'][0, irl, :, 0, :, :][::-1, :, :].data,
            origin=self.start,
            dt=self.dt,
            grid=self.grid,
            release_attributes=self.releases.iloc[irl].to_dict(),
            run_attributes=self.params,
            coordinates=self.coordinates,
            specie=self.species,
        )

    def __getitem__(self, item):
        return self.ds.__getitem__(item)


def postprocess_task(task) -> None:
    releases = task.releases

    if task.status in ['success', 'skipped']:

        releases.loc[:, 'filename'] = releases.code + releases.height.map('.{:.0f}m.'.format) + releases.time.dt.strftime('%Y-%m.hdf')

        # Open the FLEXPART grid_time file:
        with GridTimeFile(task.end.strftime(os.path.join(task.rundir, 'grid_time_%Y%m%d%H%M%S.nc')), 'r') as gridfile:

            # Open also the background file, if it exists:
            bgfile = task.rundir / 'particles_final.nc'
            if bgfile.exists():
                bg = Dataset(bgfile)
            else :
                bg = SimpleNamespace(groups={})

            # Iterate over the lumia footprint files (i.e. destination)
            for file in releases.drop_duplicates(subset=['filename']).loc[:, ['filename', 'time']].itertuples():
                origin = Timestamp(file.time.strftime('%Y-%m'))
                with LumiaFile(os.path.join(checkpath(task.rcf.paths.output), file.filename), origin=origin, mode='a') as lum:
                    for release in releases.loc[releases.filename == file.filename].obsid:
                        lum.add(gridfile.get(release), bg.groups.get(release, None))

            if bgfile.exists():
                bg.close()


if __name__ == '__main__':
    pass
