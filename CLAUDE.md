# CLAUDE.md

Guidance for AI assistants (Claude Code and others) working in this repository.

## What this is

`supabase-mcp-server` is a Python MCP (Model Context Protocol) server that lets
AI tools (Cursor, Windsurf, Claude, Cline, etc.) manage a Supabase project
end-to-end: run SQL, inspect schemas, call the Management API, manage Auth,
read logs, apply migrations, and (via an extra integration) manage Meta/Facebook
Ads campaigns. It's distributed on PyPI and run via `pipx`/`uvx`/Docker as a
stdio MCP server.

- Package name: `supabase-mcp-server`, importable as `supabase_mcp`
- Python: `>=3.12`
- Build backend: `hatchling` + `hatch-vcs` (version derived from git tags into `supabase_mcp/_version.py`)
- License: Apache-2.0

## Architecture

Layered, dependency-injected design — read top to bottom for the request flow:

```
FastMCP server (supabase_mcp/main.py)
    -> ToolRegistry (tools/registry.py)        registers ~60 MCP tools on the FastMCP app
    -> FeatureManager (core/feature_manager.py) routes tool calls to the right service
    -> ServicesContainer (core/container.py)    singleton DI container, owns service lifecycles
    -> Services (services/*)                    domain business logic
    -> Clients (clients/*)                      thin wrappers around external HTTP/DB APIs
```

Key modules:
- `supabase_mcp/main.py` — FastMCP app + `lifespan` context manager that
  initializes/shuts down the `ServicesContainer` and registers tools. Exposes
  the `run_server` / `run_inspector` entry points. Note the intentional
  `os._exit(0)` in the lifespan teardown — it hard-kills the process to avoid
  the MCP stdio transport hanging on shutdown; don't "fix" this without
  understanding why it's there.
- `supabase_mcp/settings.py` — Pydantic `BaseSettings` for all configuration
  (Supabase project ref, DB password, region, API keys, etc.)
- `supabase_mcp/logger.py`, `exceptions.py` — shared logging setup and custom exceptions

### `clients/` — external API/DB wrappers
`base_http_client.py`, `management_client.py` (Supabase Management API),
`sdk_client.py` (official `supabase` SDK), `api_client.py` (TheQuery.dev API),
`meta_ads_client.py` (Meta/Facebook Ads API).

### `core/` — orchestration
`container.py` (`ServicesContainer` singleton DI), `feature_manager.py`
(routes a tool invocation to the owning service).

### `services/` — domain logic, one subpackage per domain
- `database/` — Postgres connectivity & SQL execution: `postgres_client.py`
  (asyncpg pooling), `query_manager.py`, `migration_manager.py`, plus
  `sql/` (loader, validator, models) and `sql/queries/*.sql` (schema/table/
  migration/log queries loaded from disk, not inlined in Python)
- `api/` — Supabase Management API interaction: `api_manager.py`, `spec_manager.py`
- `safety/` — guards around destructive operations: `safety_manager.py`,
  `safety_configs.py`, `models.py` (this is what backs the
  `live_dangerously` / `confirm_destructive_operation` tools — see Safety below)
- `logs/` — `log_manager.py` for retrieving project logs
- `sdk/` — Auth Admin SDK spec/models (`auth_admin_sdk_spec.py`, `auth_admin_models.py`)
- `meta_ads/` — Meta/Facebook Ads campaign tools (`campaign_manager.py`, `models.py`)

### `tools/` — MCP tool surface
- `registry.py` — wires tools onto the FastMCP server
- `manager.py` — `ToolName` enum and tool descriptions (the canonical list of
  ~60 exposed tools: schema/table inspection, `execute_postgresql`,
  `retrieve_migrations`, `live_dangerously`, `confirm_destructive_operation`,
  `send_management_api_request`, `get_management_api_spec`,
  `get_auth_admin_methods_spec`, `call_auth_admin_method`, `retrieve_logs`,
  `meta_list_*` / `meta_create_*` campaign tools, etc.)
- `descriptions/` — YAML files documenting each tool for the MCP client

