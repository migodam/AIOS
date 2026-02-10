---

# AIOS — Agentic Interactive Operating System

**Replayable Closed-Loop Learning Architecture (Windows Demo)**

---

## 1. Objective

AIOS is a research-grade closed-loop agent operating layer designed to:

* continuously observe user and system interaction
* learn long-term procedural behavior patterns
* build a persistent interaction knowledge graph (operation FSM / behavior graph)
* enable agents to query learned procedural memory
* remain fully replayable, auditable, and evolvable

The system implements a full loop:

**Observe → Parse → Learn → Decide → Act → Learn**

---

## 2. Layered System Architecture

AIOS is organized into five vertical layers connected by two extensible protocol buses.

### Layers

1. Observer Layer
2. Protocol1 Layer (Perception + Learning)
3. Agent Layer
4. Protocol2 Layer (Action Planning)
5. Actuator Layer

### Buses

* **Protocol1 BUS** — carries structured `ObservationEvent`
* **Protocol2 BUS** — carries executable `ActionPlan`

Both buses are append-only and replayable.

---

## 3. Observer Layer

Observers are independent modules that capture raw signals without semantic interpretation.

### Screenshot Observer

* full-screen capture
* artifact stored externally
* emits `screenshot_ref`

### UIA Observer

* Windows accessibility tree extraction
* focused window metadata
* emits `uia_ref`

### Log Tail Observer

* deterministic system log tail
* emits `tail_ref`

Each observer produces **RawSignal records** referenced by artifact hash.

---

## 4. Protocol1 — Perception and Learning Layer

Protocol1 converts raw signals into structured knowledge and continuously learns interaction structure.

### 4.1 Aggregation

Signals from multiple observers are temporally aligned into a single observation frame.

### 4.2 LLM Parsing

An online LLM extracts structured semantic interaction features:

* UI state
* environment state
* operation context
* interaction intent signals

### 4.3 Schema Validation

All outputs are validated against strict ObservationEvent schema.

If LLM parsing fails, a deterministic rule-based fallback produces a low-fidelity but schema-valid record.

### 4.4 Interaction Graph (Learning Memory)

Protocol1 maintains a persistent **Interaction Graph**:

**Nodes**

* application states
* UI contexts
* environment states

**Edges**

* user operations
* agent actions
* state transitions

The graph continuously expands and supports:

* procedural skill discovery
* operation sequence learning
* behavior clustering
* long-term pattern extraction

Graph versions are stored incrementally for reproducibility.

### 4.5 Emission

Protocol1 emits:

```
ObservationEvent (aggregated)
+ GraphUpdate
```

to the Protocol1 BUS.

---

## 5. Agent Layer

The core agent performs a continuous **OODA loop**:

1. Observe — receive ObservationEvent
2. Orient — query Interaction Graph memory
3. Decide — generate policy decision
4. Act — emit ActionPlan

Decision mechanisms may combine:

* rule-based guards
* retrieval-augmented reasoning
* LLM policy inference

---

## 6. Protocol2 — Action Planning Layer

Protocol2 converts agent intent into executable actions.

### Steps

1. Plan compilation
2. Constraint enforcement
3. Safety validation
4. Dry-run verification
5. Dispatch

Each action plan contains:

* action type
* parameters
* constraints
* trace_id
* safety flags

---

## 7. Actuator Layer

Actuators execute validated actions:

* keyboard input
* mouse control
* optional UI focus control

Each execution returns a **receipt**:

* success / error
* latency
* post-action state reference

Receipts are fed back into the observation stream.

---

## 8. Reproducibility and Replay

The entire system is replayable using:

### Event Stream (JSONL)

Append-only sequence:

```
RawSignals → ObservationEvents → ActionPlans → Receipts
```

### Artifact Store

External artifacts referenced by:

* hash
* path
* timestamp

### Replay Harness

Allows:

* deterministic offline evaluation
* regression testing
* policy comparison

---

## 9. Learning Capability (Key Contribution)

Unlike traditional agent pipelines, AIOS integrates **learning directly inside Protocol1**.

Protocol1 does not only parse perception signals — it builds a continuously evolving **operation knowledge graph**, enabling the agent to:

* learn user workflows
* learn game strategies
* learn application usage patterns
* reuse procedural experience across tasks

This enables long-term adaptive agent behavior without retraining the base model.

---

## 10. Demo Scenario (Windows)

The demo system demonstrates:

* Chrome Dino gameplay observation
* obstacle detection via perception pipeline
* agent jump/duck decision loop
* continuous interaction graph learning
* deterministic replay of gameplay sessions

---

## 11. Design Principles

* Replayability first
* Protocol-driven modular architecture
* Extensible multi-observer multi-actuator buses
* Learning embedded at perception layer
* Safety-gated execution
* Evolutionary system growth

---

## 12. Future Extensions

* hierarchical task graphs
* multi-agent collaborative execution
* long-horizon skill composition
* autonomous UI navigation learning
* cross-application behavior transfer

---
