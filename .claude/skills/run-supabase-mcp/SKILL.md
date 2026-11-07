---
name: run-supabase-mcp
description: Build, run, and verify the Supabase MCP server (FastMCP over stdio, Python/uv) - live MCP handshake, every ToolName tool registered with its YAML description, the TheQuery.dev feature-access gate, and the SQL safety chain (safe mode, live_dangerously, confirm_destructive_operation) against a throwaway PostgreSQL. Use when asked to run, start, smoke-test, or verify the server or its tools.
---

FastMCP server (`supabase_mcp.main:run_server`) that talks JSON-RPC over
**stdio**. It has no HTTP port, no UI, and nothing to click. It is driven with
the official `mcp` client SDK plus the project's own `pytest` suite.
**The driver never uses real credentials and never connects to a real
database or external service.** See "Why driver.py is safe to run".

Paths below are relative to the repository root.

## Run (agent path): two layers

```bash
uv sync --all-groups                                       # once
uv run pytest -m "not integration" -q                      # layer 1: logic, in-process
uv run python .claude/skills/run-supabase-mcp/driver.py    # layer 2: the real server over stdio
```

**Layer 1, `pytest`**, covers the services in-process: the SQL validator and
risk levels, safety manager, settings validation, API and SDK clients with
mocks. It never starts the server or speaks MCP. The 80 `integration` tests are
deselected by default (see "Integration tests").

**Layer 2, `driver.py`**, covers what imports can't: that the installed entry
point boots as a real MCP server and that the guard chain behaves the same when
reached through the protocol. In order, it:

1. Starts a throwaway PostgreSQL cluster (initdb on a free port, temp dir).
2. Spawns `supabase-mcp-server` with an isolated env, cwd and HOME, then runs
   `initialize`.
3. Runs `tools/list`. Every `ToolName` value in `supabase_mcp/tools/manager.py`
   must be registered and serve exactly its text from
   `tools/descriptions/*.yaml`. A non-empty check would not be enough: FastMCP
   silently falls back to the function docstring. Verified by deleting one
   YAML entry, which fails the run.
4. Feature gate: `get_auth_admin_methods_spec` with access granted (returns the
   static spec), then again with access denied. The second call is refused
   before the tool body runs.
5. `get_auth_status`: every credential `missing`, `api_connection=unreachable`,
   `db_connection=healthy`.
6. Meta tools without `META_*`: a read tool returns "Meta Ads is not
   configured". A write tool is refused by the safety manager in SAFE mode.
7. SQL safety chain:
   - SAFE: `SELECT` is allowed; `CREATE TABLE` is refused and the table is not
     created.
   - `live_dangerously(database, True)`, then `CREATE` and `INSERT` work.
   - `DROP` returns a `conf_xxxxxxxx` ID and the table survives.
     `confirm_destructive_operation` with `user_confirmation=False` is refused;
     with `True` the DROP runs.
   - `retrieve_migrations` lists exactly the CREATE and DROP migrations.
   - Back to SAFE: `CREATE` is refused again.
8. Audit: N tool calls produced exactly N feature checks at the local stub, all
   with the configured key, and no other HTTP request.

Options:

- `--no-db` skips the SQL layer (step 7).
- `--require-db` fails instead of skipping when PostgreSQL is missing. Use it
  in CI.
- `--log-dir DIR` copies `mcp_server.log`, `server-stderr.log` and
  `postgres.log` out before the temp dirs are deleted.

Verified in this repo's cloud container on 2026-11-07:

- pytest: "216 passed, 80 deselected".
- Driver: "ALL CHECKS PASSED", with 38 tools and 21 tool calls / 21 feature
  checks, in about 5 s.
- `--no-db`: passes with "SQL safety chain SKIPPED", 5 calls.
- A failing check exits 1 and prints the server log tail.
- The driver passes ruff and mypy with the repo config.

## Why driver.py is safe to run

