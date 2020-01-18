from collections import defaultdict
from typing import *

import numpy as np

from data import *
from log import log


def _risk(cnt: int, traj: Trajectory, itds: Dict[int, ITD]) -> float:
    """ Gets the risk value for the given trajectory with a specific
        count.
    """
    return cnt / sum(itd.count(traj) for _, itd in itds.items())


def _find_riskest(uid: int, itds: ITD) -> Trajectory:
    """ Find the trajectory with the highest risk value in an ITD.
    """
    itd = itds[uid]
    return max([[t, _risk(itd.count(t), t, itds)] for t in itd.trajectories],
               key=lambda x: x[1]
              )[0]


def _find_strong_relations(
        riskest: Dict[int, Trajectory]
        ) -> Dict[int, List[int]]:
    """ Finds the strong relationships.
    """
    t2uid = defaultdict(set)
    for uid, t in riskest.items():
        t2uid[t].add(uid)
    relations = defaultdict(list)
    for t, uids in t2uid.items():
        if len(uids) > 1:
            for uid in uids:
                relations[uid] = list(uids - set([uid]))
    return relations


def _find_weak_relations(
        riskest: Dict[int, Trajectory],
        itds: Dict[int, ITD],
        strong_relations: Dict[int, List[int]]
        ) -> Tuple[Dict[int, List[int]], Dict[int, List[int]]]:
    """ Finds the weak relationships.
    """
    if not strong_relations:
        strong_relations = _find_strong_relations(riskest)
    weak = defaultdict(list)
    for uid1, itd1 in itds.items():
        for uid2, itd2 in itds.items():
            if (uid1 != uid2
                    and uid1 in riskest
                    and riskest[uid1] in itds[uid2].trajectories
                    and uid2 not in strong_relations[uid1]):
                weak[uid1] += uid2,
    return weak


def _affected_by(
        riskest: Dict[int, Trajectory],
        itds: Dict[int, ITD],
        ) -> Dict[int, List[int]]:
    """ Lists affected users when one user's privacy parameter changes.
    """
    affected = {uid: [uid] for uid in itds}

    strong_relations = _find_strong_relations(riskest)
    for k, v_list in strong_relations.items():
        for v in v_list:
            affected[v] += k,

    weak_relations = _find_weak_relations(riskest, itds, strong_relations)
    for k, v_list in weak_relations.items():
        for v in v_list:
            affected[v] += k,

    return affected


def _format_matrix(mat: List[List[float]]) -> List[str]:
    """ Formats matrix for printing.
    """
    def format_val(val: float) -> str:
        return (" " if val >= 0 else "") + "%3.2f" % val
    return ["[%s]" % ", " .join(format_val(val) for val in row) for row in mat]


def compute_CIDP(
        itds: Dict[int, ITD],            # A mapping from UID to ITD
        riskest: Dict[int, Trajectory],  # A mapping from UID to trajectory
        epsl: Dict[int, float],          # A mapping from UID to epsilon
        theta: float = 0.25              # Weak correlation coefficient
    ) -> Dict[int, float]:
    """ Correlated individual differencial privacy.
    """
    log.debug("Computing CIDP(epsilon={}, theta={})".format(epsl, theta))

    strong_relations = _find_strong_relations(riskest)
    weak_relations = _find_weak_relations(riskest, itds, strong_relations)

    #log.debug("strong relations: " + str(strong_relations))
    #log.debug("weak relations: " + str(weak_relations))

    # Note i, j are indices starts from 0. Indices are assigned to
    # users in an order sorted by their UID.
    idx2uid = {i: uid for i, uid in enumerate(sorted(itds.keys()))}
    uid2idx = {uid: i for i, uid in enumerate(sorted(itds.keys()))}
    n = len(itds)

    # Let mat_R[i][j] = -epsl_i when i and j are not related. This does
    # not affect the computation result
    mat_L = [[0] * n for _ in range(n)]
    mat_R = [[-epsl[idx2uid[i]]] * n for i in range(n)]

    # Let L[i][i] = #connections
    # Let L[i][j] = L[j][i] = -1 if related
    for i in range(n):
        for uid_j in strong_relations[idx2uid[i]]:
            j = uid2idx[uid_j]
            #log.debug("{} <-> {}".format(i, j))
            mat_L[i][i] += 0.5
            mat_L[j][j] += 0.5
            mat_L[i][j] = mat_L[j][i] = -1
            mat_R[i][j] = - epsl[idx2uid[i]]
            mat_R[j][i] = - epsl[idx2uid[j]]
        for uid_j in weak_relations[idx2uid[i]]:
            j = uid2idx[uid_j]
            #log.debug("{} --> {}".format(i, j))
            mat_L[i][i] += 1
            mat_L[j][j] += 1
            mat_L[i][j] = mat_L[j][i] = -1
            mat_R[i][j] = - epsl[idx2uid[i]] * theta
            mat_R[j][i] = 0

    # Let R[i][i] = epsl[i] / w[i]
    for i in range(n):
        # When L[i][i] == 0, this value will not be used in computing
        if mat_L[i][i]:
            mat_R[i][i] = epsl[idx2uid[i]] / mat_L[i][i]

    log.debug("L = " + "\n    ".join(_format_matrix(mat_L)))
    log.debug("R = " + "\n    ".join(_format_matrix(mat_R)))

    cidp = {idx2uid[i]: sum(mat_L[i][j] * mat_R[j][i] for j in range(n))
            for i in range(n)}
    log.debug(f"CIDP = {cidp}")
    return cidp


