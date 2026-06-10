"""
main.py — ARIA Agent Demo
==========================

Scenario: Three-process circular wait (Dining Philosophers variant)
-------------------------------------------------------------------
  P1 acquires R1, then tries to acquire R2  (held by P2)
  P2 acquires R2, then tries to acquire R3  (held by P3)
  P3 acquires R3, then tries to acquire R1  (held by P1)

Without ARIA  → all three processes deadlock indefinitely.
With ARIA     → Fingerprinter detects HIGH RISK early;
                cycle detector confirms the deadlock;
                Negotiator applies Memory Loan strategy;
                all processes complete successfully.

Run:
    python main.py
"""

import time

from aria.agent         import ARIAAgent
from simulation.process_sim import SimProcess

SEP  = "=" * 62
SEP2 = "-" * 62


def run_demo():
    print(SEP)
    print("  ARIA — Autonomous Resource Intelligence Agent")
    print("  Deadlock Prevention Demo  |  OS Class Project")
    print(SEP)

    # ------------------------------------------------------------------ #
    # 1. Initialise ARIA                                                   #
    # ------------------------------------------------------------------ #
    agent = ARIAAgent(verbose=True)
    agent.start()
    print()

    # Register resources
    for rid in ["R1", "R2", "R3"]:
        agent.register_resource(rid)
    print()

    # Register processes with simulated page tables
    agent.register_process("P1", pages={"page_A": "frame_01",
                                         "page_B": "frame_02"})
    agent.register_process("P2", pages={"page_C": "frame_03",
                                         "page_D": "frame_04"})
    agent.register_process("P3", pages={"page_E": "frame_05",
                                         "page_F": "frame_06"})
    print()

    # ------------------------------------------------------------------ #
    # 2. Build circular-wait scripts                                       #
    # ------------------------------------------------------------------ #
    #
    #  Each process acquires its "own" resource first (hold step),
    #  then tries to acquire the next process's resource → deadlock forms.
    #
    p1_script = [
        ("acquire", "R1"),
        ("work",    0.15),         # hold R1 while simulating some work
        ("acquire", "R2"),         # BLOCKS — P2 holds R2 → deadlock imminent
        ("work",    0.10),
        ("release", "R2"),
        ("release", "R1"),
    ]

    p2_script = [
        ("acquire", "R2"),
        ("work",    0.15),         # hold R2
        ("acquire", "R3"),         # BLOCKS — P3 holds R3 → deadlock imminent
        ("work",    0.10),
        ("release", "R3"),
        ("release", "R2"),
    ]

    p3_script = [
        ("acquire", "R3"),
        ("work",    0.15),         # hold R3
        ("acquire", "R1"),         # BLOCKS — P1 holds R1 → DEADLOCK
        ("work",    0.10),
        ("release", "R1"),
        ("release", "R3"),
    ]

    # ------------------------------------------------------------------ #
    # 3. Launch concurrent processes                                       #
    # ------------------------------------------------------------------ #
    print(SEP2)
    print("  Launching 3 concurrent processes...")
    print("  Wait-for chain will form: P1→P2→P3→P1 (circular)")
    print(SEP2)
    print()

    p1 = SimProcess("P1", agent.intercept_request, agent.release,
                    p1_script, start_delay=0.00)
    p2 = SimProcess("P2", agent.intercept_request, agent.release,
                    p2_script, start_delay=0.05)
    p3 = SimProcess("P3", agent.intercept_request, agent.release,
                    p3_script, start_delay=0.10)

    for p in [p1, p2, p3]:
        p.start()

    # ------------------------------------------------------------------ #
    # 4. Wait for completion or timeout                                    #
    # ------------------------------------------------------------------ #
    timeout    = 12.0
    start_time = time.time()
    processes  = [p1, p2, p3]

    while not all(p.completed for p in processes):
        if time.time() - start_time > timeout:
            print("\n[TIMEOUT] Processes did not finish within time limit.")
            break
        time.sleep(0.1)

    agent.stop()

    # ------------------------------------------------------------------ #
    # 5. Summary report                                                    #
    # ------------------------------------------------------------------ #
    summary  = agent.summary()
    all_done = all(p.completed for p in processes)

    print()
    print(SEP)
    print("  SIMULATION COMPLETE")
    print(SEP)
    print(f"  All processes completed  :  {all_done}")
    print(f"  ARIA interventions       :  {summary['interventions']}")
    print(f"  Active memory loans      :  {summary['active_loans']}")
    print(f"  Total RAG events logged  :  {len(summary['event_log'])}")

    if summary["resolutions"]:
        print()
        print("  Resolution log:")
        for r in summary["resolutions"]:
            print(f"    Strategy    : {r['strategy']}")
            print(f"    Victim      : {r['victim']}")
            print(f"    Beneficiary : {r['beneficiary']}")
            print(f"    Contested   : {r['contested']}")
            print(f"    Details     : {r['details']}")

    snap = summary["snapshot"]
    print()
    print("  Final RAG state:")
    print(f"    held    : {dict(snap['held'])}")
    print(f"    waiting : {dict(snap['waiting'])}")
    print(f"    owner   : {snap['owner']}")
    print(SEP)


if __name__ == "__main__":
    run_demo()
