#!/usr/bin/env python3
"""
Ultra Pipeline — Chef d'Orchestre Unifie

Combine:
  A) DAG-Context Manager — raisonnement = graphe compressible
  B) Self-Evaluating Pipeline — scoring + hypotheses + iterate
  C) Skill Bundler 2.0 — skills executables avec tests/memory

Ce n'est pas juste un script — c'est un ORCHESTRATEUR
qui peut tourner pendant des jours avec des sous-agents.

Architecture (inspiree UserHarness + Opus 4.8 Ultra-Code):

  ┌──────────────────────────────────────────────┐
  │           ULTRA PIPELINE ORCHESTRATOR        │
  │                                              │
  │  ┌─────────┐  ┌──────────┐  ┌────────────┐  │
  │  │DAG      │  │Self-Eval │  │Skill       │  │
  │  │Context  │◄─┤Pipeline  │◄─┤Bundler 2.0 │  │
  │  │Manager  │  │Framework │  │            │  │
  │  └────┬────┘  └────┬─────┘  └─────┬──────┘  │
  │       │            │              │          │
  │  ┌────▼────────────▼──────────────▼──────┐   │
  │  │         STATE MACHINE                 │   │
  │  │  (discrete transitions, externalise)  │   │
  │  └─────────────────┬────────────────────┘   │
  │                    │                         │
  │  ┌─────────────────▼────────────────────┐   │
  │  │      FAN-OUT CONTROLLER              │   │
  │  │  (jusqu'a N workers paralleles)      │   │
  │  └──────────────────────────────────────┘   │
  └──────────────────────────────────────────────┘

Principes:
1. L'etat est EXTERNALISE dans des fichiers JSON
   (pas de CoT, pas de chain-of-thought diffus)
2. Chaque transition = une action discrete avec pre/post conditions
3. Les skills sont des bundles executables et testables
4. Le scoring est AUTOMATIQUE et NUMERIQUE
5. La compression DAG preserve la causalite

Workflow par defaut:
  Define → Hypothesize → Test → Score → Compare → Iterate → Apply

Usage:
  # Definir un pipeline ultra
  python3 ultra_pipeline.py init mon_pipeline --metrics speed,coverage,cost
  
  # Ajouter une etape
  python3 ultra_pipeline.py step mon_pipeline --name "check-up" --skill cluster-resilience
  
  # Run complet
  python3 ultra_pipeline.py run mon_pipeline --mode test
  
  # Suivi en temps reel
  python3 ultra_pipeline.py watch mon_pipeline
  
  # Rapport
  python3 ultra_pipeline.py report mon_pipeline
"""

import json, os, sys, hashlib, subprocess, time, threading
from datetime import datetime
from pathlib import Path

# ── Imports locaux ──────────────────────────────────────
ULTRA_DIR = Path(__file__).parent
sys.path.insert(0, str(ULTRA_DIR))

from dag_context import (
    new_session, add_node, compress_dag, export_dag, get_stats,
    get_active_session, load_session_nodes
)
from self_eval_pipeline import (
    new_pipeline, load_pipeline, save_pipeline, new_hypothesis,
    new_run, compute_score, compare_to_baseline, log_run,
    add_hypothesis, apply_hypothesis, generate_report, set_mode
)
from skill_bundler import (
    create_bundle, validate_bundle, record_run as record_skill_run,
    get_bundle_score, list_bundles, read_memory, append_memory
)

# ── Ultra Pipeline State Machine ────────────────────────
# Inspire de UserHarness — transitions d'etat discretes

STATE_INIT = "init"
STATE_DEFINED = "defined"
STATE_READY = "ready"          # tests passes
STATE_RUNNING = "running"
STATE_EVALUATING = "evaluating"
STATE_COMPARING = "comparing"
STATE_ITERATING = "iterating"
STATE_APPLIED = "applied"      # nouvelle baseline
STATE_FAILED = "failed"

VALID_TRANSITIONS = {
    STATE_INIT: [STATE_DEFINED],
    STATE_DEFINED: [STATE_READY, STATE_FAILED],
    STATE_READY: [STATE_RUNNING],
    STATE_RUNNING: [STATE_EVALUATING, STATE_FAILED],
    STATE_EVALUATING: [STATE_COMPARING],
    STATE_COMPARING: [STATE_ITERATING, STATE_APPLIED, STATE_FAILED],
    STATE_ITERATING: [STATE_RUNNING],  # boucle
    STATE_APPLIED: [STATE_READY],      # pret pour le prochain run
    STATE_FAILED: [STATE_ITERATING, STATE_READY],
}

