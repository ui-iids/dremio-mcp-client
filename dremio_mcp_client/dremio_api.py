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
        return self._get("/api/v3/catalog")

    def get_entity(self, entity_id: str) -> Dict[str, Any]:
        return self._get(f"/api/v3/catalog/{entity_id}")

    def get_children(self, entity_id: str) -> List[Dict[str, Any]]:
        try:
            data = self._get(f"/api/v3/catalog/{entity_id}/children")
            return data.get("children", data.get("data", [])) or []
        except requests.HTTPError:
            ent = self.get_entity(entity_id)
            return ent.get("children", []) or []

    # Focused iterators: spaces only, then descend through folders/containers
    def iter_spaces(self) -> Iterable[Dict[str, Any]]:
        """
        Yield top-level spaces from GET /api/v3/catalog root.
        Handles both shapes:
        • {"type":"SPACE", ...}
        • {"type":"CONTAINER","containerType":"SPACE", ...}  <-- your payload
        """
        root = self.get_catalog_root()
        for obj in root.get("data") or root.get("children") or []:
            t = (obj.get("type") or obj.get("entityType") or "").upper()
            ct = (obj.get("containerType") or "").upper()
            if t == "SPACE" or (t == "CONTAINER" and ct == "SPACE"):
                yield obj

    def iter_space_tree(self, space_id: str) -> Iterable[Dict[str, Any]]:
        """
        Breadth-first over a single space: yields folders/containers and datasets
        (children of the space and nested folders).
        """
        queue: List[Tuple[str, Dict[str, Any]]] = [("SPACE", {"id": space_id})]

        while queue:
            parent_kind, node = queue.pop(0)
            node_id = node.get("id")
            if not node_id:
                continue

            for child in self.get_children(node_id):
                yield child
                ctype = (child.get("type") or child.get("entityType") or "").upper()
                # Recurse into containers/folders only
                if ctype in {"CONTAINER", "FOLDER"}:
                    queue.append(("CONTAINER", {"id": child.get("id")}))

    # ---- views (virtual datasets) ------------------------------------------

    @staticmethod
    def _is_view(obj: Dict[str, Any]) -> bool:
        """
        Recognize views in both shapes:
          • Space/folder children: {"type":"DATASET","datasetType":"VIRTUAL"}
          • Full view objects:     {"entityType":"dataset","type":"VIRTUAL_DATASET"}
        Docs:
          - Space children show datasetType 'VIRTUAL'. (24.3.x Space)
          - View objects use type 'VIRTUAL_DATASET'. (24.3.x View)
        """
        type_upper = (obj.get("type") or obj.get("entityType") or "").upper()
        ds_type_upper = (
            obj.get("datasetType") or obj.get("containerType") or ""
        ).upper()

        # Full view object
        if type_upper == "VIRTUAL_DATASET":
            return True

        # Space/folder listing entry
        if type_upper == "DATASET" and ds_type_upper in {"VIRTUAL", "VIRTUAL_DATASET"}:
            return True

        # Embedded dataset object
        ds = obj.get("dataset") or {}
        ds_type2 = (ds.get("type") or ds.get("datasetType") or "").upper()
        if ds_type2 in {"VIRTUAL", "VIRTUAL_DATASET"}:
            return True

        return False

    def _normalize_path(self, obj: Dict[str, Any]) -> Tuple[List[str], Optional[str]]:
        parts = obj.get("path") or obj.get("fullPathList") or []
        if isinstance(parts, str):
            parts = [parts]
        path_str = ".".join(parts) if parts else None
        return parts, path_str

    def list_views(
        self,
        *,
        space_names: Optional[List[str]] = None,
        include_sql: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Return all views across all (or selected) spaces.
        Each item:
          { id, path, path_str, type, createdAt, modifiedAt, sql? }
        """
        results: List[Dict[str, Any]] = []

        # Determine which spaces to traverse
        spaces = list(self.iter_spaces())
        if space_names:
            wanted = set({s.lower() for s in space_names})
            spaces = [s for s in spaces if s.get("name", "").lower() in wanted]

        for space in spaces:
            sid = space.get("id")
            if not sid:
                continue

            for obj in self.iter_space_tree(sid):
                if not self._is_view(obj):
                    continue

                path_parts, path_str = self._normalize_path(obj)
                vid = obj.get("id")
                vtype = (
                    obj.get("type")
                    or obj.get("datasetType")
                    or (obj.get("dataset") or {}).get("datasetType")
                    or "VIRTUAL_DATASET"
                )

                sql = obj.get("sql")
                # Child listings in spaces usually omit SQL; hydrate if requested.
                if include_sql and not sql and vid:
                    try:
                        full = self.get_entity(vid)
                        sql = full.get("sql") or (full.get("dataset") or {}).get("sql")
                        # Normalize path from full object if missing
                        if not path_parts:
                            path_parts, path_str = self._normalize_path(full)
                    except Exception:
                        pass  # non-fatal

                results.append(
                    {
                        "id": vid,
                        "path": path_parts,
                        "path_str": path_str,
                        "type": vtype,
                        "createdAt": obj.get("createdAt") or obj.get("created_at"),
                        "modifiedAt": obj.get("modifiedAt")
                        or obj.get("modified_at")
                        or obj.get("lastModified"),
                        "sql": sql,
                    }
                )

        return results

    # dremio_mcp_client/dremio_api.py  (append to the class)

    # ---- SQL / jobs --------------------------------------------------------

    def run_sql(self, sql: str) -> str:
        """
        POST /api/v3/sql -> { id: <jobId> }
        """
        payload = {"sql": sql}
        data = self._s.post(
            self._url("/api/v3/sql"),
            json=payload,
            timeout=self.timeout,
            verify=self.verify_ssl,
        )
        data.raise_for_status()
        return data.json().get("id")

    def get_job(self, job_id: str) -> Dict[str, Any]:
        return self._get(f"/api/v3/job/{job_id}")

    def get_job_results(
        self, job_id: str, *, offset: int = 0, limit: int = 100
    ) -> Dict[str, Any]:
        return self._get(
            f"/api/v3/job/{job_id}/results", params={"offset": offset, "limit": limit}
        )

    def wait_for_job(
        self, job_id: str, *, timeout_s: float = 30.0, poll_s: float = 0.5
    ) -> Dict[str, Any]:
        """
        Polls /api/v3/job/{id} until state in {"COMPLETED","CANCELED","FAILED"} or timeout.
        Returns the final job object.
        """
        import time

        deadline = time.time() + timeout_s
        while True:
            job = self.get_job(job_id)
            state = (job.get("jobState") or job.get("state") or "").upper()
            if state in {"COMPLETED", "CANCELED", "FAILED"}:
                return job
            if time.time() >= deadline:
                raise TimeoutError(
                    f"Job {job_id} did not finish within {timeout_s}s (last state={state!r})"
                )
            time.sleep(poll_s)

    # ---- Helpers -----------------------------------------------------------

    @staticmethod
    def quote_identifier(parts: List[str] | None) -> str:
        """
        Turn ["IIDS","my_view"] into "IIDS"."my_view"
        """
        parts = parts or []
        return ".".join(f'"{p.replace('"', '""')}"' for p in parts if p is not None)

    def _post(self, path: str, **kwargs) -> Dict[str, Any]:
        r = self._s.post(
            self._url(path), timeout=self.timeout, verify=self.verify_ssl, **kwargs
        )
        r.raise_for_status()
        return r.json()

    def create_view_sql(
        self,
        *,
        path_parts: List[str],
        select_sql: str,
        or_replace: bool = True,
    ) -> str:
        """
        Create a view using SQL (CREATE [OR REPLACE] VIEW … AS …).
        Returns the jobId. Caller may wait on job if desired.

        Ref: CREATE VIEW docs. :contentReference[oaicite:3]{index=3}
        """
        ident = self.quote_identifier(path_parts)
        prefix = "CREATE OR REPLACE VIEW" if or_replace else "CREATE VIEW"
        sql = f"{prefix} {ident} AS {select_sql.rstrip().rstrip(';')}"
        return self.run_sql(sql)

    def create_view_catalog(
        self,
        *,
        path_parts: List[str],
        select_sql: str,
        sql_context: Optional[List[str]] = None,
        or_replace: bool = True,
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a view using the Catalog API.

        On self-hosted / v3: POST /api/v3/catalog
        On Dremio Cloud:      POST /projects/{project-id}/catalog

        Body shape (per docs):
          {
            "entityType":"dataset",
            "type":"VIRTUAL_DATASET",
            "path":["Space","Folder","ViewName"],
            "sql":"SELECT ...",
            "sqlContext":["Samples", "samples.dremio.com"]   # optional
          }

        For 'OR REPLACE', we first try POST; if it fails because it exists
        and or_replace=True, we look up the entity and PUT with the new SQL.

        Ref: Catalog View API. :contentReference[oaicite:4]{index=4}
        """
        base_path = None
        # Prefer Cloud route if a project_id is provided in args OR in env/config
        project_id = project_id or os.getenv("DREMIO_PROJECT_ID") or None
        if project_id:
            base_path = f"/projects/{project_id}/catalog/"
        else:
            base_path = "/api/v3/catalog"

        payload = {
            "entityType": "dataset",
            "type": "VIRTUAL_DATASET",
            "path": path_parts,
            "sql": select_sql,
        }
        if sql_context:
            payload["sqlContext"] = sql_context

        try:
            return self._post(base_path, json=payload)
        except requests.HTTPError as e:
            # If it already exists and or_replace=True, try PUT update
            if not or_replace:
                raise
            status = getattr(e.response, "status_code", None)
            # Fetch existing entity by path & then PUT with tag
            # There isn't a direct "by-path" endpoint in v3; we can list or search.
            # Simplest: run SHOW CREATE VIEW to ensure it exists, then get entity via search (or list).
            try:
                # Try to find entity by listing space/folders where possible,
                # but here we fallback to GET /api/v3/catalog and scan (small installs).
                root = self.get_catalog_root()
                # Brute search for matching path
                wanted = [p.lower() for p in path_parts]

                def path_matches(obj):
                    p = obj.get("path") or obj.get("fullPathList") or []
                    return [str(x).lower() for x in p] == wanted

                # Try root children and some recursion if needed
                def scan(node):
                    items = node.get("data") or node.get("children") or []
                    for it in items:
                        if path_matches(it):
                            return it
                    return None

                found = scan(root)
                if not found:
                    # last resort: enumerate spaces and walk (costlier)
                    for s in self.iter_spaces():
                        for child in self.get_children(s.get("id")):
                            p = child.get("path") or child.get("fullPathList") or []
                            if [str(x).lower() for x in p] == wanted:
                                found = child
                                break
                        if found:
                            break

                if not found or not found.get("id"):
                    raise RuntimeError(
                        f"View exists but ID not found for path {'.'.join(path_parts)}"
                    )

                eid = found["id"]
                # Get full entity to retrieve current tag if required
                full = self.get_entity(eid)
                tag = full.get("tag") or (full.get("dataset") or {}).get("tag")

                put_body = {
                    "entityType": "dataset",
                    "id": eid,
                    "type": "VIRTUAL_DATASET",
                    "path": path_parts,
                    "sql": select_sql,
                }
                if tag:
                    put_body["tag"] = tag

                r = self._s.put(
                    self._url(
                        base_path.rstrip("/") + "/" + requests.utils.quote(eid, safe="")
                    ),
                    json=put_body,
                    timeout=self.timeout,
                    verify=self.verify_ssl,
                )
                r.raise_for_status()
                return r.json()
            except Exception:
                raise
