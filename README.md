# ARIA — Autonomous Resource Intelligence Agent

> An AI-powered OS middleware agent that predicts, negotiates, and resolves deadlocks without killing a single process — using Memory Management and Concurrency principles.

---

## The Problem

Every major cloud outage has one silent killer: **deadlocks**. Processes waiting on each other forever, with no way out.

Traditional OS solutions are broken:

| Approach             | Problem                                     |
| -------------------- | ------------------------------------------- |
| Banker's Algorithm   | Too conservative — blocks valid allocations |
| Detection + Kill     | Destructive — terminates innocent processes |
| Manual lock ordering | Rigid — breaks under dynamic workloads      |

**ARIA takes a third path.**

---

## What ARIA Does

ARIA is a middleware agent that sits between concurrent processes and the OS kernel.

It intercepts resource requests, learns deadlock-prone patterns, and resolves circular waits autonomously before they fully form.

### Three Core Components

| Component              | Role                                                                                                                                   |
| ---------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| **Fingerprinter**      | Learns historical deadlock-prone request patterns and raises alerts 2–3 steps before a circular wait closes                            |
| **Negotiator**         | Dynamically reschedules lock acquisitions to break potential cycles without process awareness                                          |
| **Memory Loan Broker** | Temporarily remaps a memory page from one process to another via page table manipulation, then restores it without killing any process |

---

## System Architecture

### Flow

```text
Processes
    ↓
ARIA Agent
(Fingerprinter + Negotiator + Loan Broker)
    ↓
OS Kernel
(Resource Allocator + Memory Manager)
```

---

## OS Concepts Applied

### Memory Management

* Virtual memory remapping
* Page table manipulation
* Memory page migration

### Concurrency / Deadlock

* Resource Allocation Graph (RAG) monitoring
* Circular wait detection
* Lock rescheduling
* Priority inversion handling

---

## Implementation Phases

### 1. RAG Monitor

Kernel module intercepting `lock()` and `malloc()` calls while maintaining a live directed Resource Allocation Graph.

### 2. Fingerprint Engine

Pattern model trained on historical RAG snapshots preceding known deadlocks.

### 3. Memory Loan Broker

Non-destructive deadlock resolution using page remapping between competing processes.

### 4. Negotiation Engine

Dynamic lock reordering with timed delays and priority boosts.

### 5. Simulation & Evaluation

Stress testing against:

* Producer-Consumer workloads
* Dining Philosophers problem
* Database transaction lock workloads

---

## Real-World Impact

A system like ARIA could have prevented:

* The 2017 AWS S3 outage caused by cascading internal process locks
* Database transaction deadlocks in high-concurrency OLTP systems
* Microservice resource contention in cloud schedulers

---

## Tech Stack

**Languages**

* C
* Python (simulation layer)

**Operating System**

* Linux (Ubuntu 24)

**Core Technologies & Concepts**

* POSIX Threads
* `mmap`
* `/proc` filesystem
* Resource Allocation Graphs (RAG)

---

## Project Context

Operating Systems class project exploring Agentic AI applied to core OS resource management problems.

---

## Author

**Mirzarakhimov Bobur**

* Sejong University
* 3rd Year Student
* Operating Systems Project

Email: [boburmirzarakhimov2006@gmail.com](mailto:boburmirzarakhimov2006@gmail.com)

LinkedIn: Bobur Mirzarakhimov
