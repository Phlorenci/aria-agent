"""
aria/rag_monitor.py

Resource Allocation Graph (RAG) Monitor
========================================
Tracks which processes hold and wait for resources in real time.
Detects deadlock cycles using depth-first search on the wait-for graph.

Two types of graph edges:
  Assignment edge  →  resource owns process   (process HOLDS resource)
  Request edge     →  process waits resource  (process BLOCKED, waiting)

Deadlock detection reduces to finding a cycle in the "wait-for" graph:
  Process A → Process B  if A is waiting for a resource currently held by B.
"""

import threading
import time
from collections import defaultdict
from typing import Dict, List, Optional, Set


class RAGMonitor:
    """
    Live Resource Allocation Graph.
    All public methods are thread-safe.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self.held: Dict[str, Set[str]]     = defaultdict(set)  # pid  → {rid}
        self.waiting: Dict[str, Set[str]]  = defaultdict(set)  # pid  → {rid}
        self.owner: Dict[str, Optional[str]] = {}              # rid  → pid
        self.event_log: List[dict]         = []

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def register_resource(self, resource_id: str) -> None:
        """Declare a new resource (initially unowned)."""
        with self._lock:
            if resource_id not in self.owner:
                self.owner[resource_id] = None

    def request(self, process_id: str, resource_id: str) -> bool:
        """
        Process requests resource_id.
        Returns True  → granted immediately (resource was free).
        Returns False → blocked (another process holds it).
        """
        with self._lock:
            self._log("request", process_id, resource_id)
            current = self.owner.get(resource_id)

            if current is None:
                self._grant(process_id, resource_id)
                return True
            if current == process_id:
                return True                           # already owns it

            # Block — add request (wait) edge to the graph
            self.waiting[process_id].add(resource_id)
            return False

    def release(self, process_id: str, resource_id: str) -> None:
        """Release a held resource. No-op if caller does not own it."""
        with self._lock:
            if self.owner.get(resource_id) == process_id:
                self.owner[resource_id] = None
                self.held[process_id].discard(resource_id)
                self._log("release", process_id, resource_id)

    def force_preempt(self, process_id: str, resource_id: str) -> None:
        """ARIA removes a process's wait edge (used during loan resolution)."""
        with self._lock:
            self.waiting[process_id].discard(resource_id)
            self._log("preempt", process_id, resource_id)

    def grant_waiting(self, process_id: str, resource_id: str) -> None:
        """ARIA directly grants a resource to a process after clearing a block."""
        with self._lock:
            self.waiting[process_id].discard(resource_id)
            if self.owner.get(resource_id) is None:
                self._grant(process_id, resource_id)

    def detect_deadlock(self) -> Optional[List[str]]:
        """
        Builds the wait-for graph and runs DFS cycle detection.
        Returns list of process IDs forming the cycle, or None if no deadlock.
        """
        with self._lock:
            return self._find_cycle()

    def snapshot(self) -> dict:
        """Returns a point-in-time copy of the full RAG state."""
        with self._lock:
            return {
                "held":    {k: list(v) for k, v in self.held.items()},
                "waiting": {k: list(v) for k, v in self.waiting.items()},
                "owner":   dict(self.owner),
            }

    # ------------------------------------------------------------------ #
    # Private helpers                                                      #
    # ------------------------------------------------------------------ #

    def _grant(self, pid: str, rid: str) -> None:
        self.owner[rid] = pid
        self.held[pid].add(rid)
        self._log("grant", pid, rid)

    def _log(self, event_type: str, pid: str, rid: str) -> None:
        self.event_log.append({
            "time": round(time.time(), 4),
            "type": event_type,
            "process": pid,
            "resource": rid,
        })

    def _build_wait_for(self) -> Dict[str, Set[str]]:
        """
        Derives the wait-for graph from the current RAG.
        P1 → P2 if P1 is waiting for a resource owned by P2.
        """
        wf: Dict[str, Set[str]] = defaultdict(set)
        for pid, resources in self.waiting.items():
            for rid in resources:
                holder = self.owner.get(rid)
                if holder and holder != pid:
                    wf[pid].add(holder)
        return wf

    def _find_cycle(self) -> Optional[List[str]]:
        """DFS cycle detection on the wait-for graph."""
        wf = self._build_wait_for()
        visited:   Set[str] = set()
        rec_stack: Set[str] = set()

        def dfs(node: str, path: List[str]) -> Optional[List[str]]:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            for neighbor in wf.get(node, set()):
                if neighbor not in visited:
                    result = dfs(neighbor, path)
                    if result is not None:
                        return result
                elif neighbor in rec_stack:
                    start = path.index(neighbor)
                    return path[start:]          # the cycle
            path.pop()
            rec_stack.remove(node)
            return None

        for node in list(wf.keys()):
            if node not in visited:
                result = dfs(node, [])
                if result is not None:
                    return result
        return None
