#!/usr/bin/env python3
"""Protocol-level driver for the Supabase MCP server.

Spawns the real `supabase-mcp-server` entry point as a subprocess and speaks
real MCP (JSON-RPC over stdio) to it with the official `mcp` client SDK. The
unit suite (`uv run pytest -m "not integration"`) never does this: it imports
services in-process, so it cannot catch a server that fails to boot, a tool
that is not registered, or a tool that has no description.

Isolation, so the driver can never touch a real project or service:
  * The subprocess gets a whitelisted environment (no SUPABASE_*, DB_URL,
    QUERY_API_*, META_* or proxy variables from your shell), and both its
    working directory and HOME are fresh temp dirs, so neither a `.env` in
    the repo nor ~/.config/supabase-mcp/.env is ever read.
  * Every tool call first asks TheQuery.dev for feature access
    (FeatureManager.check_feature_access). QUERY_API_URL and SUPABASE_API_URL
    point at a stub HTTP server this driver runs on 127.0.0.1, which records
    every request it gets.
  * The SQL layer runs against a throwaway PostgreSQL cluster that this
    driver creates with initdb on a free port and deletes afterwards. It
    never connects to an existing database (not even a local Supabase stack
    on 54322). Without PostgreSQL binaries the SQL layer is reported as
    SKIPPED, or fails with --require-db.

Usage (from the repository root):
    uv run python .claude/skills/run-supabase-mcp/driver.py [--require-db]
"""

from __future__ import annotations

import argparse
import ast
import asyncio
import glob
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import traceback
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

REPO = Path(__file__).resolve().parents[3]
PG_PASSWORD = "postgres"  # same default the server assumes for local projects
STUB_KEY = "driver-local-stub"
CALL_TIMEOUT = timedelta(seconds=60)


class CheckFailed(Exception):
    pass


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailed(message)


def expected_tool_names() -> set[str]:
    """Read ToolName values from tools/manager.py without importing the package.

    Importing supabase_mcp creates a log file under the real ~/.local/share,
    so parse the enum with ast instead.
    """
    tree = ast.parse((REPO / "supabase_mcp" / "tools" / "manager.py").read_text())
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "ToolName":
            return {
                stmt.value.value
                for stmt in node.body
                if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Constant)
            }
    raise CheckFailed("ToolName enum not found in supabase_mcp/tools/manager.py")


def yaml_descriptions() -> dict[str, str]:
    """Load tools/descriptions/*.yaml the way ToolManager does (merged name -> text)."""
    import yaml  # type: ignore[import-untyped]  # runtime dep of the server; no stubs in the dev group

    merged: dict[str, str] = {}
    for path in sorted((REPO / "supabase_mcp" / "tools" / "descriptions").glob("*.yaml")):
        merged.update(yaml.safe_load(path.read_text()) or {})
    return merged


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def tail(path: Path, lines: int = 40) -> str:
    try:
        return "\n".join(path.read_text(errors="replace").splitlines()[-lines:])
    except OSError:
        return f"(no log at {path})"


# --------------------------------------------------------------------------- stub


class FeatureStub:
    """Local stand-in for TheQuery.dev (feature access) and the Management API."""

    def __init__(self) -> None:
        self.requests: list[tuple[str, str, str | None]] = []
        self.denied: set[str] = set()
        stub = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 (http.server API)
                stub.requests.append(("GET", self.path, self.headers.get("X-API-Key")))
                m = re.fullmatch(r"/v1/features/([\w-]+)/access", self.path)
                if m:
                    self._send(200, {"access_granted": m.group(1) not in stub.denied})
                else:
                    self._send(404, {"error": "not handled by the driver stub"})

            def do_POST(self) -> None:  # noqa: N802
                stub.requests.append(("POST", self.path, self.headers.get("X-API-Key")))
                self._send(404, {"error": "not handled by the driver stub"})

            def _send(self, status: int, body: dict[str, Any]) -> None:
                data = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args: Any) -> None:
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


# ----------------------------------------------------------------- throwaway postgres


