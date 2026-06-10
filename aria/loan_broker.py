"""
aria/loan_broker.py

Memory Loan Broker
==================
Simulates non-destructive deadlock resolution via memory page remapping.

Real-world OS analogy:
  - mmap / mremap   → remap virtual address space
  - Page table edit → change physical page frame mappings

ARIA resolution flow (without killing any process):
  1. Identify the victim process (lowest priority in the deadlock cycle).
  2. Temporarily remap its held memory pages to the beneficiary process.
  3. The beneficiary completes its critical section and releases resources.
  4. Pages are restored to the original owner via restore().
  5. No process is terminated; work is not lost.
"""

import threading
import time
from typing import Dict, List, Optional


class PageTable:
    """
    Simulates a per-process virtual-to-physical page mapping.
    In a real kernel this lives in the MMU/TLB.
    """

    def __init__(self, process_id: str):
        self.process_id = process_id
        self.pages: Dict[str, str] = {}    # virtual_page_id → physical_frame_id
        self._lock = threading.Lock()

    def map(self, page_id: str, frame_id: str) -> None:
        with self._lock:
            self.pages[page_id] = frame_id

    def unmap(self, page_id: str) -> Optional[str]:
        """Remove a mapping and return the physical frame, or None."""
        with self._lock:
            return self.pages.pop(page_id, None)

    def has_page(self, page_id: str) -> bool:
        with self._lock:
            return page_id in self.pages

    def __repr__(self) -> str:
        return f"PageTable({self.process_id}): {self.pages}"


class MemoryLoanBroker:
    """
    Coordinates temporary page remapping between processes.
    Maintains a ledger of active loans so they can be fully restored.
    """

    def __init__(self):
        self.page_tables: Dict[str, PageTable] = {}
        self._active_loans: List[dict] = []    # loans not yet restored
        self.audit_log: List[dict]     = []    # complete history
        self._lock = threading.Lock()
        self._loan_counter = 0

    # ------------------------------------------------------------------ #
    # Setup                                                                #
    # ------------------------------------------------------------------ #

    def register_process(self, process_id: str) -> None:
        if process_id not in self.page_tables:
            self.page_tables[process_id] = PageTable(process_id)

    def allocate_pages(self, process_id: str, pages: Dict[str, str]) -> None:
        """Give a process an initial set of virtual_page → physical_frame mappings."""
        pt = self.page_tables.get(process_id)
        if pt:
            for page_id, frame_id in pages.items():
                pt.map(page_id, frame_id)

    # ------------------------------------------------------------------ #
    # Loan / Restore                                                       #
    # ------------------------------------------------------------------ #

    def loan(self, from_pid: str, to_pid: str, page_ids: List[str]) -> Optional[int]:
        """
        Temporarily remaps page_ids from from_pid's page table to to_pid's.
        Returns a loan_id (int) on success, or None if loan could not be made.
        """
        from_pt = self.page_tables.get(from_pid)
        to_pt   = self.page_tables.get(to_pid)
        if not from_pt or not to_pt:
            return None

        loaned_frames: Dict[str, str] = {}
        for page_id in page_ids:
            frame = from_pt.unmap(page_id)
            if frame:
                to_pt.map(page_id, frame)
                loaned_frames[page_id] = frame

        if not loaned_frames:
            return None

        with self._lock:
            loan_id = self._loan_counter
            self._loan_counter += 1
            record = {
                "id":        loan_id,
                "from":      from_pid,
                "to":        to_pid,
                "pages":     loaned_frames,
                "start":     time.time(),
                "restored":  False,
            }
            self._active_loans.append(record)
            self.audit_log.append(record)
        return loan_id

    def restore(self, loan_id: int) -> bool:
        """
        Return all loaned pages to their original owner.
        Returns True on success.
        """
        with self._lock:
            record = next(
                (r for r in self._active_loans if r["id"] == loan_id), None
            )
            if not record or record["restored"]:
                return False

            from_pt = self.page_tables.get(record["from"])
            to_pt   = self.page_tables.get(record["to"])

            for page_id, frame_id in record["pages"].items():
                if to_pt:
                    to_pt.unmap(page_id)
                if from_pt:
                    from_pt.map(page_id, frame_id)

            record["restored"]     = True
            record["restore_time"] = time.time()
            self._active_loans.remove(record)
            return True

    def active_loans(self) -> List[dict]:
        with self._lock:
            return list(self._active_loans)

    def restore_all(self) -> None:
        """Restore every outstanding loan (used at shutdown / cleanup)."""
        with self._lock:
            ids = [r["id"] for r in self._active_loans]
        for loan_id in ids:
            self.restore(loan_id)
