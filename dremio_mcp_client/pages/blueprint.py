import json
import os
import re
import threading
from collections.abc import Mapping, Sequence
from shutil import which

from flask import Blueprint, current_app, jsonify, render_template, request
from mcp.client.stdio import StdioServerParameters

from ..mcp_bridge import MCPBridge

pages = Blueprint(
    "pages",
    __name__,
    template_folder="templates/pages",  # looks in DREMIO_MCP_CLIENT/pages/templates/
    static_folder="static",  # optional, if you add css/js later
)

# --- Lazy, threadsafe bridge singleton ---------------------------------------
_bridge = None
_bridge_lock = threading.Lock()

# pages.py (add near top)
from ..dremio_api import DremioClient

_dclient = None
_dclient_lock = threading.Lock()


def get_dremio_client() -> DremioClient:
    global _dclient
    if _dclient is None:
        with _dclient_lock:
            if _dclient is None:
                base = os.getenv("DREMIO_URL")
                token = os.getenv("DREMIO_TOKEN")
                scheme = os.getenv("DREMIO_AUTH_SCHEME")  # optional
                client = DremioClient(base_url=base, token=token, auth_scheme=scheme)
                _dclient = client
                current_app.logger.info("Dremio REST client initialized.")
    return _dclient


try:
    # If TextContent is importable:
    from some_module import TextContent
except Exception:
    TextContent = tuple()  # harmless fallback so isinstance() never matches


def to_jsonable(obj):
    # Handle Dremio MCP/Anthropic-style content wrappers
    if isinstance(obj, TextContent):
        # Keep only what you need; parse inner JSON if the text looks like JSON
        text = getattr(obj, "text", None) or getattr(obj, "content", None)
        try:
            return json.loads(text)
        except Exception:
            return {
                "type": getattr(obj, "type", "text"),
                "text": text,
            }
    # Pydantic models?
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    # dataclasses?
    if hasattr(obj, "__dataclass_fields__"):
        from dataclasses import asdict

        return asdict(obj)
    # Mappings
    if isinstance(obj, Mapping):
        return {k: to_jsonable(v) for k, v in obj.items()}
    # Sequences (but not str/bytes)
    if isinstance(obj, Sequence) and not isinstance(obj, (str, bytes, bytearray)):
        return [to_jsonable(v) for v in obj]
    # Fallback: primitive or stringified
    return obj


def _build_server_params() -> StdioServerParameters:
    mcp_dir = os.getenv("DREMIO_MCP_DIR")  # dremio-mcp repo root
    mcp_cfg = os.getenv("DREMIO_MCP_CFG")  # optional config.yaml
    if not mcp_dir:
        raise SystemExit("Set DREMIO_MCP_DIR to the cloned dremio-mcp repo path")

    # Ensure `uv` is resolvable (Claude-style launcher). Allow override.
    uv_bin = os.getenv("UV_BIN") or which("uv")
    if not uv_bin:
        raise SystemExit(
            "Could not find `uv` in PATH. Set UV_BIN to the full path or install uv."
        )

    args = ["run", "--directory", mcp_dir, "dremio-mcp-server", "run"]
    if mcp_cfg:
        args += ["--config-file", mcp_cfg]

    return StdioServerParameters(command=uv_bin, args=args, env=None)


def get_bridge() -> MCPBridge:
    global _bridge
    if _bridge is None:
        with _bridge_lock:
            if _bridge is None:
                params = _build_server_params()
                print(params)
                b = MCPBridge(params)
                b.connect()
                _bridge = b
                if b is None:
                    current_app.logger.info("Dremio MCP bridge failed to connect.")
                else:
                    current_app.logger.info("Dremio MCP bridge connected.")
    return _bridge


# --- Routes -------------------------------------------------------------------


@pages.get("/")
def index():
    # Simple chat UI
    return render_template("chat.html")


@pages.get("/health")
def health():
    bridge = get_bridge()
    tools = bridge.list_tools()
    print(tools)
    return jsonify({"status": "ok", "tools": [t["name"] for t in tools]})


@pages.post("/ask")
def ask():
    bridge = get_bridge()
    data = request.get_json(force=True, silent=True) or {}
    q = (data.get("q") or "").strip()
    if not q:
        return jsonify({"error": "missing 'q'"}), 400

    try:
        result = bridge.process_query(q)  # {"answer": "...", "trace": [...]}
        safe = to_jsonable(result)
        return jsonify(safe)
    except Exception as e:
        current_app.logger.exception("MCP ask failed")
        return jsonify({"error": str(e)}), 500