class UltraPipeline:
    """Orchestrateur de pipeline"""
    
    def __init__(self, name):
        self.name = name
        self.state = STATE_INIT
        self.state_file = ULTRA_DIR / "runs" / f"{name}_state.json"
        self.runs_dir = ULTRA_DIR / "runs" / name
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.dag_session = None
        self.pipeline_def = None
        self.current_run = None
    
    def save_state(self):
        state = {
            "name": self.name,
            "state": self.state,
            "updated": datetime.utcnow().isoformat(),
            "dag_session": self.dag_session["id"] if self.dag_session else None,
            "pipeline": self.pipeline_def["name"] if self.pipeline_def else None,
            "current_run": self.current_run["id"] if self.current_run else None,
        }
        self.state_file.write_text(json.dumps(state, indent=2))
    
    def load_state(self):
        if not self.state_file.exists():
            return False
        state = json.loads(self.state_file.read_text())
        self.state = state["state"]
        if state.get("dag_session"):
            # restaurer la session DAG
            pass  # TODO: restaurer depuis session ID
        return True
    
    def transition(self, new_state):
        if new_state not in VALID_TRANSITIONS.get(self.state, []):
            raise ValueError(
                f"Invalid transition: {self.state} → {new_state} "
                f"(valid: {VALID_TRANSITIONS.get(self.state, [])})")
        
        old_state = self.state
        self.state = new_state
        self.save_state()
        
        if self.dag_session:
            add_node("decision", f"State transition: {old_state} → {new_state}")
        
        return new_state
    
    def define_pipeline(self, metrics, description=""):
        """Etat: init → defined"""
        assert self.state == STATE_INIT
        
        self.pipeline_def = new_pipeline(self.name, metrics)
        self.pipeline_def["description"] = description
        save_pipeline(self.pipeline_def)
        
        self.dag_session = new_session(f"ultra:{self.name}")
        add_node("plan", f"Pipeline defined: {', '.join(metrics)}")
        
        self.transition(STATE_DEFINED)
        return self.pipeline_def
    
    def run_tests(self):
        """Etat: defined → ready (si tests passent)"""
        assert self.state in (STATE_DEFINED, STATE_READY, STATE_FAILED)
        
        add_node("action", "Running skill bundle tests")
        
        # Valider tous les bundles utilises
        bundles = list_bundles()
        all_pass = True
        for b in bundles:
            name = b["name"]
            success = validate_bundle(name)
            status = "PASS" if success else "FAIL"
            add_node("observation", f"Test {name}: {status}", cost=50)
            if not success:
                all_pass = False
        
        if all_pass:
            self.transition(STATE_READY)
        else:
            self.transition(STATE_FAILED)
        
        return all_pass
    
    def run(self, mode="test", hypothesis_id=None):
        """Etat: ready → running → evaluating → comparing"""
        assert self.state in (STATE_READY, STATE_APPLIED)
        
        self.transition(STATE_RUNNING)
        add_node("action", f"Starting pipeline run (mode={mode})")
        
        # Creer le run
        self.current_run = new_run(self.name, hypothesis_id, mode)
        start_time = time.time()
        
        add_node("plan", f"Run {self.current_run['id'][:8]}… started")
        
        self.transition(STATE_EVALUATING)
        
        # Scoring (exemple avec metric generiques)
        self.current_run["scores"] = {
            "speed": 0,
            "coverage": 0,
            "cost": 0,
        }
        
        self.transition(STATE_COMPARING)
        
        # Comparer a la baseline
        p = load_pipeline(self.name)
        if p and p.get("baseline"):
            comparison = compare_to_baseline(self.current_run, p["baseline"])
            add_node("observation", 
                f"Delta vs baseline: {comparison['delta']} "
                f"({comparison['percent_change']}%)", cost=30)
            
            if comparison["improvement"]:
                add_node("decision", "Improvement detected! Applying...")
                self.transition(STATE_APPLIED)
                if hypothesis_id:
                    apply_hypothesis(self.name, hypothesis_id)
            else:
                add_node("decision", "No improvement. Keeping baseline.")
                self.transition(STATE_ITERATING)
        else:
            # Premier run = baseline
            add_node("observation", "First run — setting as baseline")
            p["baseline"] = self.current_run
            save_pipeline(p)
            self.transition(STATE_APPLIED)
        
        # Enregistrer le run
        duration = time.time() - start_time
        self.current_run["finished"] = datetime.utcnow().isoformat()
        self.current_run["scores"]["speed"] = round(duration, 1)
        log_run(self.name, self.current_run)
        
        # Enregistrer dans le skill bundle
        record_skill_run(self.name, score=self.current_run["total_score"],
                        duration=int(duration))
        
        self.save_state()
        return self.current_run
    
    def get_status(self):
        """Retourne l'etat complet du pipeline"""
        p = load_pipeline(self.name)
        
        return {
            "name": self.name,
            "state": self.state,
            "total_runs": len(p.get("runs", [])) if p else 0,
            "hypotheses": len(p.get("hypotheses", [])) if p else 0,
            "baseline_score": p["baseline"].get("total_score", 0) if p and p.get("baseline") else 0,
            "best_score": p["best_run"].get("total_score", 0) if p and p.get("best_run") else 0,
            "mode": p.get("mode", "?") if p else "?",
        }

