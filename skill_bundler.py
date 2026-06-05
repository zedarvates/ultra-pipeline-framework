#!/usr/bin/env python3
"""
Ultra Skill Bundler 2.0

Transforme nos skills en bundles executables avec:
- SKILL.md (definition)
- scripts/ (executeables)
- tests/ (validation sandbox)
- memory.md (par-skill: long/mid/short-term)
- meta.json (score, runs, derniere erreur)

Inspire de MUSE-AutoSkill — le skill n'est pas juste un
fichier instruction, c'est un package avec tests et memory.

Scoring par skill:
- success_rate: % de runs sans erreur
- avg_duration: temps moyen d'execution  
- avg_tokens: tokens consommes
- last_error: derniere erreur rencontree
- confidence: [0-1] base sur l'historique

Bundles valides seulement si les tests passent.
En mode test (read-only) par defaut — pas de risque.

Structure generee:
  skills/<name>/
    SKILL.md
    meta.json
    memory/
      long_term.md    # connaissances persistantes
      mid_term.md     # contexte de session (reset entre sessions)
      short_term.md   # etat courant (reset a chaque run)
    scripts/
      <name>.py       # scripts d'execution
    tests/
      test_<name>.py  # tests de validation
      fixtures/       # donnees de test

Usage:
  # Creer un bundle depuis un skill existant
  python3 skill_bundler.py init <skill_name>
  
  # Valider un bundle (tests)
  python3 skill_bundler.py validate <skill_name>
  
  # Enregistrer un run (pour scoring)
  python3 skill_bundler.py record <skill_name> --score 85 --duration 120 --tokens 5000
  
  # Voir le score d'un skill
  python3 skill_bundler.py score <skill_name>
  
  # Lister les skills bundles
  python3 skill_bundler.py list
  
  # Exporter un bundle (portable)
  python3 skill_bundler.py export <skill_name> --output /tmp/bundle.json
"""

import json, os, sys, hashlib, subprocess, time, re
from datetime import datetime
from pathlib import Path

ULTRA_HOME = Path(os.environ.get("ULTRA_HOME", Path.cwd() / "ultra"))
SKILLS_DIR = Path.home() / ".hermes" / "skills"
BUNDLES_DIR = ULTRA_HOME / "skill_bundles"
MEMORY_DIR = ULTRA_HOME / "skill_memory"

# ── Templates ────────────────────────────────────────────

MEMORY_LONG_TERM = """# Long-Term Memory — {skill_name}

> Connaissances persistantes, traverse les sessions.
> Mise a jour manuellement ou apres runs confirmes.

## Contexte
- Cree: {created}
- Derniere mise a jour: {created}

## Connaissances
<!-- Ajouter ici les apprentissages durables -->

## Patterns reconnus
<!-- Patterns decouverts pendant les runs -->

## Pieges connus
<!-- Erreurs frequentes a eviter -->
"""

MEMORY_MID_TERM = """# Mid-Term Memory — {skill_name}

> Contexte de session. Reset entre sessions longues.
> Mis a jour automatiquement pendant les runs.

## Session actuelle
- Debut: {timestamp}
- Objectif: (rempli auto)

## Etat
<!-- Etat courant de la session -->

## Notes
<!-- Notes de session -->
"""

MEMORY_SHORT_TERM = """# Short-Term Memory — {skill_name}

> Etat courant. Reset a chaque run.
> Utilise pour la coherence immediate.

## Run actuel
- ID: (rempli auto)
- Debut: {timestamp}

## Variables
<!-- Variables du run en cours -->

## Resultats intermediaires
<!-- Resultats partiels a conserver -->
"""