@pages.get("/views")
def list_views_route():
    try:
        client = get_dremio_client()
        views = client.list_views()
        return jsonify({"data": views, "count": len(views)})
    except Exception as e:
        current_app.logger.exception("Failed to list views")
        return jsonify({"error": str(e)}), 500


@pages.post("/views/preview")
def preview_view():
    """
    Body can be:
      { "id": "<catalog-id>", "limit": 100 }
      or
      { "path": ["IIDS","my_view"], "limit": 100 }
      or
      { "path_str": "IIDS.my_view", "limit": 100 }
    Returns: { columns:[{name,type}], rows:[{col:value,...}], jobId }
    """
    data = request.get_json(force=True, silent=True) or {}
    limit = int(data.get("limit") or 100)

    c = get_dremio_client()

    # Resolve path parts
    path_parts = None
    if "path" in data and isinstance(data["path"], list):
        path_parts = data["path"]
    elif "path_str" in data and isinstance(data["path_str"], str):
        path_parts = data["path_str"].split(".")
    elif "id" in data:
        ent = c.get_entity(data["id"])
        path_parts = ent.get("fullPathList") or ent.get("path")

    if not path_parts:
        return jsonify({"error": "Provide id, path, or path_str"}), 400

    ident = c.quote_identifier(path_parts)
    sql = f"SELECT * FROM {ident} LIMIT {limit}"

    job_id = c.run_sql(sql)
    job = c.wait_for_job(job_id, timeout_s=60.0)

    state = (job.get("jobState") or job.get("state") or "").upper()
    if state != "COMPLETED":
        return jsonify(
            {"error": f"Job {job_id} ended in state {state}", "jobId": job_id}
        ), 500

    res = c.get_job_results(job_id, offset=0, limit=limit)

    # Normalize columns/rows
    schema = res.get("schema") or []
    rows = res.get("rows") or []

    columns = [{"name": col.get("name"), "type": col.get("type")} for col in schema]

    return jsonify(
        {
            "jobId": job_id,
            "columns": columns,
            "rows": rows,  # already a list of {col: value}
            "rowCount": res.get("rowCount"),
        }
    )


_SQL_SELECT_RE = re.compile(r"^\s*select\b", re.IGNORECASE | re.DOTALL)
_SQL_LIMIT_RE = re.compile(r"\blimit\s+\d+\b", re.IGNORECASE)


def _ensure_limit(sql: str, default_limit: int, max_limit: int) -> str:
    """
    If the user didn't provide LIMIT, append one.
    If they did, cap it at max_limit by wrapping the query.
    """
    if not _SQL_LIMIT_RE.search(sql):
        return f"{sql.rstrip().rstrip(';')} LIMIT {default_limit}"
    # If the query already has LIMIT, we keep it; Dremio results will still
    # be paged by offset/limit on /job/{id}/results below. If you want to
    # hard-cap, you can wrap, but usually paging is enough.
    return sql


@pages.post("/sql/run")
def run_sql_endpoint():
    """
    Body: { "sql": "<SELECT ...>", "limit": 200, "offset": 0 }
    Returns: { jobId, columns:[{name,type}], rows:[{...}], rowCount }
    """
    data = request.get_json(force=True, silent=True) or {}
    sql = (data.get("sql") or "").strip()
    if not sql:
        return jsonify({"error": "Provide 'sql'"}), 400

    # --- Configurable bounds ---
    DEFAULT_LIMIT = int(data.get("limit") or 200)
    OFFSET = int(data.get("offset") or 0)
    MAX_LIMIT = int(current_app.config.get("SQL_RUN_MAX_LIMIT", 5000))
    ENFORCE_SELECT_ONLY = bool(current_app.config.get("SQL_RUN_SELECT_ONLY", True))

    # --- Safety: single SELECT only (by default) ---
    # Reject multiple statements and non-SELECT commands unless explicitly allowed.
    if ENFORCE_SELECT_ONLY:
        # crude multi-statement check — you can replace with a proper SQL parser if needed
        if ";" in sql.strip().rstrip(";"):
            return jsonify({"error": "Multiple statements are not allowed."}), 400
        if not _SQL_SELECT_RE.match(sql):
            return jsonify({"error": "Only SELECT queries are allowed."}), 400

    # Append LIMIT if missing (bounded by DEFAULT_LIMIT)
    effective_limit = min(DEFAULT_LIMIT, MAX_LIMIT)
    sql_to_run = _ensure_limit(sql, effective_limit, MAX_LIMIT)

    c = get_dremio_client()

    try:
        job_id = c.run_sql(sql_to_run)
        job = c.wait_for_job(
            job_id, timeout_s=float(current_app.config.get("SQL_RUN_TIMEOUT_S", 60.0))
        )
    except TimeoutError as te:
        return jsonify({"error": str(te)}), 504
    except Exception as e:
        return jsonify({"error": f"Failed to start or wait for job: {e}"}), 500

    state = (job.get("jobState") or job.get("state") or "").upper()
    if state != "COMPLETED":
        return jsonify(
            {"error": f"Job {job_id} ended in state {state}", "jobId": job_id}
        ), 500

    try:
        res = c.get_job_results(job_id, offset=OFFSET, limit=effective_limit)
    except Exception as e:
        return jsonify({"error": f"Failed to fetch results: {e}", "jobId": job_id}), 500

    schema = res.get("schema") or []
    rows = res.get("rows") or []

    columns = [{"name": col.get("name"), "type": col.get("type")} for col in schema]

    return jsonify(
        {
            "jobId": job_id,
            "sql": sql,  # original (unmodified) SQL for reference
            "columns": columns,
            "rows": rows,
            "rowCount": res.get("rowCount"),  # total rows in result set (if provided)
            "offset": OFFSET,
            "limit": effective_limit,
        }
    )


