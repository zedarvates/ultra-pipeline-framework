#!/usr/bin/env python3
"""
dag_context.py — DAG-Based Context Manager

Remplace le summary lineaire par un graphe de decisions/compressions.
Inspire de MUSE-AutoSkill (arXiv 2605.27366).

Structure:
  Nodes = turns de raisonnement (plan, action, observation)
  Branches = approches alternatives
  Compression L1 = in-place summary (20K → 5K tokens)
  Compression L2 = chain-level merge (71K → 42K tokens)

Usage:
  python3 dag_context.py add --type plan "Étudier le sujet X"
  python3 dag_context.py add --type action --tool web_search "recherche Y"
  python3 dag_context.py compress --level 2 --budget 50000
  python3 dag_context.py export --format json
  python3 dag_context.py show  # affiche l'arbre
"""

import json, os, sys, hashlib, time
from datetime import datetime
from pathlib import Path

HOME = Path(os.environ.get("ULTRA_HOME", Path.cwd() / "ultra"))
STORE = HOME / "dag_store"
SESSIONS = STORE / "sessions"
NODES = STORE / "nodes"
INDEX = STORE / "index.json"

# ── Node Types ──────────────────────────────────────────
NODE_TYPES = {"plan", "action", "observation", "decision", "hypothesis", "result"}

# ── Data Model ──────────────────────────────────────────
def make_node(node_type, content, parent_id=None, tool=None, cost=0):
    assert node_type in NODE_TYPES, f"Invalid type: {node_type}"
    nid = hashlib.sha256(f"{content}{time.time()}".encode()).hexdigest()[:12]
    return {
        "id": nid,
        "type": node_type,
        "content": content,
        "parent": parent_id,
        "tool": tool,
        "cost": cost,          # tokens used
        "status": "active",    # active | compressed | merged | dropped
        "timestamp": datetime.utcnow().isoformat(),
        "summary": None,       # filled by compression
        "children": [],
    }

# ── Persistence ──────────────────────────────────────────
def init_store():
    SESSIONS.mkdir(parents=True, exist_ok=True)
    NODES.mkdir(parents=True, exist_ok=True)
    
def load_index():
    if INDEX.exists():
        return json.loads(INDEX.read_text())
    return {"active_session": None, "sessions": []}

def save_index(idx):
    INDEX.write_text(json.dumps(idx, indent=2))

def save_node(node, session_id):
    path = NODES / f"{session_id}_{node['id']}.json"
    path.write_text(json.dumps(node, indent=2))

def load_session_nodes(session_id):
    nodes = []
    for f in sorted(NODES.glob(f"{session_id}_*.json")):
        nodes.append(json.loads(f.read_text()))
    return nodes

def save_session(session):
    path = SESSIONS / f"{session['id']}.json"
    path.write_text(json.dumps(session, indent=2))

# ── Session Management ──────────────────────────────────
def new_session(label=""):
    init_store()
    sid = hashlib.sha256(f"{label}{time.time()}".encode()).hexdigest()[:16]
    session = {
        "id": sid,
        "label": label,
        "created": datetime.utcnow().isoformat(),
        "total_cost": 0,
        "total_nodes": 0,
        "compressed_nodes": 0,
        "root_node": None,
        "head_node": None,  # current leaf
    }
    save_session(session)
    idx = load_index()
    idx["active_session"] = sid
    idx["sessions"].append({"id": sid, "label": label, "created": session["created"]})
    save_index(idx)
    return session

def get_active_session():
    idx = load_index()
    if not idx["active_session"]:
        return None
    path = SESSIONS / f"{idx['active_session']}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())

def set_active_session(sid):
    idx = load_index()
    idx["active_session"] = sid
    save_index(idx)