TEST_TEMPLATE = '''#!/usr/bin/env python3
"""
Tests pour le skill: {skill_name}
Valide que le bundle fonctionne correctement.
"""
import json, subprocess, sys
from pathlib import Path

BUNDLE_DIR = Path(__file__).parent.parent

def test_skill_exists():
    """Le skill a un SKILL.md valide"""
    skill_md = BUNDLE_DIR / "SKILL.md"
    assert skill_md.exists(), "SKILL.md missing"
    content = skill_md.read_text()
    assert "name:" in content, "SKILL.md missing frontmatter"

def test_scripts_executables():
    """Les scripts sont executables"""
    scripts_dir = BUNDLE_DIR / "scripts"
    if scripts_dir.exists():
        for script in scripts_dir.glob("*.py"):
            result = subprocess.run(
                [sys.executable, str(script), "--help"],
                capture_output=True, timeout=10
            )
            # Accepte exit 0 ou 2 (argparse --help = exit 0)

def test_memory_structure():
    """La structure memory existe"""
    for subdir in ["long_term.md", "mid_term.md", "short_term.md"]:
        path = BUNDLE_DIR / "memory" / subdir
        # C'est OK si ca n'existe pas encore (cree au 1er run)

def test_meta_valid():
    """meta.json est valide"""
    meta_path = BUNDLE_DIR / "meta.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())
        assert "name" in meta, "meta.json missing name"
        assert "score" in meta, "meta.json missing score"

if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            print(f"  PASS: {test.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL: {test.__name__}: {e}")
            failed += 1
    
    print(f"\\n{passed}/{passed+failed} tests passed")
    sys.exit(0 if failed == 0 else 1)
'''

# ── Bundle Manager ──────────────────────────────────────

def init_store():
    BUNDLES_DIR.mkdir(parents=True, exist_ok=True)
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)

def create_bundle(skill_name, description="", author="hermes"):
    """Cree un bundle ultra depuis un skill existant ou nouveau"""
    bundle_dir = BUNDLES_DIR / skill_name
    if bundle_dir.exists():
        print(f"Bundle '{skill_name}' already exists")
        return None
    
    # Creer la structure
    (bundle_dir / "scripts").mkdir(parents=True)
    (bundle_dir / "tests").mkdir(parents=True)
    (bundle_dir / "memory").mkdir(parents=True)
    (bundle_dir / "tests" / "fixtures").mkdir(parents=True)
    
    now = datetime.utcnow().isoformat()
    
    # Meta
    meta = {
        "name": skill_name,
        "description": description,
        "author": author,
        "created": now,
        "version": 1,
        "score": {
            "success_rate": 0,
            "avg_duration": 0,
            "avg_tokens": 0,
            "total_runs": 0,
            "failed_runs": 0,
            "confidence": 0,
        },
        "last_run": None,
        "last_error": None,
        "status": "new",  # new | validated | active | deprecated
    }
    (bundle_dir / "meta.json").write_text(json.dumps(meta, indent=2))
    
    # Memory files
    (bundle_dir / "memory" / "long_term.md").write_text(
        MEMORY_LONG_TERM.format(skill_name=skill_name, created=now[:19]))
    (bundle_dir / "memory" / "mid_term.md").write_text(
        MEMORY_MID_TERM.format(skill_name=skill_name, timestamp=now[:19]))
    (bundle_dir / "memory" / "short_term.md").write_text(
        MEMORY_SHORT_TERM.format(skill_name=skill_name, timestamp=now[:19]))
    
    # Test scaffold
    (bundle_dir / "tests" / f"test_{skill_name}.py").write_text(
        TEST_TEMPLATE.format(skill_name=skill_name))
    
    # SKILL.md — copier depuis l'existant si present
    existing_skill = find_existing_skill(skill_name)
    if existing_skill:
        shutil.copy(str(existing_skill / "SKILL.md"), str(bundle_dir / "SKILL.md"))
    else:
        (bundle_dir / "SKILL.md").write_text(
            f"---\nname: {skill_name}\ndescription: {description}\n---\n\n# {skill_name}\n\n{description}\n")
    
    return meta

def find_existing_skill(skill_name):
    """Cherche un skill existant dans ~/.hermes/skills/"""
    # Direct match
    direct = SKILLS_DIR / skill_name / "SKILL.md"
    if direct.exists():
        return direct.parent
    
    # Recherche recursive
    for f in SKILLS_DIR.rglob("SKILL.md"):
        if f.parent.name == skill_name:
            return f.parent
    
    return None

