#!/usr/bin/env python3
"""Sync formula YAML files from stack repos in the agentic-stacks org.

Usage:
    python sync_formulas.py --org agentic-stacks --output ./stacks
    python sync_formulas.py --org agentic-stacks --output ./stacks --token ghp_...

Requires: PyYAML. Uses GitHub REST API directly (no gh CLI needed).
"""

import argparse
import json
import pathlib
import sys
import urllib.request
import urllib.error
from typing import Any
from base64 import b64decode

import yaml


CATEGORY_RULES = {
    "hardware": ["hardware-", "dell", "hpe", "supermicro", "idrac", "ilo", "bmc", "ipmi"],
    "platform": ["openstack", "kubernetes", "k8s", "talos", "docker", "proxmox", "nomad"],
    "storage": ["ceph", "minio", "zfs", "nfs", "gluster", "longhorn"],
    "networking": ["ipxe", "pxe", "opnsense", "pfsense", "frr", "bgp", "dns", "dhcp"],
    "observability": ["prometheus", "grafana", "loki", "jaeger", "datadog"],
    "security": ["vault", "keycloak", "cert-manager"],
    "automation": ["ansible", "terraform", "pulumi"],
}


def _infer_category(name: str, manifest: dict) -> str:
    """Infer a category from the stack name and target software."""
    search = name.lower()
    target = (manifest.get("target", {}).get("software", "") or "").lower()
    for category, keywords in CATEGORY_RULES.items():
        for kw in keywords:
            if kw in search or kw in target:
                return category
    return "other"


def manifest_to_formula(manifest: dict[str, Any]) -> dict[str, Any]:
    """Convert a stack.yaml manifest into a registry formula."""
    owner = manifest.get("owner") or manifest.get("namespace", "")
    name = manifest["name"]
    version = "0.0.1"

    # Strip 'entry' from skills — formulas only need name + description
    skills = []
    for skill in manifest.get("skills", []):
        skills.append({
            "name": skill["name"],
            "description": skill.get("description", ""),
        })

    # Flatten tools to just names if they're dicts
    requires = dict(manifest.get("requires", {}))
    if "tools" in requires:
        tools = requires["tools"]
        if tools and isinstance(tools[0], dict):
            requires["tools"] = [t["name"] for t in tools]

    category = manifest.get("category", _infer_category(name, manifest))

    return {
        "name": name,
        "owner": owner,
        "version": str(version),
        "category": category,
        "repository": manifest.get("repository") or f"https://github.com/{owner}/{name}",
        "tag": f"v{version}",
        "description": manifest.get("description", "").strip(),
        "target": manifest.get("target", {}),
        "skills": skills,
        "depends_on": manifest.get("depends_on", []),
        "requires": requires,
    }


def write_formulas(output_dir: pathlib.Path, formulas: list[dict]) -> None:
    """Write formula YAML files to output_dir/stacks/<owner>/<name>.yaml."""
    for formula in formulas:
        owner = formula["owner"]
        name = formula["name"]
        owner_dir = output_dir / "stacks" / owner
        owner_dir.mkdir(parents=True, exist_ok=True)
        formula_path = owner_dir / f"{name}.yaml"
        # Preserve version/tag from existing formula (set by tagger)
        if formula_path.exists():
            existing = yaml.safe_load(formula_path.read_text()) or {}
            if existing.get("version") and existing["version"] != "0.0.1":
                formula["version"] = existing["version"]
                formula["tag"] = existing.get("tag", f"v{existing['version']}")
        with open(formula_path, "w") as f:
            yaml.dump(formula, f, default_flow_style=False, sort_keys=False,
                      allow_unicode=True)


def _api_get(url: str, token: str | None = None) -> dict | list | None:
    """Make a GET request to the GitHub REST API."""
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "agentic-stacks-sync",
    }
    if token:
        headers["Authorization"] = f"token {token}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code != 404:
            print(f"  API error {e.code}: {url}", file=sys.stderr)
        return None


def fetch_repos(org: str, token: str | None = None) -> list[str]:
    """List all public repos in a GitHub org (handles pagination).

    Uses type=all to list all repos the token can access.
    """
    repos = []
    page = 1
    while True:
        url = (f"https://api.github.com/orgs/{org}/repos"
               f"?per_page=100&page={page}")
        data = _api_get(url, token=token)
        if data is None:
            print(f"  API request failed for page {page}", file=sys.stderr)
            break
        if not data:
            break
        repos.extend(r["name"] for r in data)
        if len(data) < 100:
            break
        page += 1
    return repos


def fetch_manifest(org: str, repo: str, token: str | None = None) -> dict | None:
    """Fetch stack.yaml from a repo. Returns None if not found."""
    url = f"https://api.github.com/repos/{org}/{repo}/contents/stack.yaml"
    data = _api_get(url, token)
    if not data or "content" not in data:
        return None
    try:
        content = b64decode(data["content"]).decode("utf-8")
        return yaml.safe_load(content)
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser(description="Sync registry formulas from GitHub org")
    parser.add_argument("--org", default="agentic-stacks", help="GitHub org to scan")
    parser.add_argument("--output", default=".", help="Output directory (registry repo root)")
    parser.add_argument("--token", default=None, help="GitHub token (optional, for rate limits)")
    args = parser.parse_args()

    output_dir = pathlib.Path(args.output)
    print(f"Scanning {args.org}...")

    repos = fetch_repos(args.org, args.token)
    print(f"Found {len(repos)} repos")

    formulas = []
    for repo in repos:
        manifest = fetch_manifest(args.org, repo, args.token)
        if manifest:
            formula = manifest_to_formula(manifest)
            formulas.append(formula)
        else:
            print(f"  {repo} — no stack.yaml, skipping")

    write_formulas(output_dir, formulas)

    # Print final versions (after preservation from existing formulas)
    for formula in formulas:
        print(f"  {formula['owner']}/{formula['name']}@{formula['version']}")
    print(f"\nWrote {len(formulas)} formula(s)")


if __name__ == "__main__":
    main()
