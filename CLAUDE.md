# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A fork of the community **Query MCP server for Supabase** (originally by Alexander
Zuev). It is a Python MCP server (stdio) that lets an IDE/agent run SQL, manage schema
migrations, call the Supabase Management API, and use the Auth Admin SDK — all behind a
safety system. This fork adds a **Meta Ads** service alongside the Supabase tooling
(`supabase_mcp/services/meta_ads/`, `clients/meta_ads_client.py`) plus standalone
helper scripts at the repo root.

Python 3.12+, managed with **uv** (build backend: hatchling + hatch-vcs; version comes
from git tags via `hatch.version`).

## Commands

```bash
uv sync --all-groups            # install main + dev deps (what CI uses)
uv run pytest                   # unit tests only (integration excluded by default)
uv run pytest tests/test_tools.py            # one file
uv run pytest tests/test_tools.py::test_name # one test
uv run pytest -m integration    # integration tests (need a real/local Supabase + DB)
uv run ruff check .             # lint (line-length 120)
uv run ruff format .            # format (double quotes)
uv run mypy supabase_mcp        # strict type check
uv build                        # build the wheel/sdist
pre-commit run --all-files      # full hook suite (ruff, mypy, sqlfluff, pytest, build)
```

Entry points (from `pyproject.toml`): `supabase-mcp-server` (runs the server),
`supabase-mcp-inspector` (MCP dev inspector).

### Test / CI notes

- `addopts` defaults to `-m "not integration"`, so `pytest` runs unit tests only.
  Integration tests require database access and are gated by the `integration` marker.
- `asyncio_mode = auto` — async tests need no explicit decorator.
- CI (`.github/workflows/ci.yml`) runs `uv sync --all-groups` then pytest with
  coverage, using **dummy** `SUPABASE_*` env vars (unit tests must not need real
  credentials). Ruff lint/format steps are `continue-on-error` (informational);
  pytest is the gate. There are also CodeQL, SonarQube, and PyPI publish workflows.
- mypy is configured `strict` for `supabase_mcp` and relaxed for `tests.*`. In
  pre-commit, mypy and ruff are non-blocking (`|| true` / `--exit-zero`), but pytest
  and `uv build` are blocking.

## Architecture

Lifecycle is in `supabase_mcp/main.py`: a `FastMCP` server with a `lifespan` that
builds a `ServicesContainer`, registers tools, and on shutdown calls `os._exit(0)` — an
intentional hard exit to avoid an asyncio/stdio teardown hang. Don't "fix" that exit.

Key pieces:

- `core/container.py` — `ServicesContainer`, a singleton DI container. `initialize_services`
  constructs every client and manager and wires them together; most services are
  themselves singletons via `get_instance`. This is the place to register a new service.
- `core/feature_manager.py` — all tools are executed through `feature_manager.execute_tool(...)`,
  giving a single choke point for gating/feature checks.
- `tools/registry.py` — `ToolRegistry.register_tools()` declares every `@mcp.tool`. Each
  tool's description text is pulled from YAML in `tools/descriptions/*.yaml` via
  `ToolManager` (`tools/manager.py`); `ToolName` enum lives there. **Tool descriptions
  are edited in the YAML files, not inline in Python.**
- `services/` — the functional domains:
  - `database/` — `postgres_client.py` (asyncpg, pooled + direct), `query_manager.py`,
    `migration_manager.py` (auto-versions schema changes), and `sql/` with a `validator.py`
    (runtime SQL parse + risk assessment via `pglast`) and `.sql` query files loaded by
    `sql/loader.py`.
  - `api/` — Supabase Management API manager + OpenAPI `spec_manager`.
  - `sdk/` — Auth Admin SDK wrapper.
  - `safety/` — see below.
  - `logs/`, and `meta_ads/` (this fork's addition: `campaign_manager.py`, `models.py`).
- `clients/` — HTTP/SDK clients (`base_http_client.py`, `management_client.py`,
  `api_client.py`, `sdk_client.py`, `meta_ads_client.py`).
- `settings.py` — pydantic settings from env (see README for `SUPABASE_*` vars and the
  required `QUERY_API_KEY`).

### Safety system (central to this server)

`services/safety/safety_manager.py` is a singleton enforcing per-client safety modes.
Each client type (`DATABASE`, `API`, `META`) has a `SafetyMode` (defaults to `SAFE`)
and a `SafetyConfig` (`SQLSafetyConfig`, `APISafetyConfig`, `MetaSafetyConfig`). SQL ops
are classified three-tier (safe / write / destructive); risky operations raise
`ConfirmationRequiredError` and require a confirmation id (5-min expiry) before
execution. When adding mutating tools, route them through the safety manager rather
than bypassing it.

## Root-level helper scripts (not part of the MCP server)

- `meta_dashboard.py` — standalone stdlib HTTP dashboard over `MetaAdsClient`
  (`python meta_dashboard.py`, needs `META_*` env vars).
- `meta_restaurant_analysis.py` — CLI to analyze a Meta ad account and optionally
  create a campaign structure (`--create`, `--refresh-token`). Comments/output Arabic.
- `server/metaAds.ts` — a standalone TypeScript Meta Marketing API client template
  (reference, not wired into the Python server).

## Upstream status

The original project is no longer actively maintained upstream (Supabase shipped an
official MCP server). Treat the README's broad docs as upstream history; the Meta Ads
service and root scripts are this fork's additions.