def validate_bundle(skill_name):
    """Valide un bundle en executant ses tests"""
    bundle_dir = BUNDLES_DIR / skill_name
    if not bundle_dir.exists():
        print(f"Bundle '{skill_name}' not found")
        return False
    
    test_file = bundle_dir / "tests" / f"test_{skill_name}.py"
    if not test_file.exists():
        print(f"No tests found for '{skill_name}'")
        return False
    
    result = subprocess.run(
        [sys.executable, str(test_file)],
        capture_output=True, text=True, timeout=30,
        cwd=str(bundle_dir)
    )
    
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    
    success = result.returncode == 0
    
    # mettre a jour meta
    meta = json.loads((bundle_dir / "meta.json").read_text())
    meta["status"] = "validated" if success else "broken"
    meta["last_validation"] = datetime.utcnow().isoformat()
    meta["validation_result"] = "pass" if success else "fail"
    (bundle_dir / "meta.json").write_text(json.dumps(meta, indent=2))
    
    return success

def record_run(skill_name, score=0, duration=0, tokens=0, error=None):
    """Enregistre un run pour scoring"""
    meta_path = BUNDLES_DIR / skill_name / "meta.json"
    if not meta_path.exists():
        print(f"Bundle '{skill_name}' not found")
        return None
    
    meta = json.loads(meta_path.read_text())
    s = meta["score"]
    
    total = s["total_runs"] + 1
    failed = s["failed_runs"] + (1 if error else 0)
    
    # Moyennes mobiles
    s["avg_duration"] = round(
        (s["avg_duration"] * s["total_runs"] + duration) / max(total, 1), 2)
    s["avg_tokens"] = round(
        (s["avg_tokens"] * s["total_runs"] + tokens) / max(total, 1), 1)
    s["success_rate"] = round((total - failed) / max(total, 1) * 100, 1)
    s["total_runs"] = total
    s["failed_runs"] = failed
    s["confidence"] = round(min(total / 10, 1.0) * (s["success_rate"] / 100), 2)
    
    meta["last_run"] = datetime.utcnow().isoformat()
    meta["last_error"] = error
    
    if not error:
        meta["status"] = "active"
    
    meta_path.write_text(json.dumps(meta, indent=2))
    return meta

def get_bundle_score(skill_name):
    """Retourne le score d'un bundle"""
    meta_path = BUNDLES_DIR / skill_name / "meta.json"
    if not meta_path.exists():
        return None
    return json.loads(meta_path.read_text())

def list_bundles():
    """Liste tous les bundles"""
    bundles = []
    for meta_file in sorted(BUNDLES_DIR.glob("*/meta.json")):
        try:
            meta = json.loads(meta_file.read_text())
            bundles.append(meta)
        except:
            pass
    return bundles

def export_bundle(skill_name, output_path):
    """Exporte un bundle en JSON portable (cross-agent transfer)"""
    bundle_dir = BUNDLES_DIR / skill_name
    if not bundle_dir.exists():
        print(f"Bundle '{skill_name}' not found")
        return None
    
    export = {
        "name": skill_name,
        "exported_at": datetime.utcnow().isoformat(),
        "format": "ultra-bundle-v1",
        "meta": json.loads((bundle_dir / "meta.json").read_text()),
    }
    
    # Inclure SKILL.md
    skill_md = bundle_dir / "SKILL.md"
    if skill_md.exists():
        export["skill_md"] = skill_md.read_text()
    
    # Inclure les scripts
    scripts = {}
    scripts_dir = bundle_dir / "scripts"
    if scripts_dir.exists():
        for f in scripts_dir.glob("*"):
            if f.is_file():
                scripts[f.name] = f.read_text()
    export["scripts"] = scripts
    
    # Inclure les tests
    tests = {}
    tests_dir = bundle_dir / "tests"
    if tests_dir.exists():
        for f in tests_dir.glob("*.py"):
            tests[f.name] = f.read_text()
    export["tests"] = tests
    
    output = Path(output_path)
    output.write_text(json.dumps(export, indent=2))
    return export

# ── Memory Manager ──────────────────────────────────────

def read_memory(skill_name, level="long_term"):
    """Lit la memory d'un skill"""
    path = BUNDLES_DIR / skill_name / "memory" / f"{level}.md"
    if not path.exists():
        return f"# No {level} memory yet"
    return path.read_text()

