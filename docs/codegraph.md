# FlowScribe Codegraph

FlowScribe now includes a workspace-local codegraph that can be rebuilt and
queried without any external service or system installation.

## What It Is

The codegraph is a lightweight Python AST index for this repository. It records:

- modules
- classes
- functions and methods
- import edges
- containment edges
- inheritance edges
- simple call edges

It is designed for repo navigation by humans, Codex, Claude Code, and other
LLM agents working inside this workspace.

## What It Is Not

- It is not a fully semantic cross-language graph database
- It does not force model internals to use the graph automatically
- It does not replace careful file reads for final verification

What it does provide is a stable, low-cost first-pass map that agents can query
before opening many files.

## Build

```powershell
python scripts/build_codegraph.py
```

This writes:

- [index.json](/E:/Draft/FlowScribe/.codex/codegraph/index.json)
- [summary.md](/E:/Draft/FlowScribe/.codex/codegraph/summary.md)

## Query

```powershell
python scripts/query_codegraph.py search TranscriptionService
python scripts/query_codegraph.py search QueueView --type class
python scripts/query_codegraph.py show flowscribe.app.service.TranscriptionService
python scripts/query_codegraph.py neighbors flowscribe.providers.transcribe.registry.ParaformerProvider
```

## Recommended Agent Workflow

1. Read [.codex/codegraph/summary.md](/E:/Draft/FlowScribe/.codex/codegraph/summary.md)
2. Use `scripts/query_codegraph.py` to narrow the symbol/module set
3. Read only the relevant implementation files
4. Verify final behavior in source and tests

## Enforcement Reality

You cannot truly force Codex or other LLMs to consume a local codegraph unless
their runtime exposes that graph as a first-class tool. In this repository we
use the next best approach:

- provide a committed query interface
- generate committed graph artifacts
- add repo instructions that tell agents to consult the codegraph first

