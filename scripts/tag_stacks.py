#!/usr/bin/env python3
"""Auto-tag stack repos with calver versions when content changes.

For each stack formula, checks if the repo's HEAD commit has changed
since the last tag. If so, creates a new tag using calendar versioning:
  YYYY.MMDD.N  (e.g., 2026.0331.1)

Usage:
    python tag_stacks.py --input ./stacks --token ghp_...
"""

import argparse
import datetime
import json
import pathlib
import sys
import urllib.request
import urllib.error

import yaml


def _api(method: str, url: str, token: str, data: dict | None = None) -> dict | list | None:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "agentic-stacks-tagger",
        "Authorization": f"token {token}",
    }
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, headers=headers, method=method, data=body)
    if body:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        print(f"  API error {e.code}: {method} {url}", file=sys.stderr)
        return None


def get_head_sha(owner: str, repo: str, token: str) -> str | None:
    data = _api("GET", f"https://api.github.com/repos/{owner}/{repo}/git/ref/heads/main", token)
    if data and "object" in data:
        return data["object"]["sha"]
    return None


def get_latest_tag(owner: str, repo: str, token: str) -> tuple[str | None, str | None]:
    """Returns (tag_name, commit_sha) of the latest tag, or (None, None)."""
    data = _api("GET", f"https://api.github.com/repos/{owner}/{repo}/tags?per_page=1", token)
    if data and len(data) > 0:
        return data[0]["name"], data[0]["commit"]["sha"]
    return None, None


def next_version(owner: str, repo: str, token: str) -> str:
    """Generate next calver tag: YYYY.MMDD.N"""
    today = datetime.date.today()
    prefix = f"{today.year}.{today.month:02d}{today.day:02d}"

    # Check existing tags for today to get the sequence number
    data = _api("GET", f"https://api.github.com/repos/{owner}/{repo}/tags?per_page=100", token)
    seq = 0
    if data:
        for tag in data:
            name = tag["name"].lstrip("v")
            if name.startswith(prefix):
                parts = name.split(".")
                if len(parts) == 3:
                    try:
                        n = int(parts[2])
                        seq = max(seq, n)
                    except ValueError:
                        pass
    return f"{prefix}.{seq + 1}"


def create_tag(owner: str, repo: str, sha: str, tag: str, token: str) -> bool:
    """Create a lightweight tag via the GitHub API."""
    result = _api("POST", f"https://api.github.com/repos/{owner}/{repo}/git/refs", token, {
        "ref": f"refs/tags/v{tag}",
        "sha": sha,
    })
    return result is not None


def main():
    parser = argparse.ArgumentParser(description="Auto-tag stack repos with calver versions")
    parser.add_argument("--input", default="./stacks", help="Path to stacks/ directory")
    parser.add_argument("--token", required=True, help="GitHub token with repo access")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be tagged without tagging")
    args = parser.parse_args()

    stacks_dir = pathlib.Path(args.input)
    formulas = []
    for f in sorted(stacks_dir.rglob("*.yaml")):
        data = yaml.safe_load(f.read_text())
        if data and "name" in data and "repository" in data:
            formulas.append((f, data))

    if not formulas:
        print("No formulas found")
        return

    tagged = 0
    for formula_path, formula in formulas:
        repo_url = formula["repository"]
        if not repo_url:
            continue
        # Extract owner/repo from URL
        parts = repo_url.rstrip("/").split("/")
        owner, repo = parts[-2], parts[-1]
        name = formula["name"]

        head_sha = get_head_sha(owner, repo, args.token)
        if not head_sha:
            print(f"  {name}: could not get HEAD SHA, skipping")
            continue

        last_tag, last_sha = get_latest_tag(owner, repo, args.token)

        if last_sha == head_sha:
            # Sync existing tag version into formula (handles renamed repos
            # where the formula file is new but the repo already has a tag)
            if last_tag and formula.get("version") in (None, "0.0.1"):
                tag_version = last_tag.lstrip("v")
                formula["version"] = tag_version
                formula["tag"] = last_tag
                with open(formula_path, "w") as f:
                    yaml.dump(formula, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
                print(f"  {name}: synced version from existing tag ({last_tag})")
            else:
                print(f"  {name}: up to date ({last_tag})")
            continue

        version = next_version(owner, repo, args.token)

        if args.dry_run:
            print(f"  {name}: would tag v{version} at {head_sha[:7]} (was {last_tag or 'untagged'})")
        else:
            if create_tag(owner, repo, head_sha, version, args.token):
                print(f"  {name}: tagged v{version} at {head_sha[:7]}")
                # Update formula version
                formula["version"] = version
                formula["tag"] = f"v{version}"
                with open(formula_path, "w") as f:
                    yaml.dump(formula, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
                tagged += 1
            else:
                print(f"  {name}: failed to create tag")

    print(f"\nTagged {tagged} stack(s)")


if __name__ == "__main__":
    main()