def find_pg_bindir() -> Path | None:
    candidates: list[Path] = []
    for tool in ("pg_ctl", "initdb"):
        found = shutil.which(tool)
        if found:
            candidates.append(Path(found).parent)
    if shutil.which("pg_config"):
        out = subprocess.run(["pg_config", "--bindir"], capture_output=True, text=True)
        if out.returncode == 0:
            candidates.append(Path(out.stdout.strip()))
    by_version = sorted(glob.glob("/usr/lib/postgresql/*/bin"), key=lambda p: int(p.split("/")[-2]), reverse=True)
    candidates += [Path(p) for p in by_version]
    candidates += [Path(p) for p in sorted(glob.glob("/opt/homebrew/opt/postgresql*/bin"), reverse=True)]
    candidates += [Path(p) for p in sorted(glob.glob("/usr/local/opt/postgresql*/bin"), reverse=True)]
    for c in candidates:
        if (c / "initdb").exists() and (c / "pg_ctl").exists():
            return c
    return None


class ThrowawayPostgres:
    """initdb + pg_ctl in a temp dir on a free port; removed on stop()."""

    def __init__(self, bindir: Path) -> None:
        self.bindir = bindir
        self.prefix: list[str] = []
        self._owner: tuple[int, int] | None = None
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            # PostgreSQL refuses to run as root; hand the cluster to the postgres user.
            import pwd

            try:
                pw = pwd.getpwnam("postgres")
            except KeyError as e:
                raise RuntimeError("running as root and no 'postgres' OS user exists") from e
            if not shutil.which("runuser"):
                raise RuntimeError("running as root and `runuser` is not available")
            self.prefix = ["runuser", "-u", "postgres", "--"]
            self._owner = (pw.pw_uid, pw.pw_gid)
        self.dir = Path(tempfile.mkdtemp(prefix="supabase-mcp-driver-pg-"))
        if self._owner:
            os.chown(self.dir, *self._owner)
        self.data = self.dir / "data"
        self.log = self.dir / "postgres.log"
        self.port = free_port()

    def _run(self, *args: str) -> None:
        cmd = self.prefix + [str(self.bindir / args[0]), *args[1:]]
        out = subprocess.run(cmd, capture_output=True, text=True)
        if out.returncode != 0:
            raise RuntimeError(f"{args[0]} failed ({out.returncode}):\n{out.stdout}{out.stderr}\n{tail(self.log)}")

    def start(self) -> None:
        pwfile = self.dir / "pwfile"
        pwfile.write_text(PG_PASSWORD + "\n")
        pwfile.chmod(0o600)
        if self._owner:
            os.chown(pwfile, *self._owner)
        self._run(
            "initdb", "-D", str(self.data), "-U", "postgres", "--auth=scram-sha-256",
            f"--pwfile={pwfile}", "--no-locale", "-E", "UTF8", "--no-sync",
        )  # fmt: skip
        opts = f"-c listen_addresses=127.0.0.1 -p {self.port} -k {self.dir} -c fsync=off"
        self._run("pg_ctl", "-D", str(self.data), "-l", str(self.log), "-o", opts, "-w", "-t", "60", "start")

    def stop(self) -> None:
        if (self.data / "postmaster.pid").exists():
            subprocess.run(
                self.prefix + [str(self.bindir / "pg_ctl"), "-D", str(self.data), "-m", "immediate", "-w", "stop"],
                capture_output=True,
            )
        shutil.rmtree(self.dir, ignore_errors=True)


# ------------------------------------------------------------------------ helpers


def text_of(result: Any) -> str:
    return "".join(getattr(block, "text", "") for block in result.content)


def payload(result: Any) -> Any:
    data = result.structuredContent
    if data is None:
        data = json.loads(text_of(result))
    if isinstance(data, dict) and set(data) == {"result"}:
        data = data["result"]
    return data


class Session:
    """Wraps ClientSession to count tool calls (each one must hit the feature gate once)."""

    def __init__(self, session: ClientSession) -> None:
        self.session = session
        self.calls = 0

    async def call(self, name: str, args: dict[str, Any] | None = None) -> Any:
        self.calls += 1
        return await self.session.call_tool(name, args or {}, read_timeout_seconds=CALL_TIMEOUT)

    async def ok(self, name: str, args: dict[str, Any] | None = None) -> Any:
        result = await self.call(name, args)
        expect(not result.isError, f"{name} failed unexpectedly: {text_of(result)}")
        return payload(result)

    async def error(self, name: str, args: dict[str, Any] | None = None) -> str:
        result = await self.call(name, args)
        expect(result.isError, f"{name} should have been refused, got: {text_of(result)}")
        return text_of(result).removeprefix(f"Error executing tool {name}: ")

    async def sql_rows(self, query: str) -> list[dict[str, Any]]:
        data = await self.ok("execute_postgresql", {"query": query})
        expect(len(data["results"]) > 0, f"no statement results for {query!r}: {data}")
        rows: list[dict[str, Any]] = data["results"][-1]["rows"]
        return rows