- **No configuration leaks in.** Settings come from env vars, then `.env` in
  the cwd, then `~/.config/supabase-mcp/.env` (`find_config_file` in
  `settings.py`). The subprocess gets a whitelisted env (PATH, LANG, plus the
  driver's own values), and both its cwd and HOME are empty temp dirs. Checked
  with a repo `.env`, a global `.env` and `SUPABASE_ACCESS_TOKEN` / `DB_URL` /
  `META_*` in the shell at once: the server still reported every credential
  `missing`.
- **No external HTTP.** `FeatureManager.execute_tool` asks TheQuery.dev
  (`GET {QUERY_API_URL}/features/<tool>/access`) before every tool.
  `QUERY_API_URL` and `SUPABASE_API_URL` point at a stub the driver serves on
  127.0.0.1. The Management API client refuses to send requests without
  `SUPABASE_ACCESS_TOKEN`, and the audit step fails if anything but feature
  checks reaches the stub. The driver never calls `get_management_api_spec`
  (see Gotchas).
- **No real database.** The SQL layer connects only to the cluster the driver
  just created (`SUPABASE_PROJECT_REF=127.0.0.1:<random port>`), never to 54322
  or any other existing server. The cluster and temp dirs are deleted at the
  end, pass or fail.
- **Nothing written to your home.** `ToolName` is parsed with `ast` instead of
  imported. Importing `supabase_mcp` creates `~/.local/share/supabase-mcp/`.

## Build

```bash
uv sync --all-groups
```

This is pure Python, with no compile step. The entry points
`supabase-mcp-server` and `supabase-mcp-inspector` come from
`[project.scripts]` in `pyproject.toml`.

## Run (human path)

```bash
uv run supabase-mcp-server      # blocks, speaking MCP on stdio; meant to be launched BY an MCP client
uv run supabase-mcp-inspector   # `mcp dev` inspector (not exercised by this skill)
```

Running it bare in a terminal is useless: it waits for JSON-RPC on stdin. For
real use, configure env vars or a `.env` from `.env.example` (never commit
it). Remote projects need `SUPABASE_PROJECT_REF`, `SUPABASE_DB_PASSWORD` (or
`DB_URL`) and `SUPABASE_REGION`. Management API tools need
`SUPABASE_ACCESS_TOKEN`, and Auth Admin tools need `SUPABASE_SERVICE_ROLE_KEY`.

## Tools (38 at last check, all registered unconditionally)

| Group | Tools | Needs |
|---|---|---|
| Database | `get_schemas`, `get_tables`, `get_table_schema`, `execute_postgresql`, `retrieve_migrations` | Postgres |
| Safety | `live_dangerously`, `confirm_destructive_operation` | - |
| Management API | `send_management_api_request`, `get_management_api_spec`, `retrieve_logs` | `SUPABASE_ACCESS_TOKEN` |
| Auth Admin | `get_auth_admin_methods_spec` (static), `call_auth_admin_method` | `SUPABASE_SERVICE_ROLE_KEY` |
| Status | `get_auth_status` | - |
| Meta Ads | 25 `meta_*` tools | `META_APP_ID`, `META_APP_SECRET`, `META_ACCESS_TOKEN`, `META_AD_ACCOUNT_ID(S)` |

SQL risk levels (`services/safety/safety_configs.py`):

- LOW (`SELECT`) always runs, in a read-only transaction in SAFE mode.
- MEDIUM (`INSERT`/`UPDATE`/`DELETE`, `CREATE`/`ALTER`) needs UNSAFE.
- HIGH (`DROP`, `TRUNCATE`) needs UNSAFE and a confirmation ID.

Schema changes are recorded in `supabase_migrations.schema_migrations`.

## Integration tests

`uv run pytest -m integration` needs `.env.test` (from `.env.test.example`), a
local Supabase stack (`supabase start`, Postgres on 127.0.0.1:54322), and
tokens for the API and SDK tests. This skill does not run them, and they are
not part of CI.

## Gotchas

- **Every tool depends on TheQuery.dev.** By default the server calls
  `https://api.thequery.dev/v1` with key `test-key` before each tool. If that
  host is unreachable (offline, or a sandbox that blocks it), every tool fails
  with "We couldn't verify access to '<tool>'…", even `SELECT 1`. The driver's
  stub is why it works offline.
- **Known bug: a final statement without `;` is silently skipped.**
  - libpg_query reports `stmt_len=0` for an unterminated last statement, and
    `SQLValidator` (`sql/validator.py`) slices `original_query[loc:loc+0]` to
    `''`.
  - `PostgresClient` then skips the empty statement, and the tool "succeeds"
    with `results=[]`.
  - Verified: `SELECT 1 AS ok` returns `results=[]`, and the validator yields
    `''` for `CREATE TABLE t (id int)` too.
  - The driver ends all its SQL with `;`. Its last line in step 7 reports the
    bug as a `WARNING` (not a failure) until it is fixed.
- **Known bug: two schema changes in the same second lose a migration record.**
  - The migration `version` is a `%Y%m%d%H%M%S` TEXT primary key
    (`migration_manager.py`, `init_migrations.sql`).
  - `QueryManager.handle_migration` only logs a failed insert, so the
    statement runs but its record is dropped (duplicate key in
    `postgres.log`).
  - The driver sleeps 1.1 s before the confirmed DROP for this reason.
- **A denied feature looks like an outage.** `FeatureAccessError` subclasses
  `APIError`, so `FeatureManager.check_feature_access` re-wraps it as
  `FeatureTemporaryError`. The client sees "We couldn't verify access…
  at the moment", not the Pro-plan message.
- **The `DROP TABLE` auto migration name is `drop_object_public_unknown`.**
  The validator does not extract `DropStmt` objects. Pass `migration_name` for
  a useful name.
- **`get_management_api_spec` fetches `https://api.supabase.com/api/v1-json`.**
  The URL is hardcoded in `spec_manager.py` and not overridable. The bundled
  spec is only the fallback, so the driver does not call this tool.
- **`serverInfo.version` is not this package's version.** It reports the
  `mcp` library's version (`1.27.0` at last check), because `FastMCP("supabase")`
  passes no app version.
- **Logs.** The server logs at DEBUG to `$HOME/.local/share/supabase-mcp/mcp_server.log`
  and via FastMCP's rich handler to stderr. Under the driver both land in temp
  dirs, so use `--log-dir` to keep them.
- **Root containers.** PostgreSQL refuses to run as root, so the driver runs
  initdb/pg_ctl via `runuser -u postgres`. Ubuntu keeps the binaries in
  `/usr/lib/postgresql/<ver>/bin`, off PATH; the driver also checks
  `pg_config --bindir` and the Homebrew paths.
- **`os._exit(0)` in `main.py`'s lifespan is intentional.** The server
  hard-exits when the client disconnects (see CLAUDE.md), so a fast exit after
  the session closes is expected.

## Troubleshooting

- **"entry point not found next to this interpreter"**: run
  `uv sync --all-groups`, then run the driver with `uv run python …` so it uses
  the project venv.
- **Hangs or fails at `initialize`**: rerun with `--log-dir /tmp/smcp-logs`
  and read `server-stderr.log`, which holds startup tracebacks. Don't run
  `uv run supabase-mcp-server` from the repo root to debug: it reads a `.env`
  there if one exists.
- **"SQL safety chain SKIPPED: no PostgreSQL binaries"**: install PostgreSQL
  (`apt-get install postgresql` or `brew install postgresql`). The Windows
  `.exe` layout isn't searched.
- **initdb/pg_ctl failed**: the message includes their output and the tail of
  `postgres.log`.
