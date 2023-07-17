#!/usr/bin/env python

import setuptools

setuptools.setup(
    name="lumia",
    packages=['transport'],
    python_requires='>=3.9',
    install_requires=['loguru', 'pandas', 'tqdm', 'netcdf4', 'tables', 'h5py', 'cartopy', 'xarray', 'pint', 'scipy'],
    extras_require={'interactive': ['ipython']},
    data_files=[]
)
