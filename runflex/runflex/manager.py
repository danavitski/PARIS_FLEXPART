#!/usr/bin/env python
import time

from pandas import DataFrame, Timedelta
from typing import List
from multiprocessing import Pool, cpu_count
import os
from runflex.tasks import Task, JobInfo
from runflex.observations import Observations
from omegaconf import DictConfig
from tqdm import tqdm


class QueueManager:
    def __init__(self, rcf: DictConfig, obs: DataFrame, serial: bool = False) -> None:
        self.rcf = rcf
        self.obs = Observations(obs)
        # self.rcfile = os.path.join(self.rcf.paths.global_scratch, 'flexpart.rc')
        self.serial = serial
        self.ncpus = self.rcf.run.get('ncpus', cpu_count())

    def dispatch(self, nobsmax: int = None, maxdt: Timedelta = '7D', skiptasks: List[int] = None, chunks : List[int] = None) -> List[Task]:
        tasks = self.create_tasks(nobsmax=nobsmax, maxdt=maxdt, skiptasks=skiptasks, chunks=chunks)
        return self.submit(tasks)

    def create_tasks(self, nobsmax: int = None, maxdt: Timedelta = '7D', skiptasks: List[int] = None, chunks : List[int] = None) -> List[JobInfo]:
        if nobsmax is None :
            nobsmax = self.rcf.run.get('releases_per_task', 50)

        dbfiles = self.obs.split(nobsmax=nobsmax, ncpus=self.ncpus, maxdt=maxdt)

        tasks = []
        for jobnum, rl in enumerate(dbfiles):
            tasks.append(JobInfo(
                rundir=os.path.join(self.rcf.paths['run'], str(jobnum)),
                rcf=self.rcf,
                releases=rl,
                jobid=jobnum,
            ))

        if chunks :
            tasks = [j for j in tasks if j.jobid in chunks]

        if skiptasks:
            tasks = [j for j in tasks if j.jobid not in skiptasks]

        return tasks

    def submit(self, tasks: List[JobInfo]) -> List[Task]:
        """
        Submit the individual FLEXPART runs
        """
        if self.serial :
            tasks = [Task.run_from_JobInfo(j, interactive=True) for j in tasks]
        else :
            with Pool(processes=self.ncpus) as pp:
                results = pp.imap(Task.run_from_JobInfo, tasks, chunksize=1)
                tasks = [t for t in tqdm(results, total=len(tasks), )]

        return tasks
