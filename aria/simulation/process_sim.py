"""
simulation/process_sim.py

Process Simulator
=================
Simulates concurrent OS processes that request and release resources.
Each process runs in its own thread using a declarative action script.

Action script format (list of tuples):
  ('acquire', resource_id)   →  request the resource; retry until granted
  ('work',    seconds)       →  simulate CPU work (sleep)
  ('release', resource_id)   →  release a held resource

Example — a process that holds R1 while requesting R2:
    script = [
        ('acquire', 'R1'),
        ('work',    0.1),
        ('acquire', 'R2'),   # will block if R2 is held → potential deadlock
        ('work',    0.2),
        ('release', 'R1'),
        ('release', 'R2'),
    ]
"""

import threading
import time
from typing import Callable, List, Tuple


Action = Tuple   # ('acquire'|'work'|'release', ...)


class SimProcess(threading.Thread):
    """
    A simulated OS process that executes a declarative action script.
    Retries blocked resource requests every RETRY_INTERVAL seconds.
    """

    RETRY_INTERVAL = 0.05

    def __init__(
        self,
        process_id:  str,
        request_fn:  Callable[[str, str], bool],
        release_fn:  Callable[[str, str], None],
        script:      List[Action],
        start_delay: float = 0.0,
    ):
        super().__init__(name=process_id, daemon=True)
        self.process_id = process_id
        self._request   = request_fn
        self._release   = release_fn
        self.script     = script
        self.start_delay = start_delay
        self.completed  = False
        self.log: List[str] = []

    def run(self):
        time.sleep(self.start_delay)
        self._print("started")

        for action in self.script:
            op = action[0]

            if op == "acquire":
                rid = action[1]
                self._print(f"requesting {rid}")
                granted = False
                while not granted:
                    granted = self._request(self.process_id, rid)
                    if not granted:
                        time.sleep(self.RETRY_INTERVAL)
                self._print(f"acquired  {rid}")

            elif op == "work":
                secs = action[1]
                self._print(f"working   ({secs}s)")
                time.sleep(secs)

            elif op == "release":
                rid = action[1]
                self._release(self.process_id, rid)
                self._print(f"released  {rid}")

        self.completed = True
        self._print("ALL TASKS COMPLETE")

    def _print(self, msg: str) -> None:
        entry = f"  [{self.process_id}] {msg}"
        self.log.append(entry)
        print(entry)
