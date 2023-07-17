import xarray as xr

def ImportFluxes_asArray(biofile,fossilfile,oceanfile,firesfile):
    bio = xr.open_dataarray(biofile)
    fossil = xr.open_dataarray(fossilfile)
    ocean = xr.open_dataarray(oceanfile)
    fires = xr.open_dataarray(firesfile)
    fluxes = xr.Dataset({'fossil':fossil, 'ocean':ocean, 'nee':bio, 'fires':fires}).to_netcdf('emissions.nc', group='co2')

ImportFluxes_asArray()
