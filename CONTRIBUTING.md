# Contributing to Ultra Pipeline Framework

Welcome! This is an open research project — your insights, even small ones, make it better.

## Quick Setup

```bash
git clone https://github.com/zedarvates/ultra-pipeline-framework.git
cd ultra-pipeline-framework
python3 example_checkup.py  # verify everything works
```

## How to Contribute

### Bugs & Issues
Open a GitHub issue with:
- What you expected
- What happened instead
- Steps to reproduce

### Features & Ideas
Before coding, open an issue to discuss. This is a research-driven project — we want to understand the *why* behind every feature.

### Pull Requests
1. Fork → branch → change → PR
2. Include tests (GitHub Actions runs on every PR)
3. Update README.md if adding new functionality
4. Keep modules **independent** — no cross-module imports

## Code Style

- Python 3.10+
- No external dependencies (stdlib only for core modules)
- Document functions with docstrings
- Use type hints where practical

## Architecture Principles

1. **State is externalized** — JSON files, not Python variables
2. **One module = one concern** — don't merge DAG + Pipeline + Bundler
3. **Scientific method** — measurable, testable, comparable
4. **Token-conscious** — minimize context, maximize signal

## Research References

Every major feature should cite its inspiration:
- MUSE-AutoSkill: arXiv 2605.27366
- UserHarness: UIUC (Cheng Qian et al.)
- Attention Residuals: Kimi/Moonshot arXiv 2603.15031
- Self-Improving Agent: 01 Systems (Lewis Jackson)
- LeJEPA: Yann LeCun et al.