# ------------------------------------------------------------------------- checks


async def check_protocol(s: Session, init: Any) -> None:
    print(f"    server: {init.serverInfo.name} {init.serverInfo.version}")
    print("==> tools/list")
    tools = (await s.session.list_tools()).tools
    names = {t.name for t in tools}
    expected = expected_tool_names()
    missing = expected - names
    expect(not missing, f"tools in ToolName but not registered: {sorted(missing)}")
    # FastMCP silently falls back to the function docstring when description="", so compare
    # against the YAML files rather than just checking for a non-empty description.
    yaml_desc = yaml_descriptions()
    no_yaml = sorted(n for n in expected if not (yaml_desc.get(n) or "").strip())
    expect(not no_yaml, f"ToolName values without an entry in tools/descriptions/*.yaml: {no_yaml}")
    served = {t.name: (t.description or "").strip() for t in tools}
    mismatched = sorted(n for n in expected if served[n] != yaml_desc[n].strip())
    expect(not mismatched, f"tools not serving their YAML description: {mismatched}")
    extra = sorted(names - expected)
    print(f"    {len(names)} tools registered, all {len(expected)} ToolName values serve their YAML description")
    if extra:
        print(f"    note: registered but not in ToolName: {extra}")


async def check_feature_gate(s: Session, stub: FeatureStub) -> None:
    print("==> feature-access gate (TheQuery.dev stub on 127.0.0.1)")
    spec = await s.ok("get_auth_admin_methods_spec")
    expect(isinstance(spec, dict) and len(spec) > 0, f"expected a non-empty Auth Admin spec, got: {spec!r}")
    print(f"    access granted -> get_auth_admin_methods_spec returned {len(spec)} methods (static data, no network)")
    stub.denied.add("get_auth_admin_methods_spec")
    message = await s.error("get_auth_admin_methods_spec")
    stub.denied.discard("get_auth_admin_methods_spec")
    print(f"    access denied  -> refused before the tool body ran: {message.splitlines()[0][:80]}")


async def check_auth_status(s: Session, db: bool) -> None:
    print("==> get_auth_status (no credentials configured)")
    status = await s.ok("get_auth_status")
    for key in ("personal_access_token", "service_role_key", "supabase_url", "db_url"):
        expect(status.get(key) == "missing", f"{key} should be 'missing', got {status.get(key)!r}")
    expect(status.get("api_connection") == "unreachable", f"api_connection should be 'unreachable': {status}")
    want_db = "healthy" if db else "unreachable"
    expect(status.get("db_connection") == want_db, f"db_connection should be {want_db!r}: {status}")
    print(f"    all credentials missing, api_connection=unreachable, db_connection={want_db}")


async def check_meta_unconfigured(s: Session) -> None:
    print("==> Meta tools without META_* credentials")
    message = await s.error("meta_get_account_info")
    expect("Meta Ads is not configured" in message, f"unexpected meta read error: {message}")
    print("    read tool  -> 'Meta Ads is not configured' (no Graph API client exists)")
    campaign = {"name": "driver-smoke", "objective": "OUTCOME_TRAFFIC"}
    message = await s.error("meta_create_campaign", {"campaign": campaign})
    expect("not allowed" in message.lower(), f"SAFE mode should refuse a meta write: {message}")
    print("    write tool -> blocked by the safety manager in SAFE mode, before the config check")


