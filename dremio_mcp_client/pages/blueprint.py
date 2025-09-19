import json
import os
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
                b = MCPBridge(params)
                b.connect()
                _bridge = b
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