# ── Node Operations ─────────────────────────────────────
def add_node(node_type, content, tool=None, cost=0):
    session = get_active_session()
    if not session:
        session = new_session("auto")
    
    parent_id = session["head_node"]
    node = make_node(node_type, content, parent_id, tool, cost)
    
    if parent_id:
        parent_path = NODES / f"{session['id']}_{parent_id}.json"
        if parent_path.exists():
            parent = json.loads(parent_path.read_text())
            parent["children"].append(node["id"])
            save_node(parent, session["id"])
    
    if not session["root_node"]:
        session["root_node"] = node["id"]
    session["head_node"] = node["id"]
    session["total_cost"] += cost
    session["total_nodes"] += 1
    save_session(session)
    save_node(node, session["id"])
    return node

# ── Compression Engine ──────────────────────────────────
def estimate_tokens(text):
    """Approximation rapide: 1 token ≈ 4 caractères"""
    return len(text) // 4

def compress_level1(nodes, max_tokens=5000):
    """L1: In-place summary — chaque node oversized est résumé individuellement"""
    compressed = []
    for node in nodes:
        content_tokens = estimate_tokens(node.get("content", ""))
        if content_tokens > max_tokens:
            # Compacter le contenu (on stocke le résumé, garde les métadonnées)
            node["summary"] = node["content"][:max_tokens * 4] + "... [COMPRESSED_L1]"
            node["content"] = node["summary"]
            node["status"] = "compressed"
            node["cost"] = min(node["cost"], max_tokens)
        compressed.append(node)
    return compressed

def compress_level2(nodes, budget=50000):
    """L2: Chain-level merge — T3..T5 fusionnés en un tour synthétique"""
    if len(nodes) <= 4:
        return nodes
    
    # Pinner le premier et le dernier
    first = nodes[0]
    last = nodes[-1]
    
    # Fusionner le milieu (T2..Tn-1)
    middle = nodes[1:-1]
    middle_text = " | ".join(n.get("content", "")[:200] for n in middle)
    middle_tools = list(set(n.get("tool") for n in middle if n.get("tool")))
    middle_cost = sum(n.get("cost", 0) for n in middle)
    
    merged = make_node("observation", f"[MERGED L2] {middle_text[:500]}")
    merged["status"] = "merged"
    merged["cost"] = middle_cost
    merged["tool"] = ",".join(middle_tools) if middle_tools else None
    
    for n in middle:
        n["status"] = "merged_into_child"
    
    # Mettre à jour le parent du merged
    merged["parent"] = first["id"]
    first["children"] = [merged["id"]]
    last["parent"] = merged["id"]
    
    result = [first, merged, last]
    return result

def compress_dag(session_id=None, level=2, budget=50000):
    """Pipeline de compression complet"""
    if not session_id:
        session = get_active_session()
        if not session:
            return None
        session_id = session["id"]
    
    nodes = load_session_nodes(session_id)
    if not nodes:
        return []
    
    # Trier par timestamp
    nodes.sort(key=lambda n: n.get("timestamp", ""))
    
    if level >= 1:
        nodes = compress_level1(nodes)
    if level >= 2:
        nodes = compress_level2(nodes, budget)
    
    # Sauvegarder les nodes compressés
    session = json.loads((SESSIONS / f"{session_id}.json").read_text())
    session["compressed_nodes"] = sum(1 for n in nodes if n["status"] in ("compressed", "merged"))
    save_session(session)
    
    return nodes