async def check_sql_safety_chain(s: Session) -> None:
    # Every statement ends with ';' on purpose: see the probe at the end of this function.
    table = "public.driver_smoke"
    exists = f"SELECT to_regclass('{table}') IS NOT NULL AS present;"

    print("==> SQL safety chain against the throwaway PostgreSQL cluster")
    rows = await s.sql_rows("SELECT 1 AS ok;")
    expect(rows == [{"ok": 1}], f"SELECT 1 returned {rows}")
    print("    SAFE   SELECT 1                    -> allowed (read-only transaction)")

    create = f"CREATE TABLE {table} (id int PRIMARY KEY, note text);"
    message = await s.error("execute_postgresql", {"query": create})
    expect((await s.sql_rows(exists)) == [{"present": False}], "table exists although CREATE was refused")
    print(f"    SAFE   CREATE TABLE                -> refused, table not created: {message.splitlines()[0][:70]}")

    mode = await s.ok("live_dangerously", {"service": "database", "enable_unsafe_mode": True})
    expect(mode.get("mode") == "unsafe", f"live_dangerously did not switch to unsafe: {mode}")
    print("    live_dangerously(database, True)   -> mode=unsafe")

    await s.ok("execute_postgresql", {"query": create, "migration_name": "driver_smoke_create"})
    await s.ok("execute_postgresql", {"query": f"INSERT INTO {table} VALUES (1, 'hello');"})
    rows = await s.sql_rows(f"SELECT note FROM {table};")
    expect(rows == [{"note": "hello"}], f"unexpected rows after INSERT: {rows}")
    print("    UNSAFE CREATE TABLE + INSERT       -> allowed, row reads back")

    message = await s.error("execute_postgresql", {"query": f"DROP TABLE {table};"})
    m = re.search(r"conf_[0-9a-f]{8}", message)
    if m is None:
        raise CheckFailed(f"DROP should return a confirmation id: {message}")
    conf_id = m.group(0)
    expect((await s.sql_rows(exists)) == [{"present": True}], "table vanished before confirmation")
    print(f"    UNSAFE DROP TABLE                  -> held for confirmation ({conf_id}), table still there")

    args = {"operation_type": "database", "confirmation_id": conf_id, "user_confirmation": False}
    await s.error("confirm_destructive_operation", args)
    print("    confirm(user_confirmation=False)   -> refused")
    # Migration versions are %Y%m%d%H%M%S text primary keys and a failed migration insert
    # is only logged, so a second schema change in the same second loses its record.
    await asyncio.sleep(1.1)
    await s.ok("confirm_destructive_operation", {**args, "user_confirmation": True})
    expect((await s.sql_rows(exists)) == [{"present": False}], "table still exists after confirmed DROP")
    print("    confirm(user_confirmation=True)    -> DROP executed, table gone")

    # Fresh cluster, so exactly the two schema changes above are recorded. The DROP's
    # auto-generated name doesn't contain the table name, hence no name_pattern filter.
    data = await s.ok("retrieve_migrations")
    names = sorted(row.get("name") for row in data["results"][-1]["rows"])
    expect(len(names) == 2 and "driver_smoke_create" in names, f"expected the CREATE and DROP migrations: {names}")
    print(f"    retrieve_migrations                -> {names}")

    mode = await s.ok("live_dangerously", {"service": "database", "enable_unsafe_mode": False})
    expect(mode.get("mode") == "safe", f"live_dangerously did not switch back to safe: {mode}")
    await s.error("execute_postgresql", {"query": create})
    print("    live_dangerously(database, False)  -> mode=safe, CREATE refused again")

    # Known bug probe (reported, not failed): when the last statement has no trailing ';',
    # libpg_query gives stmt_len=0 and SQLValidator slices it to '' (sql/validator.py),
    # so PostgresClient skips it and the tool "succeeds" with results=[].
    data = await s.ok("execute_postgresql", {"query": "SELECT 1 AS ok"})
    if data["results"] == []:
        print("    WARNING known bug: 'SELECT 1 AS ok' without ';' returned results=[] (statement skipped)")
    else:
        print("    'SELECT 1 AS ok' without ';' now returns rows: the stmt_len=0 bug is fixed, drop this probe")


def check_stub_audit(stub: FeatureStub, calls: int) -> None:
    print("==> outbound request audit")
    others = [r for r in stub.requests if not re.fullmatch(r"/v1/features/[\w-]+/access", r[1])]
    expect(not others, f"server made requests other than feature checks: {others}")
    expect(len(stub.requests) == calls, f"{calls} tool calls but {len(stub.requests)} feature checks")
    expect(all(r[2] == STUB_KEY for r in stub.requests), "a feature check was sent without the configured API key")
    print(f"    {calls} tool calls -> exactly {calls} feature checks to the stub, no other HTTP requests")


# --------------------------------------------------------------------------- main


