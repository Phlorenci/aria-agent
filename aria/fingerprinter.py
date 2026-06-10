"""
aria/fingerprinter.py

Deadlock Fingerprinter
======================
Analyses the current RAG snapshot and assigns a deadlock RISK SCORE
*before* a full cycle forms. Fires an early warning when risk >= threshold.

Risk factors scored:
  +1 per process that is both holding AND waiting         (active contender)
  +2 per mutual AB-BA hold pair                          (classic 2-proc pattern)
  +1 if the wait chain depth is >= 3 processes            (long chain)
"""

from typing import Dict, List, Set

RISK_THRESHOLD = 3


class DeadlockFingerprinter:
    """
    Heuristic pre-deadlock risk scorer.
    Does NOT require a full cycle — fires warnings early.
    """

    def score(self, snapshot: dict) -> int:
        """Return an integer risk score. >= RISK_THRESHOLD means high danger."""
        held    = {k: set(v) for k, v in snapshot["held"].items()}
        waiting = {k: set(v) for k, v in snapshot["waiting"].items()}
        owner   = snapshot["owner"]

        total  = 0
        total += self._active_contenders(held, waiting)
        total += self._mutual_pairs(held, waiting, owner)
        total += self._chain_depth(waiting, owner)
        return total

    def is_risky(self, snapshot: dict) -> bool:
        """True if score meets or exceeds the risk threshold."""
        return self.score(snapshot) >= RISK_THRESHOLD

    def describe(self, snapshot: dict) -> str:
        s = self.score(snapshot)
        if s == 0:
            return "no risk"
        if s < RISK_THRESHOLD:
            return f"low risk (score={s})"
        return f"HIGH RISK — deadlock likely (score={s})"

    # ------------------------------------------------------------------ #
    # Scoring components                                                   #
    # ------------------------------------------------------------------ #

    def _active_contenders(
        self,
        held: Dict[str, Set[str]],
        waiting: Dict[str, Set[str]],
    ) -> int:
        """Count processes that both hold something AND are waiting. +1 each."""
        return sum(
            1 for pid in held
            if held[pid] and waiting.get(pid)
        )

    def _mutual_pairs(
        self,
        held: Dict[str, Set[str]],
        waiting: Dict[str, Set[str]],
        owner: dict,
    ) -> int:
        """
        Classic AB-BA pattern:
          P1 holds R1 and waits for R2 held by P2,
          P2 holds R2 and waits for R1 held by P1.
        Each such pair scores +2.
        """
        score = 0
        pids = list(held.keys())
        for i in range(len(pids)):
            for j in range(i + 1, len(pids)):
                a, b = pids[i], pids[j]
                a_waits_from_b = any(
                    owner.get(r) == b for r in waiting.get(a, set())
                )
                b_waits_from_a = any(
                    owner.get(r) == a for r in waiting.get(b, set())
                )
                if a_waits_from_b and b_waits_from_a:
                    score += 2
        return score

    def _chain_depth(
        self,
        waiting: Dict[str, Set[str]],
        owner: dict,
    ) -> int:
        """
        Build the wait-for chain and measure its depth.
        Depth >= 3 earns +1 additional risk point.
        """
        # Simple single-edge wait-for (first resource each process waits for)
        wf: Dict[str, str] = {}
        for pid in waiting:
            for rid in waiting[pid]:
                holder = owner.get(rid)
                if holder and holder != pid:
                    wf[pid] = holder
                    break

        max_depth = 0
        visited: Set[str] = set()

        def depth(node: str) -> int:
            if node in visited or node not in wf:
                return 0
            visited.add(node)
            return 1 + depth(wf[node])

        for pid in wf:
            visited.clear()
            d = depth(pid)
            if d > max_depth:
                max_depth = d

        return 1 if max_depth >= 3 else 0
