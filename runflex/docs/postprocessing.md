# LUMIA postprocessing

The postprocessing is handled by the `runflex.postprocess.postprocess_task` function, called at the end of each task (`runflex.tasks.Task`), if the `postprocess.lumia` settings has been set to `True` (default `False`):

1. Check that the FLEXPART simulation hasn't failed
2. Determine the destination file (lumia format) of release (footprints are grouped in monthly, site-specific LUMIA footprint files).
3. Open the FLEXPART *grid_time* file (`runflex.postprocess.GridTimeFile`):
    * retrieve the list and positions of footprints present in the file
    * open the *particles_final.nc*, if it exists (`netCDF4.Dataset`)
4. For each destination file:
    * open the file (`runflex.LumiaFile.__init__`)
    * For each of the observations that should end up in this file:
        * retrieve the footprint from the *grid_time* file (`runflex.postprocess.GridTimeFile.get`)
        * convert it into sparse format (`runflex.Release.footprint`)
        * store it in the destination file (`runflex.LumiaFile.add`)

## LUMIA file format

LUMIA footprint files are in HDF5 format, and contain a set footprints (sensitivity to surface fluxes) and, optionally, the sensitivity to background concentrations (particles final position).

The file is organized with a hierarchy of groups:

- at the root level:
    - **latitudes** and **longitudes** variables (center of the grid points)
    - a *origin* attribute, which contains a date used as reference for the time indices in the file
    - a *run_loutstep* attribute (time step of the footprints)
    - a large number of diagnostic attributes: such as run settings (settings passed through the FLEXPART *COMMAND* and *OUTGRID* files, prefixed with *run_*), species settings (FLEXPART *SPECIES* file, prefixed with *species_*), etc.
