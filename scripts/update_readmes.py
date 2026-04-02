#!/usr/bin/env python3
"""Update README stack tables from registry formulas.

Reads formula YAMLs and regenerates the stack table in:
- The .github org profile README
- The main agentic-stacks repo README

Usage:
    python update_readmes.py --input ./stacks --dotgithub /path/to/.github --main /path/to/agentic-stacks
"""

import argparse
import pathlib

import yaml


CATEGORY_ORDER = [
    "platform",
    "storage",
    "hardware",
    "networking",
    "automation",
    "observability",
    "security",
    "other",
]


def load_stacks(stacks_dir: pathlib.Path) -> list[dict]:
    stacks = []
    for f in sorted(stacks_dir.rglob("*.yaml")):
        data = yaml.safe_load(f.read_text())
        if data and "name" in data:
            if not data.get("skills"):
                continue
            stacks.append(data)
    stacks.sort(
        key=lambda s: (
            CATEGORY_ORDER.index(s.get("category", "other"))
            if s.get("category", "other") in CATEGORY_ORDER
            else 99,
            s["name"],
        )
    )
    return stacks


def build_org_table(stacks: list[dict]) -> str:
    lines = ["| Stack | Category | Description |", "|-------|----------|-------------|"]
    for s in stacks:
        name = s["name"]
        owner = s.get("owner", "agentic-stacks")
        cat = s.get("category", "other").capitalize()
        desc = s.get("description", "").split(".")[0].strip()
        repo = s.get("repository", f"https://github.com/{owner}/{name}")
        lines.append(f"| [{name}]({repo}) | {cat} | {desc} |")
    return "\n".join(lines)


def build_main_table(stacks: list[dict]) -> str:
    lines = ["| Stack | Target | Skills |", "|-------|--------|--------|"]
    for s in stacks:
        name = s["name"]
        owner = s.get("owner", "agentic-stacks")
        target = (s.get("target", {}).get("software", "") or "").split("/")[0].strip()
        skills = len(s.get("skills", []))
        lines.append(
            f"| [{name}](https://www.agentic-stacks.com/stacks/{owner}/{name}) | {target} | {skills} |"
        )
    return "\n".join(lines)


def update_between_markers(
    content: str, marker_start: str, marker_end: str, replacement: str
) -> str:
    start = content.find(marker_start)
    end = content.find(marker_end)
    if start == -1 or end == -1:
        return content
    return (
        content[: start + len(marker_start)] + "\n" + replacement + "\n" + content[end:]
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="./stacks")
    parser.add_argument("--dotgithub", default=None, help="Path to .github repo")
    parser.add_argument("--main", default=None, help="Path to main agentic-stacks repo")
    args = parser.parse_args()

    stacks = load_stacks(pathlib.Path(args.input))
    if not stacks:
        print("No stacks found")
        return

    print(f"Found {len(stacks)} stacks")

    if args.dotgithub:
        readme = pathlib.Path(args.dotgithub) / "profile" / "README.md"
        if readme.exists():
            content = readme.read_text()
            table = build_org_table(stacks)
            updated = update_between_markers(
                content,
                "<!-- STACKS-TABLE-START -->",
                "<!-- STACKS-TABLE-END -->",
                table,
            )
            if updated != content:
                readme.write_text(updated)
                print(f"  Updated {readme}")
            else:
                print(f"  No markers in {readme}, skipping")

    if args.main:
        readme = pathlib.Path(args.main) / "README.md"
        if readme.exists():
            content = readme.read_text()
            table = build_main_table(stacks)
            updated = update_between_markers(
                content,
                "<!-- STACKS-TABLE-START -->",
                "<!-- STACKS-TABLE-END -->",
                table,
            )
            if updated != content:
                readme.write_text(updated)
                print(f"  Updated {readme}")
            else:
                print(f"  No markers in {readme}, skipping")


if __name__ == "__main__":
    main()
