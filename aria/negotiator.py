"""
aria/negotiator.py

Negotiator
==========
When the Fingerprinter raises a high-risk alarm or a full cycle is detected,
the Negotiator picks and applies a resolution strategy.

Strategies (in order of preference):
  1. Memory Loan   — loan contested pages from the victim to the beneficiary,
                     release victim's hold, grant beneficiary access. No kills.
  2. Lock Reorder  — clear the victim's wait edge so it retries later,
                     letting the beneficiary proceed first.
"""

import time
from typing import List, Optional


class Negotiator:
    """
    Selects and applies a resolution strategy for a detected deadlock cycle.
    """

    def __init__(self, rag_monitor, loan_broker):
        self.rag           = rag_monitor
        self.broker        = loan_broker
        self.resolution_log: List[dict] = []

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def resolve(self, cycle: List[str]) -> dict:
        """
        Given a cycle of process IDs (from RAG cycle detection):
          • Select a victim (process to temporarily preempt).
          • Identify the beneficiary (process blocked BY the victim).
          • Apply the best available strategy.
          • Return a resolution report dict.
        """
        victim      = self._select_victim(cycle)
        beneficiary = self._find_beneficiary(cycle, victim)

        snap                = self.rag.snapshot()
        victim_held         = list(snap["held"].get(victim, []))
        victim_waiting      = list(snap["waiting"].get(victim, []))
        beneficiary_waiting = list(snap["waiting"].get(beneficiary, []))

        # Resources the beneficiary needs that the victim currently holds
        contested = [r for r in victim_held if r in beneficiary_waiting]

        result = {
            "strategy":    None,
            "victim":      victim,
            "beneficiary": beneficiary,
            "contested":   contested,
            "success":     False,
            "details":     "",
            "timestamp":   time.time(),
        }

        if contested:
            result = self._apply_memory_loan(
                result, victim, beneficiary, contested, victim_waiting
            )
        else:
            result = self._apply_lock_reorder(
                result, victim, beneficiary, victim_waiting
            )

        self.resolution_log.append(result)
        return result

    # ------------------------------------------------------------------ #
    # Strategies                                                           #
    # ------------------------------------------------------------------ #

    def _apply_memory_loan(
        self,
        result:         dict,
        victim:         str,
        beneficiary:    str,
        contested:      List[str],
        victim_waiting: List[str],
    ) -> dict:
        """
        Strategy 1: Memory Loan
        -----------------------
        • Loan pages from victim → beneficiary (non-destructive).
        • Release the contested resources from the victim's hold.
        • Grant those resources to the beneficiary.
        • Clear the victim's wait edge (it will retry after beneficiary finishes).
        """
        loan_id = self.broker.loan(victim, beneficiary, contested)

        # Transfer resource ownership
        for rid in contested:
            self.rag.release(victim, rid)        # remove from victim
            self.rag.grant_waiting(beneficiary, rid)  # give to beneficiary

        # Remove victim from deadlock wait-for graph
        for rid in victim_waiting:
            self.rag.force_preempt(victim, rid)

        result.update({
            "strategy": "memory_loan",
            "loan_id":  loan_id,
            "success":  True,
            "details": (
                f"Pages {contested} loaned {victim} → {beneficiary}. "
                f"Cleared {victim}'s wait on {victim_waiting}. "
                f"Deadlock cycle broken without killing any process."
            ),
        })
        return result

    def _apply_lock_reorder(
        self,
        result:         dict,
        victim:         str,
        beneficiary:    str,
        victim_waiting: List[str],
    ) -> dict:
        """
        Strategy 2: Lock Reorder
        ------------------------
        • Clear the victim's wait edge so it steps back.
        • The beneficiary proceeds first; victim retries afterwards.
        """
        for rid in victim_waiting:
            self.rag.force_preempt(victim, rid)

        result.update({
            "strategy": "lock_reorder",
            "success":  True,
            "details": (
                f"Cleared {victim}'s wait on {victim_waiting}. "
                f"{beneficiary} now proceeds first. "
                f"{victim} will retry when resources are available."
            ),
        })
        return result

    # ------------------------------------------------------------------ #
    # Victim/beneficiary selection                                         #
    # ------------------------------------------------------------------ #

    def _select_victim(self, cycle: List[str]) -> str:
        """
        Select which process to temporarily preempt.
        Policy: last process in the detected cycle (least seniority).
        """
        return cycle[-1]

    def _find_beneficiary(self, cycle: List[str], victim: str) -> str:
        """
        The beneficiary is the process immediately before the victim in the
        cycle — it was blocked BY the victim and benefits most from the loan.
        """
        idx = cycle.index(victim)
        return cycle[(idx - 1) % len(cycle)]
