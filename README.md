# Ultra Pipeline Framework v1 🚀

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)]()
[![License](https://img.shields.io/badge/license-MIT-green.svg)]()
[![Status](https://img.shields.io/badge/status-active-brightgreen.svg)()

> Production-grade AI agent orchestration toolkit — DAG-based context, self-evaluating pipelines, skill bundles with memory, and a unified orchestrator for long-running workflows.

**Inspired by cutting-edge 2026 research:** MUSE-AutoSkill (arXiv 2605.27366), Attention Residuals (Kimi/Moonshot), UserHarness ToM (UIUC), Self-Improving Agents (01 Systems), LeJEPA (Yann LeCun).

---

## The Problem We Solve

AI agent workflows today are **linear and unstructured**:

- Context grows indefinitely → token waste, context window overflow
- No way to compare runs → can't tell if a change improved things
- Skills are static markdown files → no memory, no tests, no validation
- No scientific approach to optimization → change everything at once, hope for the best
- Long-running workflows lose coherence → agent forgets why it made earlier decisions

## Our Approach: Four Modules, One Vision

| Module | What It Does | Research Inspiration |
|--------|-------------|---------------------|
| **DAG-Context Manager** | Reasoning as a compressible directed acyclic graph — not linear summary | MUSE-AutoSkill DAG compression |
| **Self-Evaluating Pipeline** | Scientific method for workflows: hypothesize → test one variable → score → iterate | Self-Improving Trading Agent |
| **Skill Bundler 2.0** | Executable skill bundles with tests, scripts, per-skill memory | MUSE-AutoSkill skill packages |
| **Ultra Pipeline** | Unified orchestrator with discrete state machine | UserHarness ToM, Opus 4.8 Ultra-Code |

### Architecture

```
┌─────────────────────────────────────────────────┐
│           ULTRA PIPELINE ORCHESTRATOR           │
│                                                 │
│  ┌──────────┐  ┌───────────┐  ┌─────────────┐  │
│  │DAG       │  │Self-Eval  │  │Skill        │  │
│  │Context   │◄─┤Pipeline   │◄─┤Bundler 2.0  │  │
│  │Manager   │  │Framework  │  │             │  │
│  └────┬─────┘  └────┬──────┘  └──────┬──────┘  │
│       │             │                │          │
│  ┌────▼─────────────▼────────────────▼──────┐   │
│  │         STATE MACHINE                     │   │
│  │  (discrete transitions, externalized)     │   │
│  └─────────────────┬────────────────────────┘   │
│                    │                             │
│  ┌─────────────────▼────────────────────────┐   │
│  │      FAN-OUT CONTROLLER                  │   │
│  │  (parallel workers, up to 5)             │   │
│  └──────────────────────────────────────────┘   │
└─────────────────────────────────────────────────┘
```

---

## Quick Start

### 1. DAG Context Manager — Reasoning as a Graph

```python
from dag_context import new_session, add_node, compress_dag, export_dag

# Start a session
session = new_session("my-task")

# Add reasoning nodes
add_node("plan", "Research the best approach for X")
add_node("action", "Run web search for X patterns")
add_node("observation", "Found 3 key papers on X")
add_node("decision", "Use approach from paper 2 — most practical")

# Compress when context gets large
nodes = compress_dag(level=2, budget=50000)

# Export for LLM injection
compact = export_dag(fmt="compact")
```

**Node types:** `plan`, `action`, `observation`, `decision`, `hypothesis`, `result`

**Compression:**
- Level 1: In-place summary (20K → 5K tokens per node)
- Level 2: Chain-level merge — middle turns fused, first & last pinned (71K → 42K)

### 2. Self-Evaluating Pipeline — Scientific Method for Workflows

```python
from self_eval_pipeline import new_pipeline, add_hypothesis, log_run

# Define what to measure
pipeline = new_pipeline("my-workflow", metrics=["speed", "accuracy", "cost"])

# Form a hypothesis — only change ONE variable
h = add_hypothesis("my-workflow", 
    "Using DAG compression reduces tokens by 30%",
    variable="context_strategy", expected_delta="-30%")

# Run and score
run = new_run("my-workflow", hypothesis_id=h["id"], mode="test")
run["scores"] = {"speed": 85, "accuracy": 92, "cost": 70}
log_run("my-workflow", run)
```

**Philosophy:** One variable. One test. Measurable outcome. Full stop.

### 3. Skill Bundler 2.0 — Executable Skills with Memory

A skill is **not** just a markdown file. It's a complete package:

```
skills/<name>/
├── SKILL.md              # Definition
├── meta.json             # Score, runs, confidence
├── memory/
│   ├── long_term.md      # Persistent knowledge across sessions
│   ├── mid_term.md       # Per-session context
│   └── short_term.md     # Per-run state (resets each time)
├── scripts/
│   └── <name>.py         # Executable automation
└── tests/
    └── test_<name>.py    # Validation (sandbox)
```

```bash
# Create a bundle
python3 skill_bundler.py init my-skill "Does X automatically"

# Validate (runs tests)
python3 skill_bundler.py validate my-skill

# Record a run (for scoring)
python3 skill_bundler.py record my-skill --score 85 --duration 45 --tokens 3200

# Check confidence
python3 skill_bundler.py score my-skill
# {"success_rate": 100.0, "avg_duration": 45.0, "confidence": 0.1}
```

### 4. Ultra Pipeline — The Orchestrator

```python
from ultra_pipeline import UltraPipeline

pipe = UltraPipeline("my-workflow")

# Define → transition state machine
pipe.define_pipeline(metrics=["speed", "accuracy", "cost"])
# State: init → defined

# Validate
pipe.run_tests()
# State: defined → ready (if all skill tests pass)

# Run and auto-evaluate
result = pipe.run(mode="test")
# State: ready → running → evaluating → comparing → [applied|iterating]
```

**State machine:** init → defined → ready → running → evaluating → comparing → iterating → applied (with failure/recovery paths)

---

## Unified CLI

```bash
# DAG management
python3 ultra.py dag new "session-label"
python3 ultra.py dag add plan "What to investigate"
python3 ultra.py dag show                    # tree view
python3 ultra.py dag export compact          # LLM-ready format
python3 ultra.py dag compress 2              # L2 compression

# Pipeline evaluation
python3 ultra.py eval define my-pipe --metrics speed,coverage,cost
python3 ultra.py eval hypothesize my-pipe "DAG compression saves tokens"
python3 ultra.py eval status                 # list all pipelines
python3 ultra.py eval report my-pipe         # detailed report

# Skill bundling
python3 ultra.py bundle init my-skill "Description"
python3 ultra.py bundle validate my-skill
python3 ultra.py bundle list
python3 ultra.py bundle export my-skill --output /tmp/bundle.json

# Full orchestration
python3 ultra.py run init my-pipeline
python3 ultra.py run test my-pipeline
python3 ultra.py run go my-pipeline --mode test
```

---

## Research Foundations

### MUSE-Style Context Compression

Inspired by [MUSE-AutoSkill (arXiv 2605.27366)](https://arxiv.org/abs/2605.27366):

> Instead of treating reasoning history as linear text, model it as a **Directed Acyclic Graph (DAG)** where nodes are reasoning turns and branches are alternative approaches. Two-level adaptive compression keeps token budgets under control while preserving causal structure.

**Key result:** 71K → 56K (Level 1) → **42K** (Level 2) tokens — within 50K budget.

### Scientific Method for Optimization

Inspired by [01 Systems' Self-Improving Agent](https://skool.com/zero-one):

> Change one variable. Test against baseline. If better, becomes new baseline. Repeat indefinitely. Never change multiple variables at once — you won't know which one caused the improvement.

### Discrete State Machine Over Fuzzy CoT

Inspired by [UserHarness ToM (arXiv 2026)](https://github.com/):

> Genuine machine mentalizing is not an emergent property of parameter scale — it is a **structural consequence of externalized epistemic boundaries**. By externalizing state into discrete transitions, a 14B parameter model matches Opus 4.7 accuracy using 10x fewer tokens.

### Per-Skill Memory Architecture

Inspired by MUSE-AutoSkill's skill bundles and [Kitten TTS](https://github.com/zedarvates/kitten-tts)'s memory system:

> Each skill carries three memory tiers:
> - **Long-term:** Cross-session persistent knowledge, discovered patterns, known pitfalls
> - **Mid-term:** Per-session context, current objective, session notes
> - **Short-term:** Per-run variables, intermediate results (resets each run)

---

## Roadmap

- [ ] DAG-Context: Integration with Hermes Agent session DB (auto-log reasoning nodes)
- [ ] DAG-Context: Attention Residuals-style selective retrieval (access old states directly)
- [ ] Pipeline: Web dashboard for real-time pipeline monitoring
- [ ] Pipeline: Auto-generate hypotheses from historical run deltas
- [ ] Skill Bundler: Cross-agent skill export/import (JSON portable format)
- [ ] Skill Bundler: Auto-generate skill bundles from existing SKILL.md files
- [ ] Ultra: Integration with cron jobs ( DAG context + scoring for each cron execution)
- [ ] Ultra: Multi-worker fan-out with result aggregation
- [ ] Ultra: Long-running workflow mode (days, not minutes)

## License

MIT — Do whatever you want. Build something beautiful.

## By

Built by [Hermes Agent / zedarvates](https://github.com/zedarvates) for the [NexRealm](https://github.com/zedarvates) ecosystem.
96% of the design insights come from open research — we're just connecting the dots and shipping code.

---

## Related Projects

- [hermes-brain](https://github.com/zedarvates/hermes-brain) — Architecture cognitive Hermes
- [cogniarc](https://github.com/zedarvates/cogniarc) — ARC-AGI-3 solver
- [hermes-feedback](https://github.com/zedarvates/hermes-feedback) — Feedback system
- [kitten-tts](https://github.com/zedarvates/kitten-tts) — TTS local FR
- [FoveaCore](https://github.com/zedarvates/FoveaCore) — VR rendering engine

*"The skill encodes task structure and workflow — not model-specific behavior."*
— MUSE-AutoSkill transfer experiment conclusion
