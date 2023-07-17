#!/usr/bin/env python
  
import setuptools
import glob
import os


data_files = [_ for _ in glob.glob('inputs/**', recursive=True) if os.path.isfile(_)]
data_files += glob.glob('build/flexpart/flexpart.x')


setuptools.setup(
        name="runflex",
        version="1.0",
        author="Guillaume Monteil",
        author_email="guillaume.monteil@nateko.lu.se",
        description="runflex",
        long_description_content_type="text/markdown",
        packages=['runflex'],
        classifiers=[
            "Programming Language :: Python :: 3",
            "Operating System :: OS Independent",
        ],
        python_requires='>=3.10',
        install_requires=['loguru', 'pandas', 'tqdm', 'netcdf4', 'tables', 'h5py', 'omegaconf', 'gitpython', 'distro', 'pymdown-extensions', 'mkdocs'],
        extras_require={'interactive': ['ipython']},
        data_files=[
                ('share/flexpart/inputs/', data_files),
                ('share/flexpart/src/flexpart10.4/', [_ for _ in glob.glob('src/flexpart10.4/**', recursive=True) if os.path.isfile(_)]),
                ('share/flexpart/src/extras/', [_ for _ in glob.glob('src/extras/**', recursive=True) if os.path.isfile(_)]),
        ],
        scripts=['bin/runflex']
)
