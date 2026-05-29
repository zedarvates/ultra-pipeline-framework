"""
Example: Using Ultra Pipeline Framework for a self-improving check-up workflow.

This demonstrates all four modules working together:
1. DAG-Context: Track reasoning as nodes
2. Self-Eval: Score each run against baseline
3. Skill Bundler: Wrap check-up logic as a testable bundle
4. Ultra Pipeline: Orchestrate the full scientific loop
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from dag_context import (
    new_session, add_node, compress_dag, 
    export_dag, get_stats
)
from self_eval_pipeline import (
    new_pipeline, save_pipeline, new_hypothesis, 
    new_run, compute_score, compare_to_baseline, 
    log_run, add_hypothesis, apply_hypothesis,
    load_pipeline, generate_report, set_mode
)
from skill_bundler import (
    create_bundle, validate_bundle, record_run as record_skill_run
)

EXAMPLE_METRICS = {
    "speed": {"weight": 0.3, "target": "min", "scale": "seconds"},
    "coverage": {"weight": 0.3, "target": "max", "scale": "percent"},
    "cost": {"weight": 0.2, "target": "min", "scale": "tokens"},
    "reliability": {"weight": 0.2, "target": "max", "scale": "percent"},
}


def stage_1_dag_context():
    """Step 1: Use DAG-Context Manager to track reasoning"""
    print("=" * 60)
    print("STAGE 1: DAG-Context Manager")
    print("=" * 60)
    
    # Start a session for cluster check-up
    session = new_session("cluster-check-up")
    print(f"Session created: {session['id'][:8]}…")
    
    # Log reasoning steps
    add_node("plan", "Check cluster health post-Windows-reboot")
    add_node("action", "Ping EUREKAI .47 and .66", tool="ping", cost=10)
    add_node("observation", "SSH OK on both, Qdrant has 19 collections")
    add_node("action", "Check Home Assistant", tool="curl", cost=5)
    add_node("observation", "HA unreachable — needs Windows restart")
    add_node("decision", "Flag HA for manual restart, others OK")
    
    # Show the tree
    print("\n" + export_dag(fmt="tree"))
    
    # Stats
    stats = get_stats()
    print(f"\nStats: {stats['total_nodes']} nodes, {stats['total_cost']} tokens")
    
    return session


def stage_2_self_eval_pipeline():
    """Step 2: Define a self-evaluating pipeline"""
    print("\n" + "=" * 60)
    print("STAGE 2: Self-Evaluating Pipeline")
    print("=" * 60)
    
    # Define pipeline
    pipeline = new_pipeline("cluster-checkup", 
                           metrics=["speed", "coverage", "cost", "reliability"])
    save_pipeline(pipeline)
    print(f"Pipeline '{pipeline['name']}' defined")
    
    # Form hypothesis
    h = add_hypothesis("cluster-checkup",
        "DAG compression reduces context tokens by 30%",
        "context_compression", "-30%")
    print(f"Hypothesis created: {h['id'][:8]}…")
    print(f"  Variable: {h['variable']}")
    print(f"  Expected: {h['expected_delta']}")
    
    # Simulate a run
    run = new_run("cluster-checkup", h["id"], mode="test")
    run["scores"] = {"speed": 78, "coverage": 92, "cost": 85, "reliability": 90}
    compute_score(run, EXAMPLE_METRICS)
    log_run("cluster-checkup", run)
    print(f"\nRun completed: score={run['total_score']}")
    
    # First run becomes baseline
    p = load_pipeline("cluster-checkup")
    print(f"\n{p['name']}: {len(p['runs'])} runs, "
          f"baseline={'set' if p['baseline'] else 'none'}")
    
    return h["id"]


def stage_3_skill_bundler():
    """Step 3: Create a skill bundle"""
    print("\n" + "=" * 60)
    print("STAGE 3: Skill Bundler 2.0")
    print("=" * 60)
    
    # Create bundle (skip if exists from prior run)
    from pathlib import Path
    if Path(f"ultra/skill_bundles/cluster-checkup").exists():
        meta = {"name": "cluster-checkup"}  # reuse existing
        print(f"Bundle already exists: {meta['name']}")
    else:
        meta = create_bundle("cluster-checkup", 
                            "Automatic cluster health diagnostic")
        print(f"Bundle created: {meta['name']}")
    
    # Validate
    success = validate_bundle("cluster-checkup")
    print(f"Validation: {'PASS' if success else 'FAIL'}")
    
    # Record runs
    record_skill_run("cluster-checkup", score=88, duration=42, tokens=3100)
    record_skill_run("cluster-checkup", score=91, duration=38, tokens=2900)
    
    # Check score
    meta = load_pipeline("cluster-checkup")
    # Get score from skill bundler
    bundles = __import__('skill_bundler', fromlist=['list_bundles']).list_bundles()
    if bundles:
        score = bundles[0].get("score", {})
        print(f"\nScore after 2 runs:")
        print(f"  Success rate: {score.get('success_rate', 0)}%")
        print(f"  Avg duration: {score.get('avg_duration', 0)}s")
        print(f"  Confidence: {score.get('confidence', 0)}")
    
    return meta


def stage_4_full_pipeline(hypothesis_id):
    """Step 4: Run the full ultra pipeline"""
    print("\n" + "=" * 60)
    print("STAGE 4: Ultra Pipeline (Full)")
    print("=" * 60)
    
    from ultra_pipeline import UltraPipeline
    
    pipe = UltraPipeline("cluster-checkup")
    
    # Skip define (already done), go to tests
    pipe.state = "defined"  # already defined in stage 2
    pipe.pipeline_def = load_pipeline("cluster-checkup")
    
    # Run
    print(f"Running pipeline (mode=test)...")
    result = pipe.run(mode="test", hypothesis_id=hypothesis_id)
    
    print(f"\nRun result:")
    print(f"  Score: {result.get('total_score', '?')}")
    print(f"  Delta vs baseline: {result.get('delta_vs_baseline', '?')}")
    print(f"  State: {pipe.state}")
    
    # Final report
    print("\n" + "=" * 60)
    print("FINAL REPORT")
    print("=" * 60)
    print(generate_report("cluster-checkup"))


if __name__ == "__main__":
    session = stage_1_dag_context()
    hypothesis_id = stage_2_self_eval_pipeline()
    bundle_meta = stage_3_skill_bundler()
    stage_4_full_pipeline(hypothesis_id)
    
    print("\n" + "=" * 60)
    print("ALL STAGES COMPLETE")
    print("=" * 60)
    print("\nThe Ultra Pipeline Framework is ready for production use.")
