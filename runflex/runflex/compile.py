#!/usr/bin/env python

import shutil
import os
import contextlib
import sys
from datetime import datetime
from dataclasses import dataclass
from loguru import logger

try :
    # If this file is imported by runflex as a module, this will work
    from runflex.utilities import checkpath, runcmd
except ModuleNotFoundError:
    # If it's called as a standalone script (using the if __name__ == '__main__', then this will work:
    from utilities import checkpath, runcmd
from pathlib import Path
import distro


@dataclass
class Flexpart:
    build : Path
    src : Path = None
    makefile : str = None
    extras : Path = None

    def __post_init__(self):
        if self.makefile is None :
            self.makefile = f'makefile.{distro.id()}.gfortran'
        self.build = Path(self.build)
        
        logger.info(f"Compiling FLEXPART into {self.build} using source codes from:")
        logger.info(f"  {self.src}")
        logger.info(f"  {self.extras}")
        logger.info(f"Using makefile {self.makefile}")

    def setup(self, dest: Path) -> None:
        shutil.copy(os.path.join(self.build, 'flexpart.x'), dest)

    def compile(self, dest : Path = None) -> None:

        assert self.src is not None, logger.error("Can't compile without a source code!")

        t0 = datetime.now()

        # Copy files to the build path:
        runcmd(f'rsync -avh {self.src}/ --include=*.f90 --include={self.makefile} --exclude=* {checkpath(self.build)}/')

        # Additional set of source files (typically, those that are specific to a machine or project, and not on the git repository)
        if self.extras is not None :
            runcmd(f'rsync -avh {self.extras}/ --include=*.f90 --include={self.makefile} --exclude=* {self.build}/')

        # Ensure that the makedepf90 dependencies file is deleted:
        (self.build / 'dependencies').unlink(missing_ok=True)

        # Make
        curdir = os.getcwd()
        os.chdir(self.build)

        # Remove previous executable if it exists
        with contextlib.suppress(FileNotFoundError):
            os.remove('flexpart.x')

        runcmd(f'make -f {self.makefile}')

        # Check if the executable
        try :
            t1 = datetime.fromtimestamp(os.path.getmtime('flexpart.x'))
        except FileNotFoundError:
            logger.exception("Compilation failed. Such sadness ...")
            sys.exit()

        os.chdir(curdir)
        if dest is not None and dest != self.build :
            (self.build / 'flexpart.x').rename(dest)

        if t0 > t1 :
            logger.error("Compilation aborted. The whole universe is against you.")
            raise RuntimeError


if __name__ == '__main__':
    from argparse import ArgumentParser

    p = ArgumentParser()
    p.add_argument('--build', help='build directory', type=Path)
    p.add_argument('--src', help='main source directory', type=Path)
    p.add_argument('--extra', help='extra source directory', type=Path)
    p.add_argument('--makefile', help='FLEXPART makefile', type=Path)
    p.add_argument('--bin', default=None, type=Path)

    args = p.parse_args(sys.argv[1:])

    fp = Flexpart(build=args.build, src=args.src, makefile=args.makefile, extras=args.extra)
    fp.compile(args.bin)