# ── Batch Runner (parallele) ───────────────────────────

class BatchRunner:
    """Execute plusieurs runs en parallele (jusqu'a 5 workers)"""
    
    def __init__(self, max_workers=5):
        self.max_workers = max_workers
        self.results = []
    
    def run_batch(self, pipeline_name, configs):
        """
        Execute un batch de configs sur un pipeline.
        configs = [{"hypothesis_id": ..., "mode": "test", "variables": {...}}]
        """
        threads = []
        results = [None] * len(configs)
        
        def worker(idx, config):
            try:
                pipe = UltraPipeline(pipeline_name)
                pipe.load_state()
                run = pipe.run(
                    mode=config.get("mode", "test"),
                    hypothesis_id=config.get("hypothesis_id")
                )
                results[idx] = {"status": "ok", "run": run}
            except Exception as e:
                results[idx] = {"status": "error", "error": str(e)}
        
        for i, config in enumerate(configs):
            if len(threads) >= self.max_workers:
                # Attendre un thread
                for t in threads:
                    t.join(timeout=30)
                threads = [t for t in threads if t.is_alive()]
            
            t = threading.Thread(target=worker, args=(i, config))
            t.start()
            threads.append(t)
        
        # Attendre tous
        for t in threads:
            t.join(timeout=120)
        
        self.results = results
        return results

# ── CLI ─────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    
    cmd = sys.argv[1]
    
    if cmd == "init":
        name = sys.argv[2] if len(sys.argv) > 2 else "unnamed"
        metrics = sys.argv[sys.argv.index("--metrics") + 1].split(",") if "--metrics" in sys.argv else ["speed", "coverage", "cost"]
        pipe = UltraPipeline(name)
        pipe.define_pipeline(metrics)
        print(f"Pipeline '{name}' created. State: {pipe.state}")
    
    elif cmd == "test":
        name = sys.argv[2] if len(sys.argv) > 2 else None
        if not name:
            print("Usage: ultra_pipeline.py test <name>")
            return
        pipe = UltraPipeline(name)
        pipe.load_state()
        ok = pipe.run_tests()
        print(f"Tests: {'ALL PASS' if ok else 'FAILED'}")
    
    elif cmd == "run":
        name = sys.argv[2] if len(sys.argv) > 2 else None
        mode = sys.argv[sys.argv.index("--mode") + 1] if "--mode" in sys.argv else "test"
        hyp_id = sys.argv[sys.argv.index("--hypothesis") + 1] if "--hypothesis" in sys.argv else None
        if not name:
            print("Usage: ultra_pipeline.py run <name> --mode test")
            return
        pipe = UltraPipeline(name)
        pipe.load_state()
        result = pipe.run(mode=mode, hypothesis_id=hyp_id)
        print(json.dumps(result, indent=2))
    
    elif cmd == "status":
        name = sys.argv[2] if len(sys.argv) > 2 else None
        if name:
            pipe = UltraPipeline(name)
            pipe.load_state()
            print(json.dumps(pipe.get_status(), indent=2))
        else:
            # lister tous les pipelines
            for f in sorted(ULTRA_DIR.glob("runs/*_state.json")):
                state = json.loads(f.read_text())
                print(f"  {state['name']:25s} state={state['state']} updated={state['updated'][:19]}")
    
    elif cmd == "report":
        name = sys.argv[2] if len(sys.argv) > 2 else None
        if not name:
            print("Usage: ultra_pipeline.py report <name>")
            return
        print(generate_report(name))
    
    elif cmd == "dag":
        # Export du DAG de la session active
        fmt = sys.argv[2] if len(sys.argv) > 2 else "compact"
        print(export_dag(fmt=fmt))
    
    elif cmd == "compress":
        level = int(sys.argv[2]) if len(sys.argv) > 2 else 2
        nodes = compress_dag(level=level)
        print(f"DAG compressed to {len(nodes) if nodes else 0} nodes")
    
    elif cmd == "batch":
        # Run batch: plusieurs configs en parallele
        name = sys.argv[2] if len(sys.argv) > 2 else None
        if not name:
            print("Usage: ultra_pipeline.py batch <name> --configs '[...]'")
            return
        configs_json = sys.argv[sys.argv.index("--configs") + 1] if "--configs" in sys.argv else "[]"
        configs = json.loads(configs_json)
        runner = BatchRunner(max_workers=5)
        results = runner.run_batch(name, configs)
        print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()
