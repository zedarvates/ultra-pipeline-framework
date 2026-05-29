#!/usr/bin/env python3
"""
Self-Evaluating Pipeline Framework

Inspire du Trading Agent self-improving (Lewis Jackson) et
de UserHarness (state machine discrete).

Chaque run de pipeline est un EXPERIENCE SCIENTIFIQUE:
  1. Hypotheses (quoi tester)
  2. Execution (run le pipeline)
  3. Scoring (metric numerique objectif)
  4. Comparaison (vs baseline)
  5. Iteration (une seule variable changee)

Scoring:
  - Chaque run produit un score ∈ [0, 100]
  - Les metric sont declarees en YAML (pas hardcode)
  - La baseline se met a jour auto quand un score depasse

Hypotheses:
  - Stockees en JSON, versionnees
  - Une seule variable modifiee par test
  - Read-only mode par defaut (pas de changement live)

Optimisation token:
  - Les runs sont compacts (DAG compression)
  - Seul le delta par rapport a la baseline est rapporte
  
Usage:
  # Definir un pipeline
  python3 pipeline.py define check-up --metrics speed,coverage,cost
  
  # Creer une hypothese
  python3 pipeline.py hypothesize check-up "Compression L2 reduit les tokens de 30%"
  
  # Run en mode test (read-only)
  python3 pipeline.py run check-up --hypothesis <id> --mode test
  
  # Comparer avec baseline
  python3 pipeline.py compare check-up
  
  # Activer le meilleur parametre
  python3 pipeline.py apply check-up --hypothesis <id>
  
  # Voir l historique des scores
  python3 pipeline.py history check-up
"""

import json, os, sys, hashlib, time, shutil
from datetime import datetime
from pathlib import Path

HOME = Path.home()
STORE = HOME / ".hermes" / "ultra" / "pipelines"

# ── Data Models ──────────────────────────────────────────

def new_pipeline(name, metrics=None):
    """Cree une definition de pipeline"""
    return {
        "name": name,
        "created": datetime.utcnow().isoformat(),
        "metrics": metrics or ["speed", "coverage", "cost"],
        "baseline": None,
        "best_run": None,
        "hypotheses": [],
        "runs": [],
        "mode": "test",  # test | live
        "version": 1,
    }

def new_hypothesis(pipeline_name, description, variable, expected_delta):
    """Cree une hypothese testable"""
    hid = hashlib.sha256(f"{description}{time.time()}".encode()).hexdigest()[:12]
    return {
        "id": hid,
        "pipeline": pipeline_name,
        "description": description,
        "variable": variable,       # quel parametre change
        "expected_delta": expected_delta,  # +30%, -15%, etc.
        "status": "pending",        # pending | testing | confirmed | rejected | applied
        "created": datetime.utcnow().isoformat(),
        "test_run": None,
        "score": None,
    }

def new_run(pipeline, hypothesis_id, mode="test"):
    """Enregistre un run de pipeline"""
    rid = hashlib.sha256(f"{pipeline}{time.time()}".encode()).hexdigest()[:16]
    return {
        "id": rid,
        "pipeline": pipeline,
        "hypothesis": hypothesis_id,
        "mode": mode,
        "started": datetime.utcnow().isoformat(),
        "finished": None,
        "scores": {},
        "total_score": 0,
        "delta_vs_baseline": 0,
        "variables": {},
        "logs": [],
    }

# ── Scoring Engine ───────────────────────────────────────

def compute_score(run, metrics_config):
    """
    Calcule le score d'un run base sur les metric declarees.
    
    metrics_config format:
    {
      "speed": {"weight": 0.4, "target": "min", "scale": "seconds"},
      "coverage": {"weight": 0.3, "target": "max", "scale": "percent"},
      "cost": {"weight": 0.3, "target": "min", "scale": "tokens"}
    }
    """
    total = 0
    for metric_name, config in metrics_config.items():
        value = run["scores"].get(metric_name, 0)
        weight = config.get("weight", 1.0 / len(metrics_config))
        
        # Normaliser (simplifie: plus petit = mieux sauf si target=max)
        if config.get("target") == "max":
            normalized = min(value / 100, 1.0) if value <= 100 else 1.0
        else:
            normalized = max(0, 1.0 - (value / 100))
        
        total += normalized * weight * 100
    
    run["total_score"] = round(total, 2)
    return run["total_score"]

