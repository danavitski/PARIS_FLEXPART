#!/usr/bin/env python

from dataclasses import dataclass, field
from numpy import meshgrid, ndarray, linspace, pi, zeros, float64, sin, diff, searchsorted, array, pad, moveaxis, arange, typing
from types import SimpleNamespace
from loguru import logger
from tqdm import tqdm
from h5py import File
import xarray as xr
from cartopy.io import shapereader
from shapely.geometry import Point
from shapely.ops import unary_union
from typing import List, Union
from shapely.prepared import prep


class LandMask:
    def __init__(self) -> None:
        self.initialized = False

    def init(self):
        land_shp_fname = shapereader.natural_earth(resolution='50m', category='physical', name='land')
        land_geom = unary_union(list(shapereader.Reader(land_shp_fname).geometries()))
        self.land = prep(land_geom)
        self.initialized = True
    
    def is_land(self, lat: float, lon: float) -> bool :
        if not self.initialized :
            self.init()
        return self.land.contains(Point(lat, lon))

    def get_mask(self, grid):
        lsm = zeros((grid.nlat, grid.nlon))
        for ilat, lat in enumerate(grid.latc):
            for ilon, lon in enumerate(grid.lonc):
                lsm[ilat, ilon] = self.is_land(lon, lat)
        return GriddedData(lsm.astype(float), grid, density=True)


land_mask = LandMask()


@dataclass
class Grid:
    lon0 : float = None
    lon1 : float = None
    lat0 : float = None
    lat1 : float = None
    dlon : float = None
    dlat : float = None
    nlon : int = None
    nlat : int = None
    latb : ndarray = field(default=None, repr=False, compare=False)
    latc : ndarray = field(default=None, repr=False, compare=False)
    lonb : ndarray = field(default=None, repr=False, compare=False)
    lonc : ndarray = field(default=None, repr=False, compare=False)
    radius_earth : float = field(default=6_378_100.0, repr=False)

    def __post_init__(self):
        """
        Ensure that all variables are set. The region can be initialized:
        - by specifying directly lat/lon coordinates (set type to b if these are boundaries)
        - by specifying lonmin, lonmax and dlon (and same in latitude)
        - by specifying lonmin, dlon and nlon (and sams in latitude)
        """

        # Set the longitudes first
        if self.dlon is None :
            if self.lonc is not None :
                self.dlon = self.lonc[1] - self.lonc[0]
            elif self.lonb is not None :
                self.dlon = self.lonb[1] - self.lonb[0]
            elif self.lon0 is not None and self.lon1 is not None and self.nlon is not None :
                self.dlon = (self.lon1 - self.lon0)/self.nlon
            logger.debug(f"Set {self.dlon = }")

        if self.lon0 is None:
            if self.lonb is not None :
                self.lon0 = self.lonb.min()
            elif self.lonc is not None :
                self.lon0 = self.lonc.min() - self.dlon / 2
            logger.debug(f"Set {self.lon0 = }")

        if self.nlon is None :
            if self.lonc is not None :
                self.nlon = len(self.lonc)
            elif self.lonb is not None :
                self.nlon = len(self.lonb) - 1
            elif self.lon0 is not None and self.lon1 is not None and self.dlon is not None :
                nlon = (self.lon1 - self.lon0) / self.dlon
                assert abs(nlon - round(nlon)) < 1.e-7, f'{nlon}, {self.lon1=}, {self.lon0=}, {self.dlon=}'
                self.nlon = round(nlon)

        # At this stage, we are sure to have at least dlon, lonmin and nlon, so use them only:`
        if self.lon1 is None :
            self.lon1 = self.lon0 + self.nlon * self.dlon

        if self.lonb is None :
            self.lonb = linspace(self.lon0, self.lon1, self.nlon + 1)

        if self.lonc is None :
            self.lonc = linspace(self.lon0 + self.dlon/2., self.lon1 - self.dlon/2., self.nlon)

        # Repeat the same thing for the latitudes:
        if self.dlat is None :
            if self.latc is not None :
                self.dlat = self.latc[1] - self.latc[0]
            elif self.lonb is not None :
                self.dlat = self.latb[1] - self.latb[0]
            elif self.lat0 is not None and self.lat1 is not None and self.nlat is not None :
                self.dlat = (self.lat1 - self.lat0)/self.nlat

        if self.lat0 is None:
            if self.latb is not None :
                self.lat0 = self.latb.min()
            elif self.latc is not None :
                self.lat0 = self.latc.min() - self.dlat / 2

        if self.nlat is None :
            if self.latc is not None :
                self.nlat = len(self.latc)
            elif self.latb is not None :
                self.nlat = len(self.latb) - 1
            elif self.lat0 is not None and self.lat1 is not None and self.dlat is not None :
                nlat = (self.lat1 - self.lat0) / self.dlat
                assert abs(nlat - round(nlat)) < 1.e-7
                self.nlat = round(nlat)

        # At this stage, we are sure to have at least dlon, lonmin and nlon, so use them only:
        if self.lat1 is None :
            self.lat1 = self.lat0 + self.nlat * self.dlat

        if self.latb is None :
            self.latb = linspace(self.lat0, self.lat1, self.nlat + 1)

        if self.latc is None :
            self.latc = linspace(self.lat0 + self.dlat/2., self.lat1 - self.dlat/2., self.nlat)