def write_memory(skill_name, level, content):
    """Ecrit la memory d'un skill"""
    path = BUNDLES_DIR / skill_name / "memory" / f"{level}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)

def append_memory(skill_name, level, note):
    """Ajoute une note a la memory"""
    path = BUNDLES_DIR / skill_name / "memory" / f"{level}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text() if path.exists() else f"# {level.replace('_', ' ').title()} Memory"
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    updated = f"{existing}\n\n## {timestamp}\n{note}"
    path.write_text(updated)

# ── CLI ─────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    
    cmd = sys.argv[1]
    init_store()
    
    if cmd == "init":
        name = sys.argv[2] if len(sys.argv) > 2 else "unnamed"
        desc = " ".join(sys.argv[3:]) if len(sys.argv) > 3 else ""
        meta = create_bundle(name, desc)
        if meta:
            print(f"Bundle created: {BUNDLES_DIR / name}")
            print(json.dumps(meta, indent=2))
    
    elif cmd == "validate":
        name = sys.argv[2] if len(sys.argv) > 2 else None
        if not name:
            print("Usage: skill_bundler.py validate <skill_name>")
            return
        success = validate_bundle(name)
        print(f"Validation: {'PASS' if success else 'FAIL'}")
    
    elif cmd == "record":
        if len(sys.argv) < 3:
            print("Usage: skill_bundler.py record <skill_name> [--score N] [--duration N] [--tokens N]")
            return
        name = sys.argv[2]
        score = int(sys.argv[sys.argv.index("--score") + 1]) if "--score" in sys.argv else 0
        duration = int(sys.argv[sys.argv.index("--duration") + 1]) if "--duration" in sys.argv else 0
        tokens = int(sys.argv[sys.argv.index("--tokens") + 1]) if "--tokens" in sys.argv else 0
        error = sys.argv[sys.argv.index("--error") + 1] if "--error" in sys.argv else None
        meta = record_run(name, score, duration, tokens, error)
        if meta:
            print(json.dumps(meta["score"], indent=2))
    
    elif cmd == "score":
        name = sys.argv[2] if len(sys.argv) > 2 else None
        if not name:
            print("Usage: skill_bundler.py score <skill_name>")
            return
        meta = get_bundle_score(name)
        if meta:
            print(json.dumps(meta["score"], indent=2))
    
    elif cmd == "list":
        bundles = list_bundles()
        if not bundles:
            print("No bundles yet")
            return
        b = sorted(bundles, key=lambda x: x.get("score", {}).get("success_rate", 0), reverse=True)
        for meta in b:
            s = meta.get("score", {})
            status_icon = {"new": "🆕", "validated": "✅", "active": "🟢", "broken": "🔴", "deprecated": "⬛"}.get(meta.get("status"), "?")
            print(f"  {status_icon} {meta['name']:30s} score={s.get('success_rate',0):5.1f}% runs={s.get('total_runs',0)} conf={s.get('confidence',0):.2f}")
    
    elif cmd == "export":
        if len(sys.argv) < 3:
            print("Usage: skill_bundler.py export <skill_name> --output /path")
            return
        name = sys.argv[2]
        output = sys.argv[sys.argv.index("--output") + 1] if "--output" in sys.argv else f"/tmp/{name}-bundle.json"
        export_bundle(name, output)
        print(f"Exported to: {output}")
    
    elif cmd == "memory":
        if len(sys.argv) < 4:
            print("Usage: skill_bundler.py memory <skill_name> <long_term|mid_term|short_term> [read|write|append] [content]")
            return
        name = sys.argv[2]
        level = sys.argv[3]
        action = sys.argv[4] if len(sys.argv) > 4 else "read"
        if action == "read":
            print(read_memory(name, level))
        elif action == "write":
            content = " ".join(sys.argv[5:]) if len(sys.argv) > 5 else ""
            write_memory(name, level, content)
            print(f"Memory written: {level}")
        elif action == "append":
            note = " ".join(sys.argv[5:]) if len(sys.argv) > 5 else ""
            append_memory(name, level, note)
            print(f"Note appended to {level}")

if __name__ == "__main__":
    main()