def compare_to_baseline(run, baseline):
    """Compare un run a la baseline"""
    if not baseline or not baseline.get("total_score"):
        return {"delta": 0, "improvement": None}
    
    delta = run["total_score"] - baseline["total_score"]
    run["delta_vs_baseline"] = round(delta, 2)
    
    return {
        "delta": round(delta, 2),
        "improvement": delta > 0,
        "percent_change": round((delta / max(baseline["total_score"], 1)) * 100, 1),
    }

# ── Persistence ──────────────────────────────────────────

def init_store():
    STORE.mkdir(parents=True, exist_ok=True)

def pipeline_path(name):
    return STORE / f"{name}.json"

def save_pipeline(p):
    pipeline_path(p["name"]).write_text(json.dumps(p, indent=2))

def load_pipeline(name):
    path = pipeline_path(name)
    if not path.exists():
        return None
    return json.loads(path.read_text())

def list_pipelines():
    pipelines = []
    for f in STORE.glob("*.json"):
        if f.stem not in ("index", "config"):
            try:
                p = json.loads(f.read_text())
                pipelines.append(p)
            except:
                pass
    return pipelines

# ── Hypothesis Manager ──────────────────────────────────

def add_hypothesis(pipeline_name, description, variable, expected_delta):
    p = load_pipeline(pipeline_name)
    if not p:
        print(f"Pipeline '{pipeline_name}' not found")
        return None
    
    h = new_hypothesis(pipeline_name, description, variable, expected_delta)
    p["hypotheses"].append(h)
    save_pipeline(p)
    return h

def confirm_hypothesis(pipeline_name, hypothesis_id, run_score):
    """Une hypothese est confirmee si le score s'ameliore"""
    p = load_pipeline(pipeline_name)
    if not p:
        return None
    
    for h in p["hypotheses"]:
        if h["id"] == hypothesis_id:
            h["score"] = run_score
            h["status"] = "confirmed" if run_score > (p["baseline"]["total_score"] if p["baseline"] else 0) else "rejected"
            save_pipeline(p)
            return h
    return None

def apply_hypothesis(pipeline_name, hypothesis_id):
    """Applique l'hypothese confirmee comme nouvelle baseline"""
    p = load_pipeline(pipeline_name)
    if not p:
        return None
    
    for h in p["hypotheses"]:
        if h["id"] == hypothesis_id and h["status"] == "confirmed":
            # Trouver le run correspondant
            for r in p["runs"]:
                if r["hypothesis"] == hypothesis_id:
                    p["baseline"] = r
                    h["status"] = "applied"
                    h["applied_at"] = datetime.utcnow().isoformat()
                    save_pipeline(p)
                    return h
    return None

# ── Run Logger ──────────────────────────────────────────

def log_run(pipeline_name, run_data):
    """Enregistre un run dans l historique"""
    p = load_pipeline(pipeline_name)
    if not p:
        return None
    
    p["runs"].append(run_data)
    
    # Mettre a jour le best run
    if not p["best_run"] or run_data["total_score"] > p["best_run"].get("total_score", 0):
        p["best_run"] = run_data
    
    save_pipeline(p)
    return run_data

def get_history(pipeline_name):
    """Retourne l historique des runs"""
    p = load_pipeline(pipeline_name)
    if not p:
        return []
    
    runs = sorted(p["runs"], key=lambda r: r.get("started", ""))
    return runs

# ── Report Generator ─────────────────────────────────────

def generate_report(pipeline_name):
    """Genere un rapport compact du pipeline"""
    p = load_pipeline(pipeline_name)
    if not p:
        return f"Pipeline '{pipeline_name}' not found"
    
    lines = [
        f"# Pipeline: {p['name']}",
        f"Created: {p['created'][:19]} | Mode: {p['mode']} | Version: {p['version']}",
        f"Metrics: {', '.join(p['metrics'])}",
        "",
    ]
    
    # Baseline
    if p["baseline"]:
        b = p["baseline"]
        lines.append(f"## Baseline (score: {b.get('total_score', '?')})")
        lines.append(f"  Run: {b['id'][:8]}… | Mode: {b.get('mode', '?')}")
        for m, v in b.get("scores", {}).items():
            lines.append(f"  {m}: {v}")
    else:
        lines.append("## No baseline yet")
    
    lines.append("")
    
    # Hypotheses
    lines.append(f"## Hypotheses ({len(p['hypotheses'])})")
    for h in p["hypotheses"]:
        status_icon = {
            "pending": "⏳", "testing": "🧪", "confirmed": "✅",
            "rejected": "❌", "applied": "🚀"
        }.get(h["status"], "?")
        lines.append(f"  {status_icon} [{h['id'][:8]}] {h['variable']}: {h['description'][:60]}")
    
    lines.append("")
    
    # Runs
    lines.append(f"## Runs ({len(p['runs'])})")
    for r in sorted(p["runs"], key=lambda x: x.get("started", ""))[-5:]:  # 5 derniers
        delta = r.get("delta_vs_baseline", 0)
        delta_str = f"+{delta}" if delta > 0 else str(delta)
        lines.append(f"  {r['id'][:8]}… score={r.get('total_score', '?')} ({delta_str}) mode={r.get('mode', '?')}")
    
    return "\n".join(lines)