_SQL_SELECT_RE = re.compile(r"^\s*select\b", re.IGNORECASE | re.DOTALL)


@pages.post("/views/create")
def create_view():
    """
    Create (or replace) a Dremio view.

    Body can be:
      {
        "path": ["SpaceOrCatalog","Folder","ViewName"],   // or
        "path_str": "SpaceOrCatalog.Folder.ViewName",
        "sql": "SELECT ...",                               // the SELECT that defines the view
        "or_replace": true,                                // default true
        "use_catalog_api": false,                          // default false -> use SQL route
        "sql_context": ["Samples","samples.dremio.com"]    // optional; Catalog API only
      }

    Returns: { ok, id?, path, path_str, jobId?, method: "sql"|"catalog" }
    """
    data = request.get_json(force=True, silent=True) or {}

    # --- Resolve path ---
    path_parts = None
    if "path" in data and isinstance(data["path"], list):
        path_parts = data["path"]
    elif "path_str" in data and isinstance(data["path_str"], str):
        path_parts = [p for p in data["path_str"].split(".") if p]

    if not path_parts or len(path_parts) < 1:
        return jsonify(
            {"error": "Provide 'path' (array) or 'path_str' (dot-separated)."}
        ), 400

    select_sql = (data.get("sql") or "").strip()
    if not select_sql:
        return jsonify({"error": "Provide 'sql' (a single SELECT statement)."}), 400

    # Basic safety: single SELECT only (user can pass CREATE VIEW if you want, but we keep UX simple)
    if ";" in select_sql.strip().rstrip(";"):
        return jsonify({"error": "Multiple statements are not allowed in 'sql'."}), 400
    if not _SQL_SELECT_RE.match(select_sql):
        return jsonify({"error": "The 'sql' must be a SELECT statement."}), 400

    or_replace = bool(data.get("or_replace", True))
    use_catalog_api = bool(data.get("use_catalog_api", False))
    sql_context = data.get("sql_context")  # optional, array of strings

    c = get_dremio_client()

    try:
        if use_catalog_api:
            # Pure REST Catalog path
            ent = c.create_view_catalog(
                path_parts=path_parts,
                select_sql=select_sql,
                sql_context=sql_context,
                or_replace=or_replace,
            )
            # The Catalog API returns the entity; normalize minimal response
            parts = ent.get("path") or path_parts
            return jsonify(
                {
                    "ok": True,
                    "method": "catalog",
                    "id": ent.get("id"),
                    "path": parts,
                    "path_str": ".".join(parts),
                    "tag": ent.get("tag"),
                    "type": ent.get("type"),
                }
            )
        else:
            # SQL path: CREATE [OR REPLACE] VIEW "<p0>"."<p1>"... AS <SELECT ...>
            job_id = c.create_view_sql(
                path_parts=path_parts, select_sql=select_sql, or_replace=or_replace
            )
            # Optionally wait for job to finish (usually instantaneous)
            job = c.wait_for_job(
                job_id,
                timeout_s=float(current_app.config.get("SQL_RUN_TIMEOUT_S", 60.0)),
            )
            state = (job.get("jobState") or job.get("state") or "").upper()
            if state != "COMPLETED":
                return jsonify(
                    {
                        "error": f"CREATE VIEW job ended in state {state}",
                        "jobId": job_id,
                    }
                ), 500

            return jsonify(
                {
                    "ok": True,
                    "method": "sql",
                    "jobId": job_id,
                    "path": path_parts,
                    "path_str": ".".join(path_parts),
                }
            )
    except Exception as e:
        return jsonify({"error": f"Failed to create view: {e}"}), 500