- each footprint is contained in a [HDF5 group](https://confluence.hdfgroup.org/display/HDF5/HDF5+File+Organization), named after the observation ID (typically following the format [sitecode].[height]m.[date]-[time])
    - each group contains:
        - four variables: **ilats**, **ilons**, **itims** and **sensi**:
            - **sensi** contains the non-zero components of the footprint. The **sensi** variables has three attributes: *units* (should be *s m3 kg-1*), *runflex_version" (date of the runflex git commit) and "runglex_commit" (hash of the runflex commit).
            - **ilats** and **ilons** contains the latitude and longitude indices of the elements in **sensi** (in the grid defined by the top-level **latitude** and **longitude** variables);
            - **itims** contains the temporal indices of the elements in **sensi**, on an axis defined by the top-level *origin* the absolute value of the *run_loutstep* attributes.
        - a set of diagnostic attributes (release characteristics + run characteristics if they differ from the top-level ones).
    - each group may also contain a **background** subgroup, with the following variables:
        - coordinates: **lon**, **lat**, **height**, **time**
        - state of the atmosphere / of the surface: **surface_height**, **potential_vorticity**, **specific_humidity**, **air_density**, **pbl_height**, **tropopause_height**, **temperature**
        - release info: **release_time**
        - state of the particles: **active**

Below is an example of partial `ncdump -h` output (limited to one observation) for one footprint file:

```
netcdf hun.115m.2018-11 {
dimensions:
        phony_dim_420 = 160 ;
        phony_dim_421 = 200 ;
variables:
        float latitudes(phony_dim_420) ;
                string latitudes:units = "degrees North" ;
                string latitudes:info = "center of the grid cells" ;
        float longitudes(phony_dim_421) ;
                string longitudes:units = "degrees East" ;
                string longitudes:info = "center of the grid cells" ;

// global attributes:
                string :run_Conventions = "CF-1.6" ;
                string :run_title = "FLEXPART model output" ;
                string :run_institution = "NILU" ;
                string :run_source = "Version 10.4 (2019-11-12) model output" ;
                string :run_history = "2022-11-30 18:53 +0100  created by guillaume on donkey2" ;
                string :run_references = "Stohl et al., Atmos. Chem. Phys., 2005, doi:10.5194/acp-5-2461-200" ;
                :run_outlon0 = -15.f ;
                :run_outlat0 = 33.f ;
                :run_dxout = 0.25f ;
                :run_dyout = 0.25f ;
                :run_ldirect = -1 ;
                string :run_ibdate = "20181029" ;
                string :run_ibtime = "140000" ;
                string :run_iedate = "20181115" ;
                string :run_ietime = "150000" ;
                :run_loutstep = -3600 ;
                :run_loutaver = -3600 ;
                :run_loutsample = -900 ;
                :run_itsplit = 99999999 ;
                :run_lsynctime = -900 ;
                :run_ctl = 0.2f ;
                :run_ifine = 5 ;
                :run_iout = 1 ;
                :run_ipout = 0 ;
                :run_lsubgrid = 1 ;
                :run_lconvection = 1 ;
                :run_lagespectra = 1209600 ;
                :run_ipin = 0 ;
                :run_ioutputforeachrelease = 1 ;
                :run_iflux = 0 ;
                :run_mdomainfill = 0 ;
                :run_ind_source = 1 ;
                :run_ind_receptor = 2 ;
                :run_mquasilag = 0 ;
                :run_nested_output = 0 ;
                :run_surf_only = 0 ;
                :run_linit_cond = 0 ;
                string :origin = "2018-11-01 00:00:00" ;
                :species_ohcconst = -9.e-10f ;
                :species_ohdconst = -9.9f ;
                string :species_units = "s m3 kg-1" ;
                string :species_long_name = "AIRTRACER" ;
                :species_decay = -0.07001485f ;
                :species_weightmolar = 29.f ;
                :species_vsetaver = 0.f ;


group: hun.115m.20181130-183000 {
  dimensions:
  	phony_dim_419 = 79504 ;
  variables:
  	short ilats(phony_dim_419) ;
  	short ilons(phony_dim_419) ;
  	short itims(phony_dim_419) ;
  	float sensi(phony_dim_419) ;
  		string sensi:units = "s m3 kg-1" ;
  		string sensi:runflex_version = "2022.11.18" ;
  		string sensi:runflex_commit = "a69d332c5a50b9cfa77625333ac801abacdca94a (2022-11-18 14:47:12+01:00)" ;

  // group attributes:
  		string :release_name = "hun.115m.20181130-183000" ;
  		:release_lat1 = 46.9558982849121 ;
  		:release_lat2 = 46.9558982849121 ;
  		:release_lon1 = 16.652099609375 ;
  		:release_lon2 = 16.652099609375 ;
  		:release_z1 = 115. ;
  		:release_z2 = 115. ;
  		:release_kindz = 1LL ;
  		string :release_start = "2018-11-30 18:30:00" ;
  		string :release_end = "2018-11-30 18:30:00" ;
  		:release_npart = 10000LL ;
  		:release_mass = 10000. ;
  		string :release_run_history = "2022-11-30 20:46 +0100  created by guillaume on donkey2" ;
  		string :release_run_ibdate = "20181115" ;
  		string :release_run_ibtime = "220000" ;
  		string :release_run_iedate = "20181202" ;
  		string :release_run_ietime = "170000" ;

  group: background {
    dimensions:
    	phony_dim_418 = 10000 ;
    variables:
    	byte active(phony_dim_418) ;
    	float air_density(phony_dim_418) ;
    	float height(phony_dim_418) ;
    	float lat(phony_dim_418) ;
    	float lon(phony_dim_418) ;
    	float pbl_height(phony_dim_418) ;
    	float potential_vorticity(phony_dim_418) ;
    	int release_time(phony_dim_418) ;
    	float specific_humidity(phony_dim_418) ;
    	float surface_height(phony_dim_418) ;
    	float temperature(phony_dim_418) ;
    	int time(phony_dim_418) ;
    		string time:units = "seconds since 2018-12-02 17:00:00" ;
    		string time:calendar = "proleptic_gregorian" ;
    	float tropopause_height(phony_dim_418) ;
    } // group background
  } // group hun.115m.20181130-183000
  ...
}
```

## Footprints (sensitivity to fluxes)

The footprints are converted from the native FLEXPART format (*grid_time* files) to the LUMIA footprint format described above. In the *grid_time* files, the footprints are stored in the **spec001_ms** variable:

- The variable has six dimensions (*nageclass, pointspec, time, height, latitude* and *longitude*), however, *nageclass* and *height* are normally of size 1, so the variable can be interpreted as a set of *n_releases* 3D arrays. 
- The postprocessing method (`postprocess.GridTimeFile.get`) returns a `postprocess.Release` object, which gives access to the data as a set of one array of non-zero values (**sensi**) and coordinate indices (**ilons**, **ilats** and **itims**). It also applies units conversions (from *s.m<sup>3</sup>/kg* to *s.m<sup>2</sup>/mol*)

The code

```python
from runflex import postprocess
f = postprocess.GridTimeFile.get('grid_time_20200608000000')
fp = f.get('xxx.1m.20200602-120000').footprint
```
is the equivalent of:

```python
from netCDF4 import Dataset, chartostring
from numpy import meshgrid, nonzero, zeros

# Retrieve the sparse version of the footprint "xxx.1m.20200602-120000" 
# from the file "grid_time_20200608000000.nc"
with Dataset('grid_time_20200608000000.nc') as ds:

    # Retrieve dimensions
    nlon = ds.dimensions['longitude'].size                          # in postprocess.GridTimeFile.__init__
    nlat = ds.dimensions['latitude'].size
    nrelease = ds.dimension['pointspec'].size

    # Create gridded versions of the time, lons and lats coordinates
    time, lons, lats = meshgrid(range(nt), range(nlat), range(nlon), indexing='ij')

    # Retrieve the footprint index:
    releases = [t.strip() for t in chartostring(ds['RELCOM'][:])]
    i_release = releases.get("xxx.1m.20200602-120000")              # in postprocess.GridTimeFile.get

    # Retrieve the first footprint of the file:
    data = ds['spec001_ms'][:][0, i_release, :, 0, :, :]
    indices = nonzero(data)                                         # in postprocess.Release.footprint
    sensi = data[indices]
    ilats = lats[indices]
    ilons = lons[indices]
    itims = times[indices]

    # Apply units conversions (from s.m^3/kg to s.m^2/mol)
    height = ds['height'][:][0]                # 
    sensi *= 1000 * ds['spec001_ms'] / height

# Reconstruct the full matrix (e.g. in lumia):
fp = zeros((nt, nlat, nlon))
fp[itims, ilats, ilons] = sensi
```

In order to facilitate the use of these footprints, the time indices are aligned, so that `itims = n` refers to the same date and time for all footprints in the file (this is because one lumia footprint file can contain footprints from several FLEXPART simulations):

- a reference time is defined (1st day of the month, 0:00). It is stored in the top-level *origin* attribute of the lumia footprint file.
- the value of `itims` is shifted by `nshift = (origin - run_start) / run_dt`, with `run_start` the end of the FLEXPART run (i.e. the *ibdate* and *ibtime* attributes, in backward mode), and *dt* the time step of the footprints, i.e. the *loutstep* attribute of the grid_time file:

```python
from pandas import Timestamp, Timedelta

origin = Timestamp(2020, 6, 1)
with Dataset('grid_time_20200608000000.nc') as ds:

    # [...]

    # adjust the time indices
    run_start = Timestamp(ds.ibdate + ds.ibtime)
    dt = Timedelta(ds.loutstep)
    shift_t = (origin - run_start) / dt

    itims += shift_t

# Reconstruct the footprint, but aligning it with an annual array of emissions:
origin_emis = Timestamp(2020, 6, 1)
shift_t_emis = (origin - origin_emis) / dt
fp = zeros((nt_year, nlat, nlon))
fp[itims + shift_t_emis, ilat, ilons] = sensi
```

## Final positions (sensitivity to background concentrations)

The final position of the particles is written by FLEXPART in the *particles_final.nc* file, when running the *dev* branch (`output_mod.f90` file). The file stores the coordinates of the particles:
- when they got deactivated (when they reached the domain boundary or their age limit)
- or at the end of the simulation, for the particles that were still alive

The file is structured in groups (one for each observation/release), with the following variables:

- coordinates: **lon**, **lat**, **height**, **time**
- state of the atmosphere / of the surface: **surface_height**, **potential_vorticity**, **specific_humidity**, **air_density**, **pbl_height**, **tropopause_height**, **temperature**
- release info: **release_time**
- state of the particles: **active**

```
netcdf particles_final {

group: htm.150m.20180101-120000 {
  dimensions:
        particles = 10000 ;
  variables:
        float lon(particles) ;
        float lat(particles) ;
        float height(particles) ;
        float surface_height(particles) ;
        float potential_vorticity(particles) ;
        float specific_humidity(particles) ;
        float air_density(particles) ;
        float pbl_height(particles) ;
        float tropopause_height(particles) ;
        float temperature(particles) ;
        int release_time(particles) ;
        int time(particles) ;
                time:units = "seconds since 2018-01-08 12:00:00" ;
                time:calendar = "proleptic_gregorian" ;
        byte active(particles) ;
  } // group htm.150m.20180101-120000
  ... 
}
```

The variables are all copied under the `background` subgroup of the corresponding observations in the lumia footprint files. However, for convenience, the **time** variable is adjusted from **"seconds since [the start of the FLEXPART simulation]"** to **"seconds since [the "origin" of the file]"**:

- the start of the FLEXPART simulation refers here to *iedate/ietime* in backward mode (*ibdate/ibtime* in forward mode)
- the origin of the file is the *origin* attribute, defined when processing the footprints.