#!/usr/bin/env python3
"""Check the public Git candidate set, Python syntax, metadata and local Markdown links."""
import ast
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
raw = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT)
files = sorted(set(raw.decode().split("\0")) - {""})
errors = []
for name in files:
    p = ROOT/name
    if not p.is_file():
        errors.append(f"Missing candidate file: {name}")
        continue
    if p.stat().st_size > 5*1024*1024:
        errors.append(f"File larger than 5 MiB: {name}")
    if p.suffix.lower() in {".blend", ".blend1", ".splat", ".ksplat", ".ply", ".npz", ".npy", ".mp4", ".mov"}:
        errors.append(f"Binary source/output asset in public set: {name}")
    if name.startswith(("prompts/garden/docs/", "prompts/garden/tools/")):
        errors.append(f"Local notes/viewer bundle in public set: {name}")
    if p.suffix == ".py":
        try:
            ast.parse(p.read_text(), filename=name)
        except SyntaxError as e:
            errors.append(str(e))
    if p.suffix in {".py", ".md", ".json", ".yaml", ".yml", ".toml", ".txt"}:
        content = p.read_text()
        if re.search(r"/(?:Users|home)/[A-Za-z][\w.-]+/", content):
            errors.append(f"Machine-specific home path: {name}")
        if re.search(r"(?:ghp_|github_pat_|sk-proj-)[A-Za-z0-9_]{20,}", content):
            errors.append(f"Possible credential: {name}")
    if p.suffix == ".md":
        for dest in re.findall(r"\]\(([^)]+)\)", p.read_text()):
            if "://" in dest or dest.startswith("#"):
                continue
            target = (p.parent/dest.split("#")[0]).resolve()
            if not target.exists():
                errors.append(f"Broken local link: {name} → {dest}")
name = "gaussian-splat-to-blender-nodes"
plugin = json.loads((ROOT/".claude-plugin/plugin.json").read_text())
market = json.loads((ROOT/".claude-plugin/marketplace.json").read_text())
if plugin["name"] != name or market["plugins"][0]["name"] != name:
    errors.append("Plugin names disagree")
skill = (ROOT/f"skills/{name}/SKILL.md").read_text()
if not skill.startswith(f"---\nname: {name}\ndescription:") or len(skill.split("---", 2)) != 3:
    errors.append("Skill frontmatter is missing or misnamed")
if not files or "README.md" not in files:
    errors.append("Repository candidate set is empty or lacks README")
for error in errors:
    print("ERROR:", error)
print(f"Checked {len(files)} candidate files; {len(errors)} error(s)")
raise SystemExit(bool(errors))