#        self.area = self.calc_area()

        self.round()

    def round(self, decimals=5):
        """
        Round the coordinates
        """
        self.latc = self.latc.round(decimals)
        self.latb = self.latb.round(decimals)
        self.lonc = self.lonc.round(decimals)
        self.lonb = self.lonb.round(decimals)
        self.lon0 = round(self.lon0, decimals)
        self.lat0 = round(self.lat0, decimals)
        self.lon1 = round(self.lon1, decimals)
        self.lat1 = round(self.lat1, decimals)

    @property
    def area(self) -> ndarray :
        return self.calc_area()

    @property
    def extent(self) -> List[float]:
        return [self.lon0, self.lon1, self.lat0, self.lat1]

    def calc_area(self):
        dlon_rad = self.dlon * pi / 180.
        area = zeros((self.nlat+1, self.nlon), float64)
        lats = ( pi / 180. ) * self.latb
        for ilat, lat in enumerate(lats):
            area[ilat, :] = self.radius_earth**2 * dlon_rad * sin(lat)
        return diff(area, axis=0)

    def get_land_mask(self, refine_factor=1, from_file=False):
        """ Returns the proportion (from 0 to 1) of land in each pixel
        By default, if the type (land or ocean) of the center of the pixel determines the land/ocean type of the whole pixel.
        If the optional argument "refine_factor" is > 1, the land/ocean mask is first computed on the refined grid, and then averaged on the region grid (accounting for grid box area differences)"""
        if from_file :
            with File(from_file, 'r') as df :
                return df['lsm'][:]
        assert isinstance(refine_factor, int), f"refine factor must be an integer ({refine_factor=})"

        # 1. Create a finer resolution grid
        r2 = Grid(lon0=self.lon0, lat0=self.lat0, lon1=self.lon1, lat1=self.lat1, dlon=self.dlon/refine_factor, dlat=self.dlat/refine_factor)
        return land_mask.get_mask(r2).transform(self).data

    def mesh(self, reshape=None):
        lons, lats = meshgrid(self.lonc, self.latc)
        lons = lons.reshape(reshape)
        lats = lats.reshape(reshape)
        return lons, lats

    @property
    def indices(self):
        return arange(self.area.size)

    @property
    def shape(self):
        return (self.nlat, self.nlon)

    def __getitem__(self, item):
        """
        Enables reading the attributes as dictionary items.
        This enables constructing methods that can take indifferently a Grid or dict object.
        """
        return getattr(self, item)

    def __le__(self, other):
        return (self.lon0 >= other.lon0) & (self.lon1 <= other.lon1) & (self.lat0 >= other.lat0) & (self.lat1 <= other.lat1)

    def __lt__(self, other):
        return (self.lon0 > other.lon0) & (self.lon1 < other.lon1) & (self.lat0 > other.lat0) & (self.lat1 < other.lat1)


