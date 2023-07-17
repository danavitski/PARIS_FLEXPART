#!/usr/bin/env python

import subprocess
import sys
from pandas import Timestamp, Timedelta
from omegaconf import DictConfig
from runflex.utilities import checkpath
from runflex.meteo import Meteo
from runflex.releases import Releases
from runflex.compile import Flexpart
from runflex.postprocess import postprocess_task
import os
import shutil
from loguru import logger
from dataclasses import dataclass
from typing import Union
from pathlib import Path
from runflex.files import Command, Outgrid, Species
from runflex.utilities import getfile
from multiprocessing import RLock


meteo_lock = RLock()


@dataclass(kw_only=True)
class JobInfo:
    rundir: str
    rcf: DictConfig
    releases: Releases
    jobid: int
    status: str = None

    @property
    def dict(self) -> dict:
        return {k: v for k, v in vars(self).items() if k in self.__annotations__}


@dataclass
class Task:
    releases: Releases
    rcf: DictConfig
    rundir: Union[Path, str]
    jobid: int = None
    start: Timestamp = None
    end: Timestamp = None
    interactive: bool = False
    status: str = None

    def __post_init__(self):

        self.rundir = checkpath(self.rundir).absolute()

        # Make sure rc-variables are updated
        self.rcf.paths.run = self.rundir

        if not self.interactive:
            logger.info(f"Task {self.jobid} logging to {self.rcf.run.logfile}")
            logger.remove()
            logger.add(os.path.join(self.rcf.run.logfile), colorize=True, mode='w')

    @property
    def okfile(self) -> str:
        return os.path.abspath(os.path.join(self.rundir, 'flexpart.ok'))

    @property
    def completed(self) -> bool:
        return os.path.exists(self.okfile)

    @property
    def command(self) -> Command:
        tmax = self.releases.time.max()
        tmin = self.releases.time.min()
        lenmax = self.rcf.releases.length
        tmin = tmin - Timedelta(days=lenmax)

        command = Command.read(self.rcf.paths.command)
        if 'command' in self.rcf:
            command.update(self.rcf.command)

        dt = Timedelta(seconds=command.LOUTAVER)
        start, end = tmin, tmax
        if dt <= Timedelta(days=1):
            start = Timestamp(start.strftime('%Y%m%d'))
            end = Timestamp(end.strftime('%Y%m%d'))
            while start + dt < tmin:
                start += dt
            while end < tmax:
                end += dt
        else:
            logger.error("LOUTAVER longer than 24 hours is not implemented in runflex (but it should be doable)")
            raise NotImplementedError

        self.start = start
        self.end = end

        command.IBDATE = self.start
        command.IBTIME = self.start
        command.IEDATE = self.end
        command.IETIME = self.end

        return command

    @property
    def outgrid(self) -> Outgrid:

        x0, x1, dx = self.rcf.outgrid.x
        y0, y1, dy = self.rcf.outgrid.y
        nx = (x1 - x0) / dx
        ny = (y1 - y0) / dy

        grid = Outgrid(
            OUTLAT0=y0, OUTLON0=x0,
            NUMXGRID=nx, NUMYGRID=ny, DXOUT=dx, DYOUT=dy,
            OUTHEIGHTS=self.rcf.outgrid.levels
        )
        return grid

    @property
    def flexpart(self) -> Flexpart:
        return Flexpart(build=self.rcf.paths.build)

    def setup_species(self) -> None:
        checkpath(os.path.join(self.rundir, 'SPECIES'))
        spec = self.rcf.releases.species
        if isinstance(spec, int):
            shutil.copy(getfile(f'SPECIES_{spec:03.0f}'), os.path.join(self.rundir, 'SPECIES'))
        elif isinstance(spec, DictConfig):
            Species(**self.rcf.releases.species).write(self.rundir / 'SPECIES' / f'SPECIES_999', name='SPECIES_PARAMS', prefix='P')

    def setup_meteo(self) -> None:
        with meteo_lock:
            logfile = self.rcf.meteo.get('logfile', sys.stdout)
            if self.interactive:
                logfile = sys.stdout
            meteo = Meteo(
                path=self.rcf.paths.meteo,
                archive=self.rcf.meteo.get('archive', None),
                prefix=self.rcf.meteo.prefix,
                tres=self.rcf.meteo.interv,
                task_id=self.jobid,
                logfile=logfile
            )
            meteo.check_unmigrate(self.start, self.end)
            meteo.write_AVAILABLE(os.path.join(self.rundir, 'AVAILABLE'))
            if self.rcf.meteo.get('cleanup', False):
                meteo.cleanup(threshold=self.rcf.meteo.cleanup.threshold, nfilesmin=self.rcf.meteo.cleanup.nfilesmin)

    def setup_pathnames(self) -> None:
        with open(os.path.join(self.rundir, 'pathnames'), 'w') as fid:
            fid.write(f'{self.rundir.absolute()}/\n')
            fid.write(f'{self.rundir.absolute()}/\n')
            fid.write(f'{Path(self.rcf.paths.meteo).absolute()}/\n')
            fid.write(os.path.join(self.rundir.absolute(), 'AVAILABLE'))

    def setup_releases(self) -> None:
        spec = self.rcf.releases.species
        if isinstance(spec, int):
            self.releases.species = [spec]
        else :
            self.releases.species = ['999']
        self.releases.loc[:, 'mass'] = self.rcf.releases.mass
        self.releases.loc[:, 'npart'] = self.rcf.releases.npart
        self.releases.write(os.path.join(self.rundir, 'RELEASES'))

    def copy_datafiles(self) -> None:
        shutil.copy(getfile('surfdata.t'), self.rundir)
        shutil.copy(getfile('surfdepo.t'), self.rundir)
        shutil.copy(getfile('IGBP_int1.dat'), self.rundir)

    def setup(self) -> None:

        # COMMAND file
        self.command.write(os.path.join(self.rundir, 'COMMAND'), name='COMMAND')

        # SPECIES
        self.setup_species()

        # OUTGRID
        self.outgrid.write(os.path.join(self.rundir, 'OUTGRID'), name='OUTGRID')

        # RELEASES file
        self.setup_releases()

        # meteo (AVAILABLE)
        self.setup_meteo()

        # pathnames
        self.setup_pathnames()

        # land use and surfdepo
        self.copy_datafiles()

        # flexpart.x
        self.flexpart.setup(Path(self.rundir) / 'flexpart.x')

    def run(self, retry: bool = True) -> "Task":

        # Do not run the task if a "flexpart.ok" file has been found in the output folder (avoid overwriting existing data).
        if self.completed:
            logger.info(f'Found okfile at {self.okfile}, returning ...')
            self.status = 'skipped'
            return self

        # Setup the task
        self.setup()

        # Run FLEXPART
        if not self.interactive:
            log_id = logger.add(sys.stdout, colorize=True, enqueue=True)
            with open(self.rcf.run.logfile, 'a') as fid:
                self.status = self.runflexpart(fid)
            match self.status:
                case 'success':
                    logger.success(f'Task {self.jobid} completed ({self.rcf.run.logfile})')
                case 'failed':
                    logger.error(f'Task {self.jobid} failed ({self.rcf.run.logfile})')
                    if retry:
                        # Make another attempt, sometimes it's enough ...
                        self.run(retry=False)
            logger.remove(log_id)
        else:
            self.status = self.runflexpart(sys.stdout)

        if self.rcf.postprocess.get('lumia', False):
            postprocess_task(self)

        return self

    def runflexpart(self, stdout) -> str:
        origin = os.getcwd()
        os.chdir(self.rundir)
        status = subprocess.run(['./flexpart.x'], stdout=stdout)
        os.chdir(origin)
        if status.returncode == 0 and self.completed:
            return 'success'
        return 'failed'

    @classmethod
    def run_from_JobInfo(cls, jobinfo: JobInfo, interactive: bool = False):
        return cls(**jobinfo.dict, interactive=interactive).run()