# ── Export ──────────────────────────────────────────────
def export_dag(session_id=None, fmt="json"):
    """Exporte le DAG pour injection dans le context LLM"""
    if not session_id:
        session = get_active_session()
        if not session:
            return None
        session_id = session["id"]
    
    nodes = load_session_nodes(session_id)
    if not nodes:
        return None
    
    session = json.loads((SESSIONS / f"{session_id}.json").read_text())
    
    if fmt == "json":
        return json.dumps({
            "session": {
                "id": session["id"],
                "label": session["label"],
                "total_cost": session["total_cost"],
                "total_nodes": session["total_nodes"],
            },
            "nodes": nodes,
        }, indent=2)
    
    elif fmt == "compact":
        """Format optimisé token — juste l'essentiel"""
        lines = [f"# DAG: {session['label']} ({session['total_nodes']} nodes, {session['total_cost']} tokens)"]
        for n in nodes:
            if n["status"] not in ("merged_into_child", "dropped"):
                icon = {"plan": "📋", "action": "⚡", "observation": "👁", 
                        "decision": "🔀", "hypothesis": "💡", "result": "✅"}.get(n["type"], "•")
                lines.append(f"{icon} [{n['type']}] {n.get('content', '')[:120]}")
        return "\n".join(lines)
    
    elif fmt == "tree":
        """Format arborescent pour visualisation"""
        nodes_by_id = {n["id"]: n for n in nodes}
        root = session.get("root_node")
        if not root or root not in nodes_by_id:
            return "No root node found"
        
        def render(nid, depth=0):
            n = nodes_by_id.get(nid)
            if not n:
                return ""
            indent = "  " * depth
            status_icon = {"active": "●", "compressed": "○", "merged": "◉"}.get(n["status"], "?")
            line = f"{indent}{status_icon} [{n['type']}] {n.get('content', '')[:80]}"
            children_lines = []
            for cid in n.get("children", []):
                cl = render(cid, depth + 1)
                if cl:
                    children_lines.append(cl)
            return "\n".join([line] + children_lines)
        
        return render(root)

# ── Stats ───────────────────────────────────────────────
def get_stats(session_id=None):
    if not session_id:
        session = get_active_session()
        if not session:
            return None
        session_id = session["id"]
    
    session = json.loads((SESSIONS / f"{session_id}.json").read_text())
    nodes = load_session_nodes(session_id)
    
    type_counts = {}
    for n in nodes:
        type_counts[n["type"]] = type_counts.get(n["type"], 0) + 1
    
    return {
        "session_id": session_id,
        "label": session["label"],
        "total_nodes": session["total_nodes"],
        "active_nodes": sum(1 for n in nodes if n["status"] == "active"),
        "compressed_nodes": sum(1 for n in nodes if n["status"] == "compressed"),
        "merged_nodes": sum(1 for n in nodes if n["status"] == "merged"),
        "total_cost": session["total_cost"],
        "type_breakdown": type_counts,
    }

# ── CLI ─────────────────────────────────────────────────
def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    
    cmd = sys.argv[1]
    
    if cmd == "new":
        label = sys.argv[2] if len(sys.argv) > 2 else ""
        s = new_session(label)
        print(json.dumps(s, indent=2))
    
    elif cmd == "add":
        node_type = sys.argv[2] if len(sys.argv) > 2 else "observation"
        content = " ".join(sys.argv[3:]) if len(sys.argv) > 3 else ""
        if not content:
            print("Usage: dag_context.py add <type> <content>")
            return
        node = add_node(node_type, content)
        print(json.dumps(node, indent=2))
    
    elif cmd == "compress":
        level = int(sys.argv[2]) if len(sys.argv) > 2 else 2
        budget = int(sys.argv[3]) if len(sys.argv) > 3 else 50000
        nodes = compress_dag(level=level, budget=budget)
        print(f"Compressed to {len(nodes)} nodes")
    
    elif cmd == "export":
        fmt = sys.argv[2] if len(sys.argv) > 2 else "compact"
        print(export_dag(fmt=fmt))
    
    elif cmd == "show":
        print(export_dag(fmt="tree"))
    
    elif cmd == "stats":
        print(json.dumps(get_stats(), indent=2))
    
    elif cmd == "list":
        idx = load_index()
        for s in idx.get("sessions", []):
            print(f"  {s['id'][:8]}… {s.get('label', '(no label)')} — {s['created'][:19]}")
    
    elif cmd == "switch":
        if len(sys.argv) < 3:
            print("Usage: dag_context.py switch <session_id>")
            return
        set_active_session(sys.argv[2])
        print(f"Active session: {sys.argv[2]}")

if __name__ == "__main__":
    main()