def compute_IDFA(
        itds: Dict[int, ITD],            # A mapping from UID to ITD
        riskest: Dict[int, Trajectory],  # A mapping from UID to trajectory
        epsl_init: float = 0.1,          # Initial privacy parameter
        beta: float = 0.05               # Step parameter
        ):
    """ Individual DF-optimization algorithm.
    """
    log.info(f"Computing IDFA(esplion_init={epsl_init}, beta={beta})")
    epsl = {uid: epsl_init for uid in itds}
    cidp = compute_CIDP(itds, riskest, epsl)

    affected = _affected_by(riskest, itds)
    log.debug(f"affected = {affected}")

    for uid in itds:
        log.info(f"Optimizing user {uid}...")
        if uid not in riskest:
            continue

        if epsl[uid] < cidp[uid] <= 1:
            while True:
                for uid_ in affected[uid]:
                    epsl[uid_] += beta
                cidp = compute_CIDP(itds, riskest, epsl)
                if cidp[uid] > 1:
                    break
        elif cidp[uid] > 1:
            while True:
                for uid_ in affected[uid]:
                    epsl[uid_] -= beta
                cidp = compute_CIDP(itds, riskest, epsl)
                if cidp[uid] <= 1:
                    break

    log.debug(f"epsl_opt = {epsl}")
    return epsl


def sanitize(
        itds: Dict[int, ITD],
        p :float = 0.5,            # risk threshold
        max_round :int = 1000      # maximum number of rounds
    ) -> Dict[int, Dict[Trajectory, float]]:
    noise_scale = {uid: [] for uid in itds}

    # Identify risky trajectories of each user and sort them by they
    # risk value in an ascending order.
    risky = {}
    for uid, itd in itds.items():
        tv = [(t, _risk(itd.count(t), t, itds)) for t in itd.trajectories]
        risky[uid] = [t for t, v in sorted(tv, key=lambda x: x[1]) if v >= p]
    log.debug(f"risky = {risky}")

    for round_ in range(1, max_round):
        log.info(f"Senitization iteration {round_}...")

        # Find the riskest trajectories of each user
        riskest = {uid: risky[uid].pop() for uid in itds if risky[uid]}
        log.debug("riskest = {"
                + "\n           ".join(f"{k}:{v}" for k, v in riskest.items())
                + "}")

        if not riskest:
            break

        # Sanitize risky trajectories
        epsl_opt = compute_IDFA(itds, riskest)

        for uid, itd in itds.items():
            if uid in riskest:
                # Reduce the risk dwon to threshold
                cnt = itd.count(riskest[uid])
                while True:
                    v = _risk(cnt, riskest[uid], itds)
                    if v < p: break
                    cnt -= 1
                loops = itd.count(riskest[uid]) - cnt
        
                #noise[uid] += abs(np.random.laplace(0, loops / epsl_opt[uid], 1))
                noise_scale[uid] += loops / epsl_opt[uid],
        log.info(f"noise_scale = {noise_scale}")

        # Add noisy to count
        noise_count = {uid: {} for uid in itds}
        for uid, itd in itds.items():
            for t in itd.trajectories:
                noise_count[uid][t] = itd.count(t)
                for scale in noise_scale[uid]:
                    noise_count[uid][t] += np.random.laplace(0, scale, 1)

        return noise_count
