from ast import literal_eval
import collections
import os
import re
import yaml
from typing import *

import pandas as pd
import numpy as np

from log import log


PROJECT_ROOT = '.'
DATA_PATH = os.path.join(PROJECT_ROOT, 'data')
TRAJ_FILE = os.path.join(DATA_PATH, 'selected.csv')

THETA = 0.5  # p - risk threshold


class Trajectory(object):
    """ Movement trajectory (Def. 1). Different from the definition,
    we do not record time in trjectory, which should not affect the
    computation.
    
    Arguments:
        location
    """
    def __init__(self, locations):
        self.locations = tuple(locations)
        
    def __hash__(self):
        return hash(self.locations)
    
    def __eq__(self, other):
        return self.__class__ == other.__class__ and self.locations == other.locations
    
    def __repr__(self):
        return '<Trajectory {}>'.format(str(self.locations))

    
class ITDBuilder(object):
    """ The builder class for ITD. """
    def __init__(self, uid):
        self.uid = uid
        self.trajs = collections.Counter()
        
    def add(self, trajectory):
        self.trajs[trajectory] += 1


class ITD(object):
    """ Individual trajectory database (Def. 2, 3, 4, 5).
    """
    def __init__(self, builder, traj_freq):
        self._uid = builder.uid
        self._ts = []
        self._t2idx = {}
        self._t2cnt = {}
        for idx, (traj, cnt) in enumerate(builder.trajs.items()):
            self._ts += traj,
            self._t2idx[traj] = idx
            self._t2cnt[traj] = cnt

    @property
    def uid(self) -> int:
        return self._uid

    @property
    def trajectories(self) -> List[Trajectory]:
        return self._ts

    def id(self, t: Trajectory) -> int:
        if t not in self._t2idx:
            raise Exception
        return self._t2idx[t]

    def count(self, t: Trajectory) -> int:
        return self._t2cnt[t] if t in self._t2cnt else 0

    def contains(self, t: Trajectory) -> bool:
        return t in self._ts
        
    def __repr__(self) -> str:
        fmt_traj = ',\n     '.join(
                'tid:{} cnt:{} {}'.format(self._t2idx[t], self._t2cnt[t], t)
                for t in self._ts)
        return '<ITD uid:{}\n     {}>'.format(self.uid, fmt_traj)


def load_ITDs() -> Dict[int, ITD]:
    df = pd.read_csv(open(TRAJ_FILE, 'r'),
                     header=0,
                     names=['uid', 'date', 'traj_site', 'traj_arr'],
                     parse_dates=['date'])
    df['traj_site'] = df['traj_site'].apply(lambda x: literal_eval(x))
    df['traj_arr'] = df['traj_arr'].apply(lambda x: literal_eval(x))

    # For ITD
    traj_freq = collections.Counter()
    itd_bdlrs = {}
    for _, (uid, date, sites, areas) in df.iterrows():
        # Costruct trajectory using area codes.
        traj = Trajectory(areas)
        if uid not in itd_bdlrs:
            itd_bdlrs[uid] = ITDBuilder(uid)
        itd_bdlrs[uid].add(traj)
        traj_freq[traj] += 1
    # A mapping from user ID to the crossponding ITD
    ITDs = {bdlr.uid: ITD(bdlr, traj_freq) for bdlr in itd_bdlrs.values()}

    log.debug(
            "Loading ITDs\n" +
            "\n".join(repr(itd) for _, itd in ITDs.items()))

    return ITDs
