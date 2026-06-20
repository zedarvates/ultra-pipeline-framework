#!/usr/bin/env python3
"""
Ultra Pipeline — Hermes Cron Adapter
Transforme les cron jobs Hermes en pipelines Ultra auto-évalués.

Usage:
  python3 hermes_cron_adapter.py --job-id <id>          # Wrap single cron job
  python3 hermes_cron_adapter.py --sync-all              # Sync all active cron jobs
  python3 hermes_cron_adapter.py --list-pipelines        # List existing pipelines
"""
import argparse, json, subprocess, sys, os, datetime, re
from pathlib import Path
from typing import Optional, List, Dict

HERMES_CRON_FILE = Path.home() / ".hermes" / "cron" / "jobs.json"
PIPELINES_DIR = Path.home() / ".hermes" / "pipelines"

# ── Hermes Cron Parser ───────────────────────────────────────

def load_hermes_cron() -> dict:
    """Load Hermes cron jobs.json"""
    if not HERMES_CRON_FILE.exists():
        # Try to get from hermes CLI
        result = subprocess.run(
            ["hermes", "cron", "list", "--json"],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
        return {}
    return json.loads(HERMES_CRON_FILE.read_text())

def classify_job(job: dict) -> str:
    """Classify a cron job into a pipeline type"""
    name = job.get("name", "").lower()
    if any(w in name for w in ["health", "check", "supervision", "gardien"]):
        return "monitoring"
    if any(w in name for w in ["backup", "sync", "cleanup"]):
        return "maintenance"
    if any(w in name for w in ["rd", "recherche", "veille", "research"]):
        return "research"
    if any(w in name for w in ["skill", "amelioration", "improve"]):
        return "improvement"
    if any(w in name for w in ["briefing", "rapport", "report", "email"]):
        return "reporting"
    if any(w in name for w in ["osint", "seo", "community"]):
        return "outreach"
    return "general"

def job_to_pipeline(job: dict) -> dict:
    """Convert a Hermes cron job to an Ultra Pipeline manifest"""
    job_id = job.get("id", "unknown")
    name = job.get("name", "unnamed")
    schedule = job.get("schedule", "unknown")
    pipeline_type = classify_job(job)
    
    return {
        "pipeline_id": f"cron-{job_id[:8]}",
        "name": name,
        "source": "hermes-cron",
        "cron_job_id": job_id,
        "cron_schedule": schedule,
        "type": pipeline_type,
        "state": "defined",
        "created": datetime.datetime.now().isoformat()[:19],
        "metrics": default_metrics(pipeline_type),
        "steps": default_steps(pipeline_type, name),
        "tags": ["cron", pipeline_type],
    }

def default_metrics(pipeline_type: str) -> List[str]:
    metrics = {
        "monitoring": ["uptime", "services_up", "disk_percent", "gpu_temp"],
        "maintenance": ["bytes_synced", "files_pruned", "duration_seconds"],
        "research": ["papers_found", "summaries_generated", "relevance_score"],
        "improvement": ["skills_updated", "score_delta", "tokens_saved"],
        "reporting": ["sections_generated", "delivery_ok"],
        "outreach": ["posts_created", "engagement_score"],
        "general": ["success", "duration_seconds", "tokens_used"],
    }
    return metrics.get(pipeline_type, metrics["general"])

def default_steps(pipeline_type: str, name: str) -> List[dict]:
    steps = {
        "monitoring": [
            {"name": "check_endpoints", "timeout": 30},
            {"name": "verify_services", "timeout": 30},
            {"name": "log_results", "timeout": 10},
        ],
        "maintenance": [
            {"name": "prepare", "timeout": 30},
            {"name": "execute_sync", "timeout": 300},
            {"name": "verify", "timeout": 30},
        ],
        "research": [
            {"name": "collect_sources", "timeout": 60},
            {"name": "extract_content", "timeout": 120},
            {"name": "summarize", "timeout": 60},
            {"name": "store_results", "timeout": 30},
        ],
        "general": [
            {"name": "initialize", "timeout": 15},
            {"name": "execute_task", "timeout": 120},
            {"name": "finalize", "timeout": 15},
        ],
    }
    return steps.get(pipeline_type, steps["general"])

# ── Pipeline Manager ─────────────────────────────────────────

def ensure_pipelines_dir():
    PIPELINES_DIR.mkdir(parents=True, exist_ok=True)

def save_pipeline(pipeline: dict):
    path = PIPELINES_DIR / f"{pipeline['pipeline_id']}.json"
    path.write_text(json.dumps(pipeline, indent=2))
    print(f"  ✅ Pipeline saved: {path.name}")

def list_pipelines():
    if not PIPELINES_DIR.exists():
        print("  No pipelines yet")
        return
    
    pipelines = sorted(PIPELINES_DIR.glob("*.json"))
    print(f"\n  📋 Ultra Pipelines ({len(pipelines)}):\n")
    for p in pipelines:
        data = json.loads(p.read_text())
        state_icon = {
            "defined": "📝", "ready": "🔵", "running": "🔄",
            "evaluating": "📊", "completed": "✅", "failed": "❌"
        }.get(data.get("state", ""), "❓")
        print(f"  {state_icon} {data.get('name', '?')} [{data.get('pipeline_id', '?')}]")
        print(f"     Type: {data.get('type', '?')} | State: {data.get('state', '?')}")
        print(f"     Created: {data.get('created', '?')}")
        print()

def sync_all_cron():
    """Sync all active Hermes cron jobs to Ultra Pipelines"""
    ensure_pipelines_dir()
    
    jobs_data = load_hermes_cron()
    
    # Handle both JSON array and object formats
    if isinstance(jobs_data, list):
        jobs = jobs_data
    elif isinstance(jobs_data, dict):
        jobs = jobs_data.get("jobs", jobs_data.get("data", []))
        if isinstance(jobs, dict):
            jobs = list(jobs.values())
    else:
        jobs = []
    
    print(f"  📡 Found {len(jobs)} cron jobs")
    
    synced = 0
    for job in jobs:
        if not isinstance(job, dict):
            continue
        if job.get("status") == "paused":
            continue
        
        pipeline = job_to_pipeline(job)
        save_pipeline(pipeline)
        synced += 1
    
    print(f"\n  ✅ Synced {synced} jobs to pipelines in {PIPELINES_DIR}")

def create_job_pipeline(job_id: str):
    """Create pipeline for a specific cron job"""
    jobs_data = load_hermes_cron()
    
    if isinstance(jobs_data, list):
        jobs = jobs_data
    elif isinstance(jobs_data, dict):
        jobs = jobs_data.get("jobs", jobs_data.get("data", []))
        if isinstance(jobs, dict):
            jobs = list(jobs.values())
    else:
        jobs = []
    
    for job in jobs:
        if isinstance(job, dict) and job.get("id") == job_id:
            ensure_pipelines_dir()
            pipeline = job_to_pipeline(job)
            save_pipeline(pipeline)
            return
    
    print(f"  ❌ Job {job_id} not found")

# ── Main ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Ultra Pipeline — Hermes Cron Adapter"
    )
    parser.add_argument("--job-id", help="Create pipeline for specific cron job")
    parser.add_argument("--sync-all", action="store_true", help="Sync all active cron jobs")
    parser.add_argument("--list-pipelines", action="store_true", help="List existing pipelines")
    
    args = parser.parse_args()
    
    if args.list_pipelines:
        list_pipelines()
    elif args.sync_all:
        sync_all_cron()
    elif args.job_id:
        create_job_pipeline(args.job_id)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