async def run(args: argparse.Namespace) -> int:
    server_bin = shutil.which("supabase-mcp-server", path=str(Path(sys.executable).parent))
    if not server_bin:
        print("FAILED: supabase-mcp-server entry point not found next to this interpreter; run `uv sync --all-groups`")
        return 1

    work = Path(tempfile.mkdtemp(prefix="supabase-mcp-driver-"))
    stub = FeatureStub()
    pg: ThrowawayPostgres | None = None
    skip_reason = None
    server_log = work / ".local" / "share" / "supabase-mcp" / "mcp_server.log"  # logger.py writes under $HOME
    stderr_log = work / "server-stderr.log"
    try:
        bindir = None if args.no_db else find_pg_bindir()
        if args.no_db:
            skip_reason = "--no-db given"
        elif bindir is None:
            skip_reason = "no PostgreSQL binaries (initdb/pg_ctl) found"
        else:
            print(f"==> starting a throwaway PostgreSQL cluster ({bindir})")
            try:
                pg = ThrowawayPostgres(bindir)
            except RuntimeError as e:
                skip_reason = str(e)
            else:
                pg.start()
                print(f"    listening on 127.0.0.1:{pg.port}, data in {pg.dir}")
        if skip_reason and args.require_db:
            print(f"FAILED: --require-db given but {skip_reason}")
            return 1

        env = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": str(work),
            "LANG": os.environ.get("LANG", "C.UTF-8"),
            "COLUMNS": "200",  # FastMCP's rich log handler wraps stderr at 80 columns otherwise
            "SUPABASE_PROJECT_REF": f"127.0.0.1:{pg.port if pg else free_port()}",
            "SUPABASE_DB_PASSWORD": PG_PASSWORD,
            "QUERY_API_URL": f"http://127.0.0.1:{stub.port}/v1",
            "QUERY_API_KEY": STUB_KEY,
            "SUPABASE_API_URL": f"http://127.0.0.1:{stub.port}",
        }
        params = StdioServerParameters(command=server_bin, args=[], env=env, cwd=str(work))

        print("==> spawning supabase-mcp-server (isolated env, cwd and HOME) and performing MCP initialize")
        with open(stderr_log, "w") as errlog:
            async with asyncio.timeout(300):
                async with stdio_client(params, errlog=errlog) as (read, write):
                    async with ClientSession(read, write) as client:
                        s = Session(client)
                        await check_protocol(s, await client.initialize())
                        await check_feature_gate(s, stub)
                        await check_auth_status(s, db=pg is not None)
                        await check_meta_unconfigured(s)
                        if pg:
                            await check_sql_safety_chain(s)
                        check_stub_audit(stub, s.calls)
    except Exception as e:
        # anyio wraps anything raised inside the MCP session in (nested) ExceptionGroups.
        err: BaseException = e
        while isinstance(err, BaseExceptionGroup) and len(err.exceptions) == 1:
            err = err.exceptions[0]
        if isinstance(err, CheckFailed | RuntimeError):  # RuntimeError: initdb/pg_ctl, output included
            print(f"FAILED: {err}")
        else:
            print("FAILED with an unexpected error:")
            traceback.print_exception(err)
        print(f"---- server log, tail ({server_log.name}) ----\n{tail(server_log, 30)}")
        print(f"---- server stderr, tail ----\n{tail(stderr_log, 15)}")
        return 1
    finally:
        stub.close()
        if args.log_dir:
            args.log_dir.mkdir(parents=True, exist_ok=True)
            for log in (server_log, stderr_log, *([pg.log] if pg else [])):
                if log.exists():
                    shutil.copy(log, args.log_dir / log.name)
            print(f"    logs copied to {args.log_dir}")
        if pg:
            pg.stop()
        shutil.rmtree(work, ignore_errors=True)

    if skip_reason:
        print(f"ALL CHECKS PASSED (SQL safety chain SKIPPED: {skip_reason})")
    else:
        print("ALL CHECKS PASSED")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    db = parser.add_mutually_exclusive_group()
    db.add_argument("--require-db", action="store_true", help="fail instead of skipping the SQL layer")
    db.add_argument("--no-db", action="store_true", help="skip the SQL layer even if PostgreSQL is installed")
    parser.add_argument("--log-dir", type=Path, help="copy the server and PostgreSQL logs here before cleanup")
    return asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