def calc_overlap_lons(sgrid, dgrid):
    """
    :param sgrid: grid specification for the source region. Can also be provided as a dictionary
    :param dgrid: grid specification for the dest region
    :return: O(s, d) matrix, where O[s, d] is the fraction (from 0 to 1) of the lon interval s in the source grid that is within the interval d in the destination grid
    """
    assert dgrid <= sgrid

    overlap = zeros((sgrid.nlon, dgrid.nlon))

    for ilon_s in range(sgrid.nlon):
        lon0, lon1 = sgrid.lonb[ilon_s], sgrid.lonb[ilon_s+1]
        ilon_d_min = max(0, searchsorted(dgrid.lonb, lon0) - 1)
        ilon_d_max = min(dgrid.nlon, searchsorted(dgrid.lonb, lon1))
        for ilon_d in range(ilon_d_min, ilon_d_max) :
            # get the partial lat-lon interval of the source grid that is in the current destination interval:
            lon_max = min(lon1, dgrid.lonb[ilon_d + 1])
            lon_min = max(lon0, dgrid.lonb[ilon_d])
            overlap[ilon_s, ilon_d] = (lon_max - lon_min) / (lon1 - lon0)
    return overlap


def calc_overlap_lats(sgrid, dgrid):
    """
    :param sgrid: grid specification for the source region. Can also be provided as a dictionary
    :param dgrid: grid specification for the dest region
    :return: O(s, d) matrix, where O[s, d] is the fraction (from 0 to 1) of the lat interval s in the source grid that is within the interval d in the destination grid
    """
    assert dgrid <= sgrid

    overlap = zeros((sgrid.nlat, dgrid.nlat))

    slatb = sgrid.latb * pi/360
    dlatb = dgrid.latb * pi/360

    for ilat_s in range(sgrid.nlat):
        lat0, lat1 = slatb[ilat_s], slatb[ilat_s+1]
        ilat_d_min = max(0, searchsorted(dlatb, lat0) - 1)
        ilat_d_max = min(dgrid.nlat, searchsorted(dlatb, lat1))
        for ilat_d in range(ilat_d_min, ilat_d_max) :
            # get the partial lat-lon interval of the source grid that is in the current destination interval:
            lat_max = min(lat1, dlatb[ilat_d + 1])
            lat_min = max(lat0, dlatb[ilat_d])
            overlap[ilat_s, ilat_d] = (lat_max - lat_min) / (lat1 - lat0)
            if overlap[ilat_s, ilat_d] < 0 : print(lat_min, lat_max, lat0, lat1, ilat_s, ilat_d)
    return overlap


def calc_overlap_matrices(reg1, reg2):
    overlap_lat = calc_overlap_lats(reg1, reg2)
    overlap_lon = calc_overlap_lons(reg1, reg2)
    return SimpleNamespace(lat=overlap_lat, lon=overlap_lon)


