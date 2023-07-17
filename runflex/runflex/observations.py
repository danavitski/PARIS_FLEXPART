#!/usr/bin/python
from pandas import DataFrame, read_csv, read_hdf, Timedelta, date_range, concat
import tarfile
from loguru import logger
from typing import List, Protocol, Union, Type
from tqdm import tqdm
from numpy import unique, array, ceil, typing
import os
from runflex.releases import Releases


class FootprintClass(Protocol):
    footprints: List[str]

    def __init__(self, filename: str, mode: str) -> None:
        ...

    def __enter__(self) -> "FootprintClass":
        ...

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        ...


def read_tgz(fname: str) -> DataFrame:
    with tarfile.open(fname, 'r:gz') as tar:
        df = read_csv(tar.extractfile('observations.csv'), infer_datetime_format='%Y%m%d%H%M%S', index_col=0, parse_dates=['time'])
    return df


class Observations(DataFrame):

    # The following is needed to ensure that methods of the parent DataFrame class return an "Observations" object, and not a "DataFrame"
    @property
    def _constructor(self):
        return Observations

    @classmethod
    def from_coordinates(cls, conf: dict) -> "Observations":
        """
        Create a footprint list at regular time intervals, based on a list of coordinates.
        Coordinates are passed as a dictionary, with the following structure:
        :param conf: a dictionary-like object with the following structure:
            coords = {
                'sitecode1':
                    {
                        'start' : %Y-%m-%d,
                        'end' : %Y-%m-%d,
                        'freq' : %s,
                        'lat' : %.2f,
                        'lon' : %.2f,
                        'alt' : %.2f,
                        'height' : %.2f,
                        'code' : %s,
                        'range' : from %H:%M to %H:%M,
                    },
                'sitecode2': {...},
                ...
            }

            The "code" and "range" attributes are optional. If "code" is not provided, the sitekey ("sitecode1",
            "sitecode2", ..., in the example above) is used instead.
            "start" and "end" should be in any format supported by pandas.Timestamp, and "freq" can be in a format
            supported by pandas.tseries.frequencies.to_offset

            The keys 'start', 'end', 'freq' and 'range' can also be set at a global level (as a default):
            coords = {
                start : '%Y-%m-%d,
                end : '%Y-%m-%d,
                freq : %s,
                range : from %H:%m to %H:%M
                site1 : dict(lat= ..., lon = ..., alt = ..., height = ...),
                site2 : dict(lat= ..., lon = ..., alt = ..., height = ..., start = ..., end = ...),
                site3 : dict(lat= ..., lon = ..., alt = ..., height = ..., range = ...)
            }
        """

        obs = []
        default_key = '\*'
        defaults = conf.get(default_key, {})
        for site in [_ for _ in conf.keys() if _ != default_key]:
            df = DataFrame(columns=['time', 'lat', 'lon', 'alt', 'height', 'code'])
            start = conf[site].get('start', defaults.get('start'))
            end = conf[site].get('end', defaults.get('end'))
            freq = conf[site].get('freq', defaults.get('freq'))
            assert start is not None, logger.error(f"No min date (`start`) provided for observations at {site}, and no default value found.")
            assert end is not None, logger.error(f"No max date (`end`) provided for observations at {site}, and no default value found.")
            assert freq is not None, logger.error(f"No sampling frequency (`freq`) key provided for site {site}, and no default value found.")
            df.loc[:, 'time'] = date_range(start, end, freq=freq)
            df.loc[:, 'lat'] = conf[site]['lat']
            df.loc[:, 'lon'] = conf[site]['lon']
            df.loc[:, 'alt'] = conf[site]['alt']
            df.loc[:, 'height'] = conf[site]['height']
            df.loc[:, 'code'] = conf[site].get('code', site)
            interval = conf[site].get('range', defaults.get('range'))
            if interval is not None:
                _, tmin, _, tmax = interval.split()
                df = df.set_index('time').between_time(tmin, tmax).reset_index()
            obs.append(df)
        obs = cls(concat(obs, ignore_index=True))
        obs.loc[:, 'obsid'] = obs.gen_obsid()
        return obs

    @classmethod
    def read(cls, fname: str) -> "Observations":
        """
        Read in the observations from one of the implemented formats:
        - tar.gz (as in LUMIA)
        - csv
        - hdf
        """

        if fname.endswith('tar.gz') or fname.endswith('tgz'):
            df = read_tgz(fname)
        elif fname.endswith('csv'):
            df = read_csv(fname)
        elif fname.endswith('hdf') or fname.endswith('h5'):
            df = read_hdf(fname)
        else:
            logger.error(f"Unrecognized observation format for observation file {fname}")
            raise RuntimeError

        if 'code' not in df:
            df.loc[:, 'code'] = df.loc[:, 'site']

        fields = ['time', 'lat', 'lon', 'alt', 'height', 'code']
        if 'kindz' in df.columns:
            fields.append('kindz')
        if 'obsid' in df.columns:
            fields.append('obsid')

        obs = cls(df.loc[:, fields].drop_duplicates())
        if 'obsid' not in obs.columns:
            obs.loc[:, 'obsid'] = obs.gen_obsid()
        return obs

    def select(self, time_range=('1900', '2100'), lon_range=(-360, 360), lat_range=(-90, 90), include: List[str] = None, exclude: List[str] = None) -> "Observations":
        """
        Filter out data that are outside the requested lat/lon/time intervals. The default values allows any (reasonable) coordinates.
        Arguments:
            time_range: list with start and end time interval. Can be any type recognized as Timestamp by pandas.
            lon_range: min and max longitudes (default -360 to 360)
            lat_range: min and max latitudes (default -90 to 90).
            include: list of sites to include (sites not in the list are excluded)
            exclude: list of sites to exclude (sites not in the list are included)
        All ranges are inclusive.
        Returns:
            a new "Observations" DataFrame (no "inplace" option).
        """
        db = self.loc[
             (self.time >= time_range[0]) &
             (self.time <= time_range[1]) &
             (self.lon >= lon_range[0]) &
             (self.lat >= lat_range[0]) &
             (self.lon <= lon_range[1]) &
             (self.lat <= lat_range[1]), :].copy()

        if include:
            db = db.loc[db.code.isin(include), :]

        if exclude:
            db = db.loc[~db.code.isin(exclude), :]

        return db

    def check_footprints(self, path: str, footprint: Type[FootprintClass]) -> List[bool]:
        """
        Check if footprints are already present in the output directory. Returns a bool array with "True" marking the missing footprints
        """
        filenames = self.filenames.values if 'filenames' in self else self.gen_filenames(path)
        if 'obsid' not in self:
            self.loc[:, 'obsid'] = self.gen_obsid()

        # Check in each file:
        self.loc[:, 'present'] = False
        for filename in tqdm(unique(filenames), desc=f'Checking the presence of footprints in {path}'):
            dfs = self.loc[filenames == filename]
            try:
                with footprint(filename, 'r') as fp:
                    self.loc[filenames == filename, 'present'] = [o in fp.footprints for o in dfs.obsid]
            except FileNotFoundError:
                logger.warning(f"File {filename} not found.")

        missing = (~self.present).tolist()
        self.drop(columns='present')

        # Message summary of footprints presence:
        if self.loc[missing, :].empty:
            logger.info(f"All footprints have already been computed")
        else:
            logger.info(f"{sum(missing)} footprints remain to be computed (out of a total of {len(missing)}")

        return missing

    def gen_filenames(self, path: str = './') -> typing.NDArray:
        filenames = self.code + '.' + self.height.astype(int).astype(str) + 'm.' + self.time.dt.strftime('%Y-%m.hdf')
        filenames = array([os.path.join(path, fn) for fn in filenames])
        return filenames

    def gen_obsid(self) -> typing.NDArray:
        obsid = self.code + '.' + self.height.astype(int).astype(str) + 'm.' + self.time.dt.strftime('%Y%m%d-%H%M%S')
        return obsid.values

    def split(self, nobsmax: int = None, ncpus: int = 1, maxdt: Union[str, Timedelta] = '7D') -> List[Releases]:

        # Sort the observations by time (so that consecutive obs end up in the same tasks).
        self.sort_values('time', inplace=True)

        # Determine the number of tasks:
        nobs = self.shape[0]
        ntasks = ceil(nobs / nobsmax)

        # If there are more CPUs than tasks, then reduce the number of obs/task (making sure that there's at least one obs/task)
        if ntasks < ncpus:
            ntasks = ncpus
            nobsmax = int(ceil(nobs / ntasks))

        logger.debug(f"   Number of CPUs requested : {ncpus:0f}")
        logger.debug(f"     Number of observations : {nobs:.0f}")
        logger.debug(f"     Max number of obs/task : {nobsmax:.0f}")

        releases = []
        i0 = 0
        with tqdm(total=self.shape[0], desc='splitting observation database') as pbar:
            while i0 < self.shape[0]:
                db = self.iloc[i0: i0 + nobsmax]
                db = db.loc[db.time - db.time.min() <= maxdt, :]

                releases.append(Releases(db))

                i0 += db.shape[0]
                pbar.update(db.shape[0])

        logger.info(f"            Number of tasks : {len(releases):.0f}")

        return releases
