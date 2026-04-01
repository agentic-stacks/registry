# Agentic Stacks Registry

Formula index for [agentic stacks](https://github.com/agentic-stacks/agentic-stacks). Each formula points to a stack's source repo with metadata for discovery and installation.

## Structure

```
stacks/
└── <owner>/
    └── <stack-name>.yaml
```

## How It Works

The CLI caches this repo locally and reads formulas for `search` and `pull` operations:

```bash
agentic-stacks search openstack     # searches local formulas
agentic-stacks pull openstack-kolla # resolves repo URL from formula
```

## Auto-Sync

A GitHub Action runs hourly to scan repos in the `agentic-stacks` org for `stack.yaml` files and update formulas automatically.

## Adding a Third-Party Stack

Open a PR adding your formula to `stacks/<your-org>/<stack-name>.yaml`, or run:

```bash
cd your-stack/
agentic-stacks publish
```