@dataclass
class GriddedData:
    """
    The GriddedData class can be used to regrid data spatially.
    Arguments:
        :param data: array to regrid
        :param grid: spatial grid of the data
        :param axis: indices of the dimensions corresponding to the latitude and longitude. For instance, if data is a 3D array, with dimensions (time, lat, lon), then axis should be (1, 2). In practice, use the "dims" parameter instead.
        :param density: whether the data are density (i.e. units/m2) or quantity (i.e. unit/gridbox).
        :param dims: list of dimension names. Should contain "lat" and "lon".
    """
    data    : typing.NDArray
    grid    : Grid
    axis    : list = None
    density : bool = False
    dims    : list = None

    def __post_init__(self):
        if self.dims is not None :
            self.axis = [self.dims.index('lat'), self.dims.index('lon')]
        if self.axis is None :
            self.axis = (0, 1)

    def to_quantity(self, inplace=False):

        logger.info(f"{inplace = }")

        # 1) Move the lat and lon to last positions:

        if self.axis[1] > self.axis[0] :
            # If lat is before lon:
            data = moveaxis(self.data, self.axis[1], -1)  # Move lon to last position
            data = moveaxis(data, self.axis[0], -2)       # Move lat to before last position
        else:
            # if lon is before lat
            data = moveaxis(self.data, self.axis[0], -1)  # Move lat to last position
            data = moveaxis(data, self.axis[1], -1)       # Move lon to last position

        # Multiply by the grid cell area
        data = data * self.grid.area

        if self.axis[1] > self.axis[0]:
            # If lat is before lon:
            data = moveaxis(data, -2, self.axis[0])  # Move lat from before last position to original location
            data = moveaxis(data, -1, self.axis[1])  # Move lon from last position to original position
        else :
            # If lon is before lat:
            data = moveaxis(data, -1, self.axis[1])  # Move lon from last position to original position
            data = moveaxis(data, -1, self.axis[2])  # Move lat from last position to original position

        # Return
        if inplace :
            self.data = data
            self.density = False
            return self
        else :
            return GriddedData(data, self.grid, self.axis, density=False, dims=self.dims)

    def to_density(self, inplace=False):

        logger.info(f"{inplace = }")

        # 1) Move the lat and lon to last positions:

        if self.axis[1] > self.axis[0] :
            # If lat is before lon:
            data = moveaxis(self.data, self.axis[1], -1)  # Move lon to last position
            data = moveaxis(data, self.axis[0], -2)       # Move lat to before last position
        else:
            # if lon is before lat
            data = moveaxis(self.data, self.axis[0], -1)  # Move lat to last position
            data = moveaxis(data, self.axis[1], -1)       # Move lon to last position

        # Multiply by the grid cell area
        data = data / self.grid.area

        if self.axis[1] > self.axis[0]:
            # If lat is before lon:
            data = moveaxis(data, -2, self.axis[0])  # Move lat from before last position to original location
            data = moveaxis(data, -1, self.axis[1])  # Move lon from last position to original position
        else :
            # If lon is before lat:
            data = moveaxis(data, -1, self.axis[1])  # Move lon from last position to original position
            data = moveaxis(data, -1, self.axis[2])  # Move lat from last position to original position

        # Return
        if inplace :
            self.data = data
            self.density = True
            return self
        else :
            return GriddedData(data, self.grid, self.axis, density=True, dims=self.dims)

    def transform(self, destgrid: Grid, padding: Union[float, int, bool]=None, inplace: bool=False) -> "GriddedData":
        """
        Regrid (crop, refine, coarsen, pad) data on a different grid.
        Arguments:
            :param destgrid: grid in which the output data should be.
            :param padding: If a value is provided, the regridded data will be padded with this value where the boundaries of the destination grid exceed those from the source grid.
            :param inplace: determine whether the regridding operation should return a new object or
        """
        data = self

        density = False
        if self.density :
            data = data.to_quantity(inplace=inplace)
            density = True

        if padding is not None :
            data = data.pad(destgrid, padding, inplace=inplace)

        if destgrid < self.grid :
            data = data.crop(destgrid, inplace=inplace)

        if data.grid.dlon < destgrid.dlon and data.grid.dlat < destgrid.dlat :
            data = data.coarsen(destgrid, inplace=inplace)

        if density :
            data = data.to_density(inplace=inplace)

        return data

    def coarsen(self, destgrid : Grid, inplace=False):
        logger.info(destgrid)

        # ensure that the new grid is within the old one
        assert self.grid >= destgrid

        # Compute overlap ratios between the two grids
        overlaps = calc_overlap_matrices(self.grid, destgrid)

        # Create a temporary data container for regridding along longitude:
        shp = list(self.data.shape)
        shp[self.axis[1]] = destgrid.nlon
        temp = zeros(shp)

        # Move the longitude to 1st position in temp array, and to last position in self.data:
        temp = moveaxis(temp, self.axis[1], 0)
        self.data = moveaxis(self.data, self.axis[1], -1)

        # Do the longitude coarsening:
        for ilon in tqdm(range(destgrid.nlon)):
            temp[ilon, :] = (self.data * overlaps.lon[:, ilon]).sum(-1)

        # Put the dimensions back in the right order:
        self.data = moveaxis(self.data, -1, self.axis[1])
        temp = moveaxis(temp, 0, self.axis[1])

        # Create final coarsened array:
        shp[self.axis[0]] = destgrid.nlat
        coarsened = zeros(shp)

        # Swap the dimensions again:
        coarsened = moveaxis(coarsened, self.axis[0], 0)
        temp = moveaxis(temp, self.axis[0], -1)

        # Do the latitude coarsening:
        for ilat in tqdm(range(destgrid.nlat)):
            coarsened[ilat, :] = (temp * overlaps.lat[:, ilat]).sum(-1)

        # Put the dimensions back in place:
        coarsened = moveaxis(coarsened, 0, self.axis[0])
        del temp

        # Return:
        if inplace :
            self.data = coarsened
            self.grid = destgrid
            return self
        else :
            return GriddedData(coarsened, destgrid, axis=self.axis, density=self.density, dims=self.dims)

    def refine(self, destgrid : Grid, inplace=False) :
        raise NotImplementedError

        #TODO: the code below might work, but needs to be tested before being used.

        # # Create an intermediate grid, with the same resolution as the new grid and the same boundaries as the original one:
        # tgrid = Grid(lat0=self.grid.lat0, lat1=self.grid.lat1, dlat=destgrid.dlat,
        #              lon1=self.grid.lon1, lon0=self.grid.lon0, dlon=destgrid.dlon)
        #
        # # Calculate transision matrices:
        # trans = calc_overlap_matrices(self.grid, tgrid)
        #
        # # Do the regridding:
        # shp = self.data.shape
        # shp[self.axis[0]] = tgrid.nlat
        # shp[self.axis[1]] = tgrid.nlon
        # out = zeros(shp)
        #
        # for ilat in range(tgrid.nlat):
        #     outlat = out.take(0, axis=self.axis[0]) * 0.
        #     # Move lat axis in last position to perform the multiplication, then move it back to original position
        #     data = self.data.swapaxes(self.axis[0], -1).copy()
        #     data *= trans.lat
        #     data = data.swapaxes(-1, self.axis[0])
        #     data = data.sum(axis=self.axis[0])
        #
        #     for ilon in range(tgrid.nlon):
        #         # We have lost one axis, account for it if needed:
        #         ax1 = self.axis[1]
        #         if self.axis[1] > self.axis[0] :
        #             ax1 = self.axis[1] - 1
        #
        #         # Repeat the axis swap trick:
        #         data = data.swapaxes(ax1, -1)
        #         data *= trans.lon
        #         data = data.swapaxes(-1, ax1)
        #
        #         data = data.sum(axis=ax1) # This has all dims of self.data except lat and lon
        #
        #         # Store this in output array:
        #         put_along_axis(outlat, ilon, data, ax1) # outlat has all dims of self.data except lat
        #     put_along_axis(out, ilat, outlat, self.axis[0])
        #
        # out = GriddedData(out, tgrid, axis=self.axis).crop(destgrid)
        # if inplace :
        #     self.data = out.data
        #     self.grid = destgrid
        #     return self
        # else :
        #     return out

    def crop(self, destgrid, inplace=False):
        logger.info(destgrid)

        # ensure that the new grid is a subset of the old one
        assert destgrid.lat0 in self.grid.latb
        assert destgrid.lat1 in self.grid.latb
        assert destgrid.lon0 in self.grid.lonb
        assert destgrid.lon1 in self.grid.lonb