# ── Mode Flip (test → live) ─────────────────────────────

def set_mode(pipeline_name, mode):
    """Change le mode du pipeline (test ou live)"""
    if mode not in ("test", "live"):
        print("Mode must be 'test' or 'live'")
        return False
    
    p = load_pipeline(pipeline_name)
    if not p:
        return False
    
    p["mode"] = mode
    p["version"] += 1
    save_pipeline(p)
    return True

# ── CLI ─────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    
    cmd = sys.argv[1]
    init_store()
    
    if cmd == "define":
        name = sys.argv[2] if len(sys.argv) > 2 else "unnamed"
        if "--metrics" in sys.argv:
            idx = sys.argv.index("--metrics")
            metrics = sys.argv[idx + 1].split(",") if len(sys.argv) > idx + 1 else ["speed", "coverage", "cost"]
        else:
            metrics = ["speed", "coverage", "cost"]
        p = new_pipeline(name, metrics)
        save_pipeline(p)
        print(json.dumps(p, indent=2))
    
    elif cmd == "hypothesize":
        pipeline = sys.argv[2]
        desc = " ".join(sys.argv[3:]) if len(sys.argv) > 3 else ""
        if not desc:
            print("Usage: pipeline.py hypothesize <pipeline> <description>")
            return
        parts = desc.rsplit(" ", 2)
        variable = parts[0] if len(parts) >= 2 else "general"
        delta = parts[-1] if len(parts) >= 3 else "unknown"
        h = add_hypothesis(pipeline, desc, variable, delta)
        if h:
            print(json.dumps(h, indent=2))
    
    elif cmd == "status":
        pipeline = sys.argv[2] if len(sys.argv) > 2 else None
        if pipeline:
            print(generate_report(pipeline))
        else:
            for p in list_pipelines():
                runs = len(p.get("runs", []))
                best = p.get("best_run")
                print(f"  {p['name']:20s} runs={runs} mode={p.get('mode','?')} best={best.get('total_score','?') if best else 'none'}")
    
    elif cmd == "list":
        for p in list_pipelines():
            print(f"  {p['name']:20s} metrics={','.join(p['metrics'])}")
    
    elif cmd == "setmode":
        if len(sys.argv) < 4:
            print("Usage: pipeline.py setmode <pipeline> <test|live>")
            return
        if set_mode(sys.argv[2], sys.argv[3]):
            print(f"Mode set to: {sys.argv[3]}")
    
    elif cmd == "report":
        pipeline = sys.argv[2] if len(sys.argv) > 2 else None
        if not pipeline:
            print("Usage: pipeline.py report <pipeline>")
            return
        print(generate_report(pipeline))
    
    elif cmd == "hypotheses":
        pipeline = sys.argv[2] if len(sys.argv) > 2 else None
        if not pipeline:
            print("Usage: pipeline.py hypotheses <pipeline>")
            return
        p = load_pipeline(pipeline)
        if not p:
            print(f"Pipeline '{pipeline}' not found")
            return
        for h in p.get("hypotheses", []):
            print(json.dumps(h, indent=2))
    
    elif cmd == "runs":
        pipeline = sys.argv[2] if len(sys.argv) > 2 else None
        if not pipeline:
            print("Usage: pipeline.py runs <pipeline>")
            return
        runs = get_history(pipeline)
        for r in runs[-10:]:
            print(f"  {r['id'][:8]}… score={r.get('total_score','?')} delta={r.get('delta_vs_baseline','?')} mode={r.get('mode','?')}")

if __name__ == "__main__":
    main()