### Other top-level items
- `server/` — a standalone `metaAds.ts` example/reference file (not part of the Python package)
- `meta_dashboard.py`, `meta_restaurant_analysis.py` — standalone analysis/dashboard scripts, not part of the MCP server package
- `llms-full.txt` — bundled reference docs (large; don't read it wholesale)

## Safety model (important when touching `services/safety/` or DB tools)

Destructive SQL operations (DDL/DML that can alter or delete data) are blocked
by default. A user must explicitly call the `live_dangerously` tool to enable
write mode, and certain operations additionally require
`confirm_destructive_operation` before they execute. When working on anything
in `services/database/` or `services/safety/`, preserve this guardrail —
it's a deliberate safety feature, not an inconvenience to route around.

## Configuration

Settings are loaded via Pydantic `BaseSettings` (see `supabase_mcp/settings.py`
and `.env.example`):

Required for remote projects:
- `SUPABASE_PROJECT_REF`, `SUPABASE_DB_PASSWORD`, `SUPABASE_REGION`, `QUERY_API_KEY`

Optional:
- `SUPABASE_ACCESS_TOKEN` (Management API), `SUPABASE_SERVICE_ROLE_KEY`,
  `DB_URL`, `SUPABASE_URL`

For local development against the Supabase CLI stack, `.env.test.example`
defaults to `SUPABASE_PROJECT_REF=127.0.0.1:54322` with password `postgres`.

## Development workflow

This repo uses [`uv`](https://docs.astral.sh/uv/) for dependency management.

```bash
uv sync --all-groups                 # install runtime + dev dependencies
uv run supabase-mcp-server           # run the server (stdio MCP transport)
uv run supabase-mcp-inspector        # run with the MCP inspector (mcp dev)
```

### Tests

```bash
uv run pytest -m "not integration"                           # unit tests (default in CI)
uv run pytest -m "not integration" --cov=supabase_mcp        # with coverage
uv run pytest -m integration                                  # integration tests (need a local Supabase DB / .env.test)
```

- Test layout mirrors `supabase_mcp/services/*` under `tests/services/...`,
  plus a top-level `tests/conftest.py` with shared fixtures (e.g.
  `clean_environment`, `settings_integration`, `mock_validator`).
- Pytest is configured with `asyncio_mode = "auto"` — async test functions
  don't need `@pytest.mark.asyncio`.
- Mark integration tests (anything touching a real Postgres connection or
  external API) with `@pytest.mark.integration`; they're excluded by default
  via `addopts = "-m 'not integration'"`.

### Linting, formatting, typing

```bash
uv run ruff check . --fix            # lint (pycodestyle, pyflakes, isort, bugbear, comprehensions, pyupgrade)
uv run ruff format .                 # format (double quotes, 4-space indent, line length 120)
uv run mypy                          # strict type checking (relaxed for tests/)
uv run sqlfluff lint supabase_mcp/services/database/sql/queries   # SQL linting (postgres dialect)
```

These all run via `pre-commit` (`.pre-commit-config.yaml`), which also checks
for private keys, merge conflicts, AST/TOML validity, and runs `pytest` and
`uv build` before push. Run `pre-commit install` once locally so hooks fire
automatically.

`mypy` runs in `strict = true` mode for `supabase_mcp/*` (untyped defs,
incomplete defs, etc. are errors); the `tests.*` override relaxes those same
checks for test code.

## Conventions

- **Async-first**: the DB layer uses `asyncpg` with connection pooling; the
  server and services are built around `asyncio`/FastMCP. Prefer `async def`
  and non-blocking I/O when extending services/clients.
- **Strict typing**: add type hints to all new functions in `supabase_mcp/*`
  (mypy strict will fail CI otherwise). Tests can be more relaxed.
- **SQL lives in files**: query text belongs in
  `services/database/sql/queries/*.sql`, loaded via `sql/loader.py` —
  don't inline large SQL strings in Python.
- **Formatting**: double-quoted strings, 4-space indentation, 120-char line
  length (enforced by `ruff format` / `ruff check`).
- **New tools**: add the tool to the `ToolName` enum and description in
  `tools/manager.py`, register it in `tools/registry.py`, document it in
  `tools/descriptions/`, and route it through the appropriate service via
  `core/feature_manager.py` — don't bypass the container/service layering by
  calling clients directly from tool handlers.

## Contributing process (see `CONTRIBUTING.MD`)

This project requires opening a **GitHub Discussion before writing code** —
PRs without prior discussion/approval are auto-closed. When asked to
implement a feature here (as opposed to a bug fix), mention this requirement
to the user rather than assuming a PR will be accepted outright. All
contributions must include tests and documentation updates, follow existing
code style (ruff/mypy enforced), and use clear commit messages
(`feat: ...`, `fix: ...` style).

## CI/CD (`.github/workflows/`)

- `ci.yml` — on push/PR to `main` (and manual): runs unit tests
  (`pytest -m "not integration"` with coverage) and ruff lint/format checks
- `publish.yaml` — on GitHub Release: builds the wheel with `uv` and publishes
  to PyPI via trusted publishing
- `codeql.yml` — CodeQL security scanning on push/PR to `main` and a weekly schedule
- `sonarqube.yml` — SonarQube code-quality analysis

## Packaging & deployment

- `Dockerfile` — Python 3.12-slim-bookworm image that `pipx install`s
  `supabase-mcp-server` from PyPI and runs it as the entrypoint
- `smithery.yaml` — Smithery packaging manifest; declares the stdio MCP start
  command and the required/optional config schema
  (`queryApiKey`, `supabaseProjectRef`, `supabaseDbPassword`, `supabaseRegion`,
  optionally `supabaseAccessToken`, `supabaseServiceRoleKey`)
