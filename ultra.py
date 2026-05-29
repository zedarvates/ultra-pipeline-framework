#!/usr/bin/env python3
"""
ultra — CLI unifie du Ultra Pipeline Framework

Point d'entree unique pour tous les outils ultra:
  dag     — DAG Context Manager
  eval    — Self-Evaluating Pipeline
  bundle  — Skill Bundler 2.0
  run     — Ultra Pipeline (chef d'orchestre)

Usage:
  ultra dag new <label>
  ultra dag add <type> <content>
  ultra dag show
  ultra dag export [compact|json|tree]
  ultra dag compress [level] [budget]
  ultra dag stats
  
  ultra eval define <name> [--metrics m1,m2,...]
  ultra eval hypothesize <name> <description>
  ultra eval status [name]
  ultra eval report <name>
  ultra eval setmode <name> <test|live>
  ultra eval runs <name>
  
  ultra bundle init <name> [description]
  ultra bundle validate <name>
  ultra bundle record <name> [--score N] [--duration N] [--tokens N]
  ultra bundle list
  ultra bundle score <name>
  ultra bundle export <name> --output <path>
  ultra bundle memory <name> <level> <read|write|append> [content]
  
  ultra run init <name> [--metrics m1,m2,...]
  ultra run test <name>
  ultra run go <name> [--mode test|live] [--hypothesis <id>]
  ultra run status [name]
  ultra run report <name>
  ultra run dag [compact|json|tree]
  ultra run compress [level]
"""

import sys
from pathlib import Path

ULTRA_DIR = Path(__file__).parent
sys.path.insert(0, str(ULTRA_DIR))

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    
    subcmd = sys.argv[1]
    remaining = sys.argv[2:]
    
    if subcmd == "dag":
        from dag_context import main as dag_main
        sys.argv = ["dag_context.py"] + remaining
        dag_main()
    
    elif subcmd == "eval":
        from self_eval_pipeline import main as eval_main
        sys.argv = ["self_eval_pipeline.py"] + remaining
        eval_main()
    
    elif subcmd == "bundle":
        from skill_bundler import main as bundle_main
        sys.argv = ["skill_bundler.py"] + remaining
        bundle_main()
    
    elif subcmd == "run":
        from ultra_pipeline import main as run_main
        sys.argv = ["ultra_pipeline.py"] + remaining
        run_main()
    
    else:
        print(f"Unknown subcommand: {subcmd}")
        print(__doc__)

if __name__ == "__main__":
    main()
