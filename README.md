# Agent Brain

Local-first knowledge management system built on the Model Context Protocol (MCP). Enables bidirectional communication between LLMs and markdown files, creating a personal and team knowledge graph that persists across conversations.

Fork of [basic-memory](https://github.com/basicmachines-co/basic-memory) adapted for internal Box use.

## Install

```bash
git clone git@git.dev.box.net:jackzhang/agent-brain.git
cd agent-brain
pip install -e ".[dev]"

# Verify
ab --version
```

CLI aliases: `ab`, `agent-brain`, `bm` (all point to the same binary).

## How We Use It

Agent Brain serves two purposes:

1. **Personal knowledge** — tool learnings, debugging findings, architecture decisions captured automatically from your Claude Code sessions into `~/agent-brain/knowledge/`.

2. **Team knowledge** — shared investigations, decisions, and code change context written to Box Drive via the `team-knowledge` project. Syncs to everyone's machine automatically.

### Team Setup

Run the setup script to register the team knowledge project and install hooks:

```bash
bash ~/Library/CloudStorage/Box-Box/Shield/3.\ Shield\ Engineering/Classification\ Team\ Knowledge/setup-team-knowledge.sh
```

This:
- Registers the Box Drive team folder as an `ab` project
- Installs Claude Code hooks (signal collector, stop hook, prompt hook)
- Appends team knowledge instructions to your `~/.claude/CLAUDE.md`
- Verifies connectivity

See the [team knowledge README](https://git.dev.box.net/jackzhang/agent-brain/-/blob/main/docs/team-knowledge.md) for full onboarding details.

## Key Commands

```bash
# Search personal knowledge
ab tool search-notes "topic" --tag repo-name

# Search team knowledge
ab tool search-notes "deadletter" --project team-knowledge

# Recent activity
ab tool recent-activity --timeframe 7d
ab tool recent-activity --project team-knowledge --timeframe 7d

# Read a specific note
ab tool read-note "memory://oncall/investigations/slug" --project team-knowledge

# Write a note
ab tool write-note --title "Finding title" \
  --folder "oncall/investigations" \
  --tags "oncall,classification" \
  --project team-knowledge

# Deep context (follows relations between notes)
ab tool build-context "memory://knowledge/decisions/slug"

# Project management
ab project list
ab project info team-knowledge
```

## Development

```bash
# Install dev dependencies
just install

# Run tests (SQLite only, fast)
just test-sqlite

# Run tests (SQLite + Postgres, needs Docker)
just test

# Fast local loop (lint + format + typecheck + impacted tests + smoke)
just fast-check

# Lint / format / typecheck
just lint
just format
just typecheck

# Create a database migration
just migration "Your migration message"
```

Requires Python 3.12+. Postgres tests use [testcontainers](https://testcontainers-python.readthedocs.io/) (Docker required).

## Note Format

Agent Brain watches a directory of markdown files, parses them into a knowledge graph, and exposes that graph via MCP tools. Notes use structured markdown with three parts:

1. **Frontmatter** — YAML metadata (`title`, `tags`, `permalink`) for indexing
2. **Observations** — `- [category] content #tag (context)` — categorized facts that search indexes
3. **Relations** — `- relation_type [[Target]]` — links between entities that `build_context` traverses

Example:

```markdown
---
title: DLQ Replay Fix
tags: [oncall, classification]
---

# DLQ Replay Fix

## Observations
- [finding] Root cause was expired TTL on retry messages #classification
- [decision] Switched to exponential backoff for DLQ replays #architecture
- [context] Found while investigating alert CLASSIFY-4082 #classification

## Relations
- discovered_in [[classification]]
- relates_to [[DLQ Retry Logic]]
```

**The hooks write notes in this exact format.** If you're modifying hooks or writing notes manually, follow it — if the format is wrong, the file still syncs but won't appear in search or graph traversal.

Full format reference with schemas, permalinks, and edge cases: [docs/NOTE-FORMAT.md](docs/NOTE-FORMAT.md)

## Architecture

See [CLAUDE.md](CLAUDE.md) for detailed architecture, code style, and development guidelines.

Key layers:
- **MCP server** (`src/basic_memory/mcp/`) — tools exposed to LLMs via Model Context Protocol
- **API** (`src/basic_memory/api/`) — FastAPI REST endpoints
- **Services** (`src/basic_memory/services/`) — business logic
- **Repository** (`src/basic_memory/repository/`) — data access (SQLAlchemy 2.0 async)
- **Sync** (`src/basic_memory/sync/`) — file watcher and markdown-to-DB synchronization
- **CLI** (`src/basic_memory/cli/`) — Typer CLI (`ab` command)

## License

AGPL-3.0. Upstream: [basicmachines-co/basic-memory](https://github.com/basicmachines-co/basic-memory)