#        assert all([l in self.grid.latc for l in destgrid.latc])
#        assert all([l in self.grid.lonc for l in destgrid.lonc])

        # crop:
        #slat = array([l in destgrid.latc for l in self.grid.latc])
        #slon = array([l in destgrid.lonc for l in self.grid.lonc])
        slat = array([destgrid.lat0 < l < destgrid.lat1 for l in self.grid.latc])
        slon = array([destgrid.lon0 < l < destgrid.lon1 for l in self.grid.lonc])

        data = self.data.swapaxes(self.axis[0], 0)
        data = data[slat, :, :]
        data = data.swapaxes(0, self.axis[0])
        data = data.swapaxes(self.axis[1], 0)
        data = data[slon, :, :]
        data = data.swapaxes(0, self.axis[1])

        newgrid = Grid(latc=self.grid.latc[slat], lonc=self.grid.lonc[slon], dlat=self.grid.dlat, dlon=self.grid.dlon)

        if inplace :
            self.data = data
            self.grid = newgrid
            return self
        else :
            return GriddedData(data, newgrid, self.axis, density=self.density, dims=self.dims)

    def pad(self, boundaries : Grid, padding, inplace=False):
        """
        Expand the existing arrays with "padding", up to the boundaries of the "destgrid".
        the "destgrid" argument is ideally an instance of the "Grid" class, but can also just be a dictionary.
        """
        logger.info(f"{boundaries = }; {padding = }")

        # 1) Create a new grid:
        pad_before_lon, lon0 = 0, self.grid.lon0
        while lon0 > boundaries['lon0'] :
            lon0 -= self.grid.dlon
            pad_before_lon += 1
        pad_before_lat, lat0 = 0, self.grid.lat0
        while lat0 > boundaries['lat0'] :
            lat0 -= self.grid.dlat
            pad_before_lat += 1
        pad_after_lon, lon1 = 0, self.grid.lon1
        while lon1 < boundaries['lon1'] :
            lon1 += self.grid.dlon
            pad_after_lon += 1
        pad_after_lat, lat1 = 0, self.grid.lat1
        while lat1 < boundaries['lat1'] :
            lat1 += self.grid.dlat
            pad_after_lat += 1
        newgrid = Grid(dlon=self.grid.dlon, dlat=self.grid.dlat, lon0=lon0, lon1=lon1, lat0=lat0, lat1=lat1)

        # 2) Create an array based on that grid, fill with "padding"
        # numpy "pad" method requires the number of elements to be added before and after, for each dim:
        padding_locations = [(0,0) for _ in range(len(self.data.shape))]
        padding_locations[self.axis[0]] = (pad_before_lat, pad_after_lat)
        padding_locations[self.axis[1]] = (pad_before_lon, pad_after_lon)

        data = pad(self.data, padding_locations, constant_values=padding)

        # 4) Return or modify self, based in the requested "inplace"
        if inplace :
            return GriddedData(data, newgrid, self.axis, density=self.density, dims=self.dims)
        else :
            self.data = data
            self.grid = newgrid
            return self

    def as_dataArray(self, coords: dict=None, dims: list=None, attrs: dict=None, **kwargs):
        if dims is None and self.dims is None :
            logger.error("Dimensions must be provided, either through the dims keyword or when instantiating the class")
        if coords is None :
            kwargs['lat'] = kwargs.get('lat', self.grid.latc)
            kwargs['lon'] = kwargs.get('lon', self.grid.lonc)
            coords = {}
            for dim in self.dims :
                coords[dim] = kwargs.get(dim)
        return xr.DataArray(
            data = self.data,
            dims = self.dims,
            coords = coords,
            attrs = attrs
        )


