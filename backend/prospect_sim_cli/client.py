"""
ApiClient — HTTP wrapper for the prospect-sim Flask API.

All network calls go through this class. Errors are always
raised as ApiError with machine-readable code + fix field.

Rule 5: fail fast with actionable, parseable errors.
Rule 6: idempotent — callers can retry any method safely.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

import requests
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import Timeout

# Polling intervals and default timeouts (seconds)
POLL_INTERVAL = 3
GRAPH_BUILD_TIMEOUT = 900   # 15 min — graph build can be slow
SIMULATION_TIMEOUT = 1800   # 30 min — multi-agent simulation
REPORT_TIMEOUT = 600        # 10 min — ReACT report agent


class ApiError(Exception):
    """
    Structured error from the backend or network layer.
    Always carries a machine-readable code + human fix hint.
    """

    def __init__(
        self,
        code: str,
        message: str,
        fix: str = "",
        docs: str = "",
        http_status: Optional[int] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.fix = fix
        self.docs = docs
        self.http_status = http_status

    def to_dict(self) -> dict:
        d = {"error": self.code, "message": self.message}
        if self.fix:
            d["fix"] = self.fix
        if self.docs:
            d["docs"] = self.docs
        return d


class ApiClient:
    """
    Thin HTTP client for the prospect-sim Flask backend.

    All methods either return parsed response data (dict/list)
    or raise ApiError — never return None or raw Response objects.
    """

    def __init__(self, base_url: str = "http://localhost:5001", timeout: int = 60) -> None:
        # Strip trailing slash for consistent URL building
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _handle_response(self, resp: requests.Response) -> dict:
        """
        Parse response and raise ApiError on failure.
        Backend always returns {"success": bool, "data": ..., "error": ...}.
        """
        try:
            body = resp.json()
        except Exception:
            raise ApiError(
                "invalid_response",
                f"Backend returned non-JSON response (HTTP {resp.status_code})",
                fix="Check backend logs: cd backend && uv run python run.py",
            )

        if resp.status_code >= 500:
            raise ApiError(
                "backend_error",
                body.get("error", f"HTTP {resp.status_code}"),
                fix="Check backend logs for the full traceback",
                http_status=resp.status_code,
            )

        if not body.get("success", True):
            raise ApiError(
                "api_error",
                body.get("error", "Unknown error from backend"),
                http_status=resp.status_code,
            )

        return body.get("data", body)

    def _get(self, path: str, params: Optional[dict] = None) -> dict:
        try:
            resp = self._session.get(self._url(path), params=params, timeout=self.timeout)
        except RequestsConnectionError:
            raise ApiError(
                "backend_unavailable",
                f"Cannot connect to backend at {self.base_url}",
                fix="cd backend && uv run python run.py",
                docs="prospect-sim config set api-url <url>",
            )
        except Timeout:
            raise ApiError("timeout", f"Request to {path} timed out after {self.timeout}s")
        return self._handle_response(resp)

    def _delete(self, path: str) -> dict:
        try:
            resp = self._session.delete(self._url(path), timeout=self.timeout)
        except RequestsConnectionError:
            raise ApiError(
                "backend_unavailable",
                f"Cannot connect to backend at {self.base_url}",
                fix="cd backend && uv run python run.py",
                docs="prospect-sim config set api-url <url>",
            )
        except Timeout:
            raise ApiError("timeout", f"Request to {path} timed out after {self.timeout}s")
        return self._handle_response(resp)

    def _post(self, path: str, json: Optional[dict] = None, files=None, data=None) -> dict:
        try:
            if files is not None:
                # Multipart form-data — don't use JSON Content-Type header
                headers = {k: v for k, v in self._session.headers.items()
                           if k != "Content-Type"}
                resp = requests.post(
                    self._url(path), files=files, data=data,
                    headers=headers, timeout=self.timeout,
                )
            else:
                resp = self._session.post(self._url(path), json=json, timeout=self.timeout)
        except RequestsConnectionError:
            raise ApiError(
                "backend_unavailable",
                f"Cannot connect to backend at {self.base_url}",
                fix="cd backend && uv run python run.py",
                docs="prospect-sim config set api-url <url>",
            )
        except Timeout:
            raise ApiError("timeout", f"Request to {path} timed out after {self.timeout}s")
        return self._handle_response(resp)

    # ── Health & Settings ───────────────────────────────────────────────

    def health_check(self) -> bool:
        """Return True if backend is reachable. Never raises."""
        try:
            self._get("/api/settings")
            return True
        except ApiError:
            return False

    def get_settings(self) -> dict:
        """Return current backend settings (llm + neo4j). Raises ApiError if offline."""
        return self._get("/api/settings")

    def update_settings(
        self,
        llm: Optional[dict] = None,
        neo4j: Optional[dict] = None,
    ) -> dict:
        """
        Update backend LLM / Neo4j config at runtime (no restart required).

        llm keys: provider, base_url, model_name, api_key
        neo4j keys: uri, user, password
        """
        body: dict = {}
        if llm:
            body["llm"] = llm
        if neo4j:
            body["neo4j"] = neo4j
        return self._post("/api/settings", json=body)

    def test_llm(self) -> dict:
        """
        Fire a minimal test call to the current LLM config.
        Returns {success, model, latency_ms} or {success: False, error}.
        Never raises — callers should check the 'success' field.
        """
        try:
            return self._post("/api/settings/test-llm")
        except ApiError as exc:
            return {"success": False, "error": exc.message}

    # ── Project / Graph ─────────────────────────────────────────────────

    def get_project(self, project_id: str) -> dict:
        """Get project metadata. Raises ApiError if not found."""
        return self._get(f"/api/graph/project/{project_id}")

    def generate_ontology(
        self,
        icp_path: Path,
        project_name: str,
        simulation_requirement: str,
    ) -> dict:
        """
        Step 1: Upload ICP file and generate ontology.
        Returns dict with project_id and ontology.
        """
        with open(icp_path, "rb") as f:
            files = [("files", (icp_path.name, f, "application/octet-stream"))]
            form_data = {
                "simulation_requirement": simulation_requirement,
                "project_name": project_name,
                "simulation_type": "email_inbox",
            }
            return self._post("/api/graph/ontology/generate", files=files, data=form_data)

    def build_graph(self, project_id: str) -> str:
        """
        Step 2: Start async graph build.
        Returns task_id for polling.
        """
        result = self._post("/api/graph/build", json={"project_id": project_id})
        task_id = result.get("task_id")
        if not task_id:
            raise ApiError("missing_task_id", "Backend returned no task_id for graph build")
        return task_id

    def poll_task(self, task_id: str, timeout: int = GRAPH_BUILD_TIMEOUT) -> dict:
        """
        Poll a background task until completed or failed.
        Returns final task result dict.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            result = self._get(f"/api/graph/task/{task_id}")
            status = result.get("status", "")
            if status == "completed":
                return result
            if status in ("failed", "error"):
                raise ApiError(
                    "task_failed",
                    result.get("error", f"Task {task_id} failed"),
                    fix="Check backend logs for details",
                )
            time.sleep(POLL_INTERVAL)

        raise ApiError(
            "task_timeout",
            f"Task {task_id} did not complete within {timeout}s",
            fix="Increase timeout or check backend logs",
        )

    # ── Variant test ─────────────────────────────────────────────────────

    def run_variant_test(
        self,
        project_id: str,
        variants: list[dict],
        simulation_requirement: str,
        parallel: bool = False,
        num_rounds: int = 8,
    ) -> list[dict]:
        """
        Create one simulation per variant.
        Returns list of {variant_id, variant_label, simulation_id}.
        """
        result = self._post("/api/simulation/run-variant-test", json={
            "project_id": project_id,
            "variants": variants,
            "simulation_requirement": simulation_requirement,
            "parallel": parallel,
            "num_rounds": num_rounds,
        })
        run_ids = result.get("variant_run_ids", [])
        if not run_ids:
            raise ApiError("no_simulations_created", "Backend created no simulation IDs")
        return run_ids

    def prepare_simulation(self, simulation_id: str) -> str:
        """
        Prepare a simulation (generates agent profiles).
        Returns task_id for polling.
        """
        result = self._post("/api/simulation/prepare", json={
            "simulation_id": simulation_id,
            "simulation_type": "email_inbox",
        })
        task_id = result.get("task_id")
        if not task_id:
            raise ApiError("missing_task_id", f"No task_id returned for prepare of {simulation_id}")
        return task_id

    def start_simulation(self, simulation_id: str) -> None:
        """Start the simulation runner for a prepared simulation."""
        self._post("/api/simulation/start", json={"simulation_id": simulation_id})

    def poll_simulation(
        self,
        simulation_id: str,
        timeout: int = SIMULATION_TIMEOUT,
    ) -> dict:
        """
        Poll simulation run status until completed or failed.
        Returns final status dict.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            result = self._get(f"/api/simulation/{simulation_id}/run-status")
            status = result.get("status", "")
            if status in ("completed", "stopped"):
                return result
            if status == "failed":
                raise ApiError(
                    "simulation_failed",
                    result.get("error", f"Simulation {simulation_id} failed"),
                    fix="Check /api/observability/events for detailed logs",
                )
            time.sleep(POLL_INTERVAL)

        raise ApiError(
            "simulation_timeout",
            f"Simulation {simulation_id} did not complete within {timeout}s",
            fix="Increase --timeout or check backend logs",
        )

    # ── Report ───────────────────────────────────────────────────────────

    def generate_report(self, simulation_id: str) -> str:
        """
        Start report generation for a completed simulation.
        Returns report_id.
        """
        result = self._post("/api/report/generate", json={
            "simulation_id": simulation_id,
        })
        report_id = result.get("report_id")
        if not report_id:
            raise ApiError("missing_report_id", "Backend returned no report_id")
        return report_id

    def poll_report(self, report_id: str, timeout: int = REPORT_TIMEOUT) -> dict:
        """Poll report generation until complete. Returns final report dict."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            result = self._post("/api/report/generate/status", json={"report_id": report_id})
            status = result.get("status", "")
            if status == "completed":
                return self.get_report(report_id)
            if status == "failed":
                raise ApiError(
                    "report_failed",
                    result.get("error", f"Report {report_id} failed"),
                    fix="Check /api/observability/events for ReACT agent logs",
                )
            time.sleep(POLL_INTERVAL)

        raise ApiError(
            "report_timeout",
            f"Report {report_id} did not complete within {timeout}s",
        )

    def get_report(self, report_id: str) -> dict:
        """Fetch a completed report."""
        return self._get(f"/api/report/{report_id}")

    # ── Graph ────────────────────────────────────────────────────────────

    def get_graph_data(self, graph_id: str) -> dict:
        """
        Fetch graph structure data for display.
        Returns {node_count, edge_count, entity_types, nodes[], edges[]}.
        """
        return self._get(f"/api/graph/data/{graph_id}")

    # ── Runs ─────────────────────────────────────────────────────────────

    def get_run_detail(self, project_id: str) -> dict:
        """
        Full inspection data for one run.
        Returns {project, graph, simulations} with agents, report outline, etc.
        Raises ApiError if project not found.
        """
        return self._get(f"/api/runs/{project_id}/detail")

    def get_runs(self) -> list:
        """
        List all past runs.
        Returns list of run dicts sorted by created_at desc.
        Each item: {project_id, name, created_at, icp_file, total_simulations,
                    total_reports, disk_mb, graph_id, simulations}.
        """
        return self._get("/api/runs")

    def delete_run(self, project_id: str) -> dict:
        """
        Delete every artifact for a run (graph + files).
        Returns {project_id, deleted_simulations, deleted_reports, graph_deleted}.
        Raises ApiError if project not found (404) or backend error.
        """
        return self._delete(f"/api/runs/{project_id}")
