"""
aria/agent.py

ARIA Agent — Orchestrator
=========================
The central controller that intercepts resource requests and runs
a background monitor thread polling for risk every POLL_INTERVAL seconds.

Architecture:
  intercept_request()  →  RAGMonitor.request()     (log + grant/block)
  background thread    →  Fingerprinter.is_risky()  (early warning)
                       →  RAGMonitor.detect_deadlock() (cycle check)
                       →  Negotiator.resolve()       (intervention)
"""

import threading
import time
from typing import Optional

from .rag_monitor  import RAGMonitor
from .fingerprinter import DeadlockFingerprinter
from .loan_broker   import MemoryLoanBroker
from .negotiator    import Negotiator

POLL_INTERVAL = 0.05   # seconds between risk-check polls


class ARIAAgent:
    """
    The ARIA agent.

    Quick start:
        agent = ARIAAgent()
        agent.start()
        agent.register_resource("R1")
        agent.register_process("P1", pages={"pageA": "frame1"})
        granted = agent.intercept_request("P1", "R1")
        agent.release("P1", "R1")
        agent.stop()
    """

    def __init__(self, verbose: bool = True):
        self.verbose       = verbose
        self.rag           = RAGMonitor()
        self.fingerprinter = DeadlockFingerprinter()
        self.broker        = MemoryLoanBroker()
        self.negotiator    = Negotiator(self.rag, self.broker)

        self._running          = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._interventions    = 0
        self._warned_cycles    = set()   # avoid re-resolving same cycle twice

    # ------------------------------------------------------------------ #
    # Lifecycle                                                            #
    # ------------------------------------------------------------------ #

    def start(self) -> None:
        """Start ARIA's background monitor thread."""
        self._running = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="ARIA-Monitor",
        )
        self._monitor_thread.start()
        self._log("ARIA started — intercepting resource requests")

    def stop(self) -> None:
        """Stop the monitor and clean up outstanding memory loans."""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=1.0)
        self.broker.restore_all()
        self._log(
            f"ARIA stopped — total interventions: {self._interventions}"
        )

    # ------------------------------------------------------------------ #
    # Public interception API                                              #
    # ------------------------------------------------------------------ #

    def register_resource(self, resource_id: str) -> None:
        self.rag.register_resource(resource_id)
        self._log(f"  [REGISTER] resource {resource_id}")

    def register_process(
        self, process_id: str, pages: Optional[dict] = None
    ) -> None:
        """Register a process and optionally seed its page table."""
        self.broker.register_process(process_id)
        if pages:
            self.broker.allocate_pages(process_id, pages)
        self._log(f"  [REGISTER] process {process_id}" +
                  (f" with pages {list(pages.keys())}" if pages else ""))

    def intercept_request(self, process_id: str, resource_id: str) -> bool:
        """
        Call this instead of requesting directly from the OS.
        ARIA logs the request and returns grant status.
        """
        granted = self.rag.request(process_id, resource_id)
        status  = "GRANTED" if granted else "BLOCKED"
        self._log(f"  [{status}]  {process_id} → {resource_id}")
        return granted

    def release(self, process_id: str, resource_id: str) -> None:
        self.rag.release(process_id, resource_id)
        self._log(f"  [RELEASE]  {process_id} freed {resource_id}")

    def summary(self) -> dict:
        return {
            "interventions": self._interventions,
            "active_loans":  len(self.broker.active_loans()),
            "resolutions":   self.negotiator.resolution_log,
            "event_log":     self.rag.event_log,
            "snapshot":      self.rag.snapshot(),
        }

    # ------------------------------------------------------------------ #
    # Background monitor                                                   #
    # ------------------------------------------------------------------ #

    def _monitor_loop(self) -> None:
        while self._running:
            time.sleep(POLL_INTERVAL)
            self._check_and_intervene()

    def _check_and_intervene(self) -> None:
        snap = self.rag.snapshot()

        # Step 1 — Fingerprint early warning
        if self.fingerprinter.is_risky(snap):
            desc = self.fingerprinter.describe(snap)
            self._log(f"  [FINGERPRINT] {desc}")

        # Step 2 — Hard deadlock check (cycle detection)
        cycle = self.rag.detect_deadlock()
        if cycle:
            cycle_key = tuple(sorted(cycle))
            if cycle_key in self._warned_cycles:
                return                           # already resolving this cycle
            self._warned_cycles.add(cycle_key)

            arrow = " → ".join(cycle) + f" → {cycle[0]}"
            self._log(f"  [DEADLOCK DETECTED] {arrow}")

            result = self.negotiator.resolve(cycle)
            self._interventions += 1

            if result["success"]:
                self._log(
                    f"  [RESOLVED] strategy={result['strategy']} | "
                    f"{result['details']}"
                )
                # Allow re-detection if cycle re-forms later
                self._warned_cycles.discard(cycle_key)
            else:
                self._log(f"  [RESOLUTION FAILED]")

    # ------------------------------------------------------------------ #

    def _log(self, msg: str) -> None:
        if self.verbose:
            ts = time.strftime("%H:%M:%S")
            print(f"[ARIA {ts}] {msg}")