def grid_from_rc(rcf, name=None):
    pfx1 = 'grid.' 
    if name is not None :
        pfx0 = f'grid.{name}.'
    else :
        pfx0 = pfx1
    lon0 = rcf.get(f'{pfx0}lon0', default=rcf.get(f'{pfx1}lon0', default=None))
    lon1 = rcf.get(f'{pfx0}lon1', default=rcf.get(f'{pfx1}lon1', default=None))
    dlon = rcf.get(f'{pfx0}dlon', default=rcf.get(f'{pfx1}dlon', default=None))
    nlon = rcf.get(f'{pfx0}nlon', default=rcf.get(f'{pfx1}nlon', default=None))
    lat0 = rcf.get(f'{pfx0}lat0', default=rcf.get(f'{pfx1}lat0', default=None))
    lat1 = rcf.get(f'{pfx0}lat1', default=rcf.get(f'{pfx1}lat1', default=None))
    dlat = rcf.get(f'{pfx0}dlat', default=rcf.get(f'{pfx1}dlat', default=None))
    nlat = rcf.get(f'{pfx0}nlat', default=rcf.get(f'{pfx1}nlat', default=None))
    return Grid(lon0=lon0, lat0=lat0, lon1=lon1, lat1=lat1, dlon=dlon, dlat=dlat, nlon=nlon, nlat=nlat)
