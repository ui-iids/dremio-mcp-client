# dremio_mcp_client/dremio_api.py
from __future__ import annotations

import os
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urljoin

import requests


class DremioClient:
    """
    Minimal Dremio v3 API client focused on catalog traversal and views (VDS).

    Auth:
      - Uses Dremio Personal Access Token header: "Authorization: <SCHEME> <TOKEN>"
      - Default scheme is "_dremio"; set auth_scheme="Bearer" if your deployment needs it.

    Configuration precedence for token:
      1) token=... (constructor arg)
      2) DREMIO_TOKEN (env)
      3) token_file=... (constructor arg)
      4) DREMIO_TOKEN_FILE (env)
      5) ./token.txt (relative to current working directory)

    Other env fallbacks:
      - DREMIO_URL  (e.g., https://dremio.example.com)
      - DREMIO_AUTH_SCHEME  (defaults to "_dremio")
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        token: Optional[str] = None,
        *,
        token_file: Optional[str] = None,
        auth_scheme: Optional[str] = None,
        timeout: float = 30.0,
        verify_ssl: bool = True,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.base_url = (base_url or os.getenv("DREMIO_URL") or "").rstrip("/")
        if not self.base_url:
            raise RuntimeError("DremioClient: set DREMIO_URL or pass base_url")

        # --- Resolve token ---
        resolved_token = token or os.getenv("DREMIO_TOKEN")
        if not resolved_token:
            # Decide which file to read: arg > env > ./token.txt
            token_file = token_file or os.getenv("DREMIO_TOKEN_FILE") or "token.txt"
            resolved_token = self._load_token_from_file(token_file)

        if not resolved_token:
            raise RuntimeError(
                "DremioClient: no token provided. "
                "Pass token=..., or set DREMIO_TOKEN, or provide token_file / DREMIO_TOKEN_FILE, "
                "or put your token in ./token.txt"
            )

        self.token = resolved_token
        self.auth_scheme = auth_scheme or os.getenv("DREMIO_AUTH_SCHEME") or "_dremio"
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self._s = session or requests.Session()
        self._s.headers.update(
            {
                "Authorization": f"{self.auth_scheme} {self.token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

    @staticmethod
    def _load_token_from_file(path: str) -> Optional[str]:
        """
        Read a PAT from a file. Returns the token stripped of whitespace/newlines,
        or None if the file doesn't exist or is empty.
        """
        try:
            with open(path, "r", encoding="utf-8") as f:
                tok = f.read().strip()
                return tok or None
        except FileNotFoundError:
            return None
        except OSError as e:
            # Surface non-ENOENT issues for visibility
            raise RuntimeError(f"Failed to read token file '{path}': {e}") from e

    # ---- low-level ----------------------------------------------------------

    def _url(self, path: str) -> str:
        if path.startswith(("http://", "https://")):
            return path
        if not path.startswith("/"):
            path = "/" + path
        return urljoin(self.base_url, path)

    def _get(self, path: str, **kwargs) -> Dict[str, Any]:
        r = self._s.get(
            self._url(path), timeout=self.timeout, verify=self.verify_ssl, **kwargs
        )
        r.raise_for_status()
        return r.json()

    # ---- catalog traversal --------------------------------------------------

    def get_catalog_root(self) -> Dict[str, Any]:
        """GET /api/v3/catalog (root)"""
        return self._get("/api/v3/catalog")

    def get_entity(self, entity_id: str) -> Dict[str, Any]:
        """GET /api/v3/catalog/{id}"""
        return self._get(f"/api/v3/catalog/{entity_id}")

    def get_children(self, entity_id: str) -> List[Dict[str, Any]]:
        """
        Children can appear inline under 'children' in some responses,
        but the canonical endpoint is:
          GET /api/v3/catalog/{id}/children
        """
        try:
            data = self._get(f"/api/v3/catalog/{entity_id}/children")
            return data.get("children", data.get("data", [])) or []
        except requests.HTTPError:
            # Some entities inline children
            ent = self.get_entity(entity_id)
            return ent.get("children", [])

    def iter_catalog(self) -> Iterable[Dict[str, Any]]:
        """
        Breadth-first walk of the entire visible catalog for the caller.
        Yields every catalog object (spaces, folders, sources, datasets).
        """
        root = self.get_catalog_root()
        queue: List[Dict[str, Any]] = []

        top = root.get("data") or root.get("children") or []
        queue.extend(top)

        while queue:
            node = queue.pop(0)
            yield node
            node_id = node.get("id")
            node_type = (node.get("type") or node.get("entityType") or "").upper()
            if node_id and node_type in {
                "SOURCE",
                "SPACE",
                "HOME",
                "CONTAINER",
                "FOLDER",
            }:
                try:
                    kids = self.get_children(node_id)
                    queue.extend(kids)
                except Exception:
                    # Non-fatal: keep walking other branches
                    pass

    # ---- views (virtual datasets) ------------------------------------------

    @staticmethod
    def _is_view(obj: Dict[str, Any]) -> bool:
        """
        Recognize virtual datasets (views) across API shapes.
        Examples:
          { "entityType": "dataset", "type": "VIRTUAL_DATASET", ... }
          { "type": "DATASET", "datasetType": "VIRTUAL_DATASET", ... }
          { "dataset": { "datasetType": "VIRTUAL_DATASET", ... } }
        """
        t = (obj.get("type") or obj.get("entityType") or "").upper()
        ds_type = (obj.get("datasetType") or obj.get("containerType") or "").upper()
        if obj.get("type", "").upper() == "VIRTUAL_DATASET":
            return True
        if t == "DATASET" and ds_type == "VIRTUAL_DATASET":
            return True
        ds = obj.get("dataset") or {}
        if (ds.get("type") or ds.get("datasetType") or "").upper() == "VIRTUAL_DATASET":
            return True
        return False

    def list_views(self) -> List[Dict[str, Any]]:
        """
        Return a flat list of all views visible to the caller.
        Each item normalized to:
          { id, path, path_str, type, createdAt, modifiedAt, sql (if present) }
        """
        out: List[Dict[str, Any]] = []
        for obj in self.iter_catalog():
            if not self._is_view(obj):
                continue

            # Normalize path
            path_parts = obj.get("path") or obj.get("fullPathList") or []
            if isinstance(path_parts, str):
                path_parts = [path_parts]
            path_str = (
                ".".join(path_parts)
                if path_parts
                else obj.get("path").replace("/", ".")
                if isinstance(obj.get("path"), str)
                else None
            )

            # Try to find SQL if present (some entities include it)
            sql = None
            if "sql" in obj:
                sql = obj.get("sql")
            elif "view" in obj and isinstance(obj["view"], dict):
                sql = obj["view"].get("sql")
            elif "dataset" in obj and isinstance(obj["dataset"], dict):
                sql = obj["dataset"].get("sql")

            out.append(
                {
                    "id": obj.get("id"),
                    "path": path_parts,
                    "path_str": path_str,
                    "type": obj.get("type")
                    or obj.get("datasetType")
                    or "VIRTUAL_DATASET",
                    "createdAt": obj.get("createdAt") or obj.get("created_at"),
                    "modifiedAt": obj.get("modifiedAt")
                    or obj.get("modified_at")
                    or obj.get("lastModified"),
                    "sql": sql,
                }
            )
        return out
