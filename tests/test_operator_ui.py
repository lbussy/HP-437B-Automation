"""Loopback HTTP/session boundaries and native fake worker lifecycle."""

import http.cookiejar
import json
import re
import threading
import time
import urllib.error
import urllib.request

import pytest

from hp437b import operator_jobs as j
from hp437b import operator_ui as ui
from hp437b import test_profiles as t
from hp437b import test_suite as u


def wait(manager, job_id):
    limit = time.monotonic() + 25
    while time.monotonic() < limit:
        manager.state()
        result = manager.get(job_id)
        if not result["active"]:
            return result
        time.sleep(0.02)
    raise AssertionError("Fake worker did not finish")


@pytest.fixture
def manager(tmp_path):
    pytest.importorskip("reportlab")
    instance = j.Jobs(tmp_path / "runs", plots=False)
    try:
        yield instance
    finally:
        instance.close()


class EmptyManager:
    def __init__(self):
        self.actions = 0

    def state(self):
        return dict(profiles=[], profile_issues=[], jobs=[], active_id=None, plots=False)

    def import_profile(self, document):
        self.actions += 1
        return "test"

    def start(self, *args):
        self.actions += 1
        return dict(job_id="test")

    def cancel(self, *args):
        self.actions += 1
        return {}

    def artifact(self, *args):
        raise ValueError("Not available")


@pytest.fixture
def http_server():
    managers = []

    def create(manager=None):
        manager = manager or EmptyManager()
        server = ui.server(manager, 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        managers.append((server, thread))
        origin = f"http://127.0.0.1:{server.server_port}"
        client = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
        )
        with client.open(origin) as response:
            page = response.read().decode()
            cookie = response.headers["Set-Cookie"]
            csp = response.headers["Content-Security-Policy"]
        token = re.search(r'name="operator-token" content="([^"]+)"', page).group(1)

        def request(path, body=None, headers=None):
            headers = {
                "X-Operator-Token": token,
                **(
                    {"Origin": origin, "Content-Type": "application/json"}
                    if body is not None
                    else {}
                ),
                **(headers or {}),
            }
            data = json.dumps(body).encode() if body is not None else None
            return client.open(urllib.request.Request(origin + path, data=data, headers=headers))

        return server, manager, request, cookie, csp

    yield create
    for server, thread in managers:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_loopback_session_cookie_csp_assets_and_no_auto_start(http_server):
    server, manager, request, cookie, csp = http_server()
    assert server.server_address[0] == "127.0.0.1"
    assert "HttpOnly" in cookie and "SameSite=Strict" in cookie
    assert "script-src 'self'" in csp and "style-src 'self';" in csp
    with request("/api/state") as response:
        assert json.load(response)["jobs"] == []
    with request("/app.js") as response:
        assert b"function renderRun" in response.read()
    with request("/app.css") as response:
        assert b"focus-visible" in response.read()
    assert manager.actions == 0


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": "http://evil.example"},
        {"X-Operator-Token": "bad"},
        {"Host": "evil.example"},
        {"Content-Type": "text/plain"},
    ],
)
def test_cross_origin_token_host_and_content_type_writes_refused(http_server, headers):
    _, manager, request, _, _ = http_server()
    with pytest.raises(urllib.error.HTTPError) as exc:
        request("/api/jobs", {}, headers)
    assert exc.value.code == 400 and manager.actions == 0


def test_session_required_unknown_routes_and_oversized_length(http_server):
    server, manager, request, _, _ = http_server()
    origin = f"http://127.0.0.1:{server.server_port}"
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(origin + "/api/state")
    assert exc.value.code == 403
    with pytest.raises(urllib.error.HTTPError) as exc:
        request("/no-route")
    assert exc.value.code == 404
    # Reject the declared length before reading a body. Sending a huge body can
    # race the server closing the socket and produce BrokenPipeError on Linux.
    with pytest.raises(urllib.error.HTTPError) as exc:
        request("/api/profiles", {}, {"Content-Length": str(ui.MAX_REQUEST + 1)})
    assert exc.value.code == 400
    assert "too large" in json.load(exc.value)["error"]
    with pytest.raises(urllib.error.HTTPError) as exc:
        request("/api/profiles", dict(profile_json=" " * (256 * 1024 + 1)))
    assert exc.value.code == 400
    assert "256 KiB" in json.load(exc.value)["error"]
    assert manager.actions == 0


def test_profile_import_preserves_strict_json_and_fakes_only(http_server, manager):
    _, _, request, _, _ = http_server(manager)
    source = t.example()
    source["profile_id"] = "import-test"
    with request("/api/profiles", dict(profile_json=json.dumps(source))) as response:
        key = json.load(response)["key"]
    assert key in manager.catalog()[0]
    source["mode"] = "physical"
    with pytest.raises(urllib.error.HTTPError):
        request("/api/profiles", dict(profile_json=json.dumps(source)))
    with pytest.raises(urllib.error.HTTPError):
        request("/api/profiles", dict(profile_json='{"mode":"physical","mode":"fake"}'))
    assert len(manager.catalog()[0]) == 2


def test_native_worker_one_active_run_progress_reports_and_reopen(manager):
    key = next(iter(manager.catalog()[0]))
    job = manager.start(key, ["WF-04", "WF-06"], "Local operator")
    assert job["active"]
    with pytest.raises(ValueError, match="already running"):
        manager.start(key, ["WF-04"], None)
    result = wait(manager, job["job_id"])
    assert (
        result["phase"] == "finished"
        and result["outcome"] == "completed"
        and len(result["results"]) == 2
    )
    assert result["pdf_ready"] and result["package_ready"]
    path = manager.root / job["job_id"]
    cap = u.load(path / "capture")[0]
    assert cap["selected"] == ["WF-04", "WF-06"] and cap["completed_workflows"] == 2
    data, media, download = manager.artifact(job["job_id"], "report.pdf")
    assert data.startswith(b"%PDF-") and media == "application/pdf" and not download
    assert manager.artifact(job["job_id"], "package.zip")[1:] == ("application/zip", True)
    root = manager.root
    manager.close()
    reopened = j.Jobs(root, plots=False)
    try:
        assert reopened.state()["jobs"][0]["job_id"] == job["job_id"]
    finally:
        reopened.close()


def test_cooperative_cancel_and_repeated_cancel_are_safe(manager):
    key = next(iter(manager.catalog()[0]))
    job = manager.start(key, list(t.KINDS), None)
    manager.cancel(job["job_id"])
    manager.cancel(job["job_id"])
    result = wait(manager, job["job_id"])
    assert result["outcome"] == "interrupted" and result["cancel_requested"]
    cap = u.load(manager.root / job["job_id"] / "capture")[0]
    assert cap["status"] == "interrupted" and cap["attempted_workflows"] < 3
    assert result["pdf_ready"] and result["package_ready"]
    with pytest.raises(ValueError):
        manager.cancel(job["job_id"])


def test_boundary_cancel_finishes_current_native_workflow(tmp_path, monkeypatch):
    pytest.importorskip("reportlab")
    job_id = "a" * 32
    path = tmp_path / job_id
    path.mkdir()
    j.atomic(
        path / "request.json",
        dict(
            schema="hp437b.operator-request.v1",
            job_id=job_id,
            profile=t.example(),
            workflows=list(t.KINDS),
            operator=None,
            plots=False,
            started_utc="2026-11-13T00:00:00+00:00",
        ),
    )
    j.atomic(
        path / "state.json",
        dict(
            job_id=job_id,
            phase="starting",
            current=None,
            index=0,
            total=3,
            results=[],
            error=None,
            outcome=None,
        ),
    )
    original = j.atomic
    events = []

    def observe(target, value):
        original(target, value)
        if target.name == "state.json":
            events.append(dict(value))
            if (
                value["phase"] == "running"
                and value["index"] == 1
                and value["current"] is None
                and value["results"]
            ):
                (path / "cancel.requested").write_text("UI boundary request")

    monkeypatch.setattr(j, "atomic", observe)
    j.worker(path)
    cap = u.load(path / "capture")[0]
    assert cap["status"] == "interrupted" and cap["stop_reason"] == "cancelled:WF-05"
    assert cap["results"][0]["rf_state"] == "off" and cap["results"][0]["supply_restored"]
    assert not (path / "capture/captures/WF-05").exists()
    assert any(event["current"] == "WF-04" for event in events)
    assert j.read(path / "state.json")["phase"] == "finished"


def test_incompatible_invalid_and_duplicate_workflows_never_start(manager):
    key = next(iter(manager.catalog()[0]))
    before = set(manager.root.iterdir())
    for workflows in ([], ["WF-04", "WF-04"], ["WF-99"]):
        with pytest.raises(ValueError):
            manager.start(key, workflows, None)
    with pytest.raises(ValueError):
        manager.start("missing", ["WF-04"], None)
    assert set(manager.root.iterdir()) == before
    bad = t.example()
    bad["mode"] = "physical"
    with pytest.raises(ValueError):
        manager.import_profile(bad)


def test_exclusive_session_lock_and_no_resume_of_old_state(tmp_path):
    pytest.importorskip("reportlab")
    root = tmp_path / "runs"
    manager = j.Jobs(root, plots=False)
    with pytest.raises(ValueError, match="Another operator"):
        j.Jobs(root, plots=False)
    job_id = "b" * 32
    path = root / job_id
    path.mkdir()
    j.atomic(
        path / "request.json",
        dict(
            job_id=job_id,
            profile=t.example(),
            workflows=["WF-04"],
            operator=None,
            started_utc="2026-11-13T00:00:00+00:00",
        ),
    )
    j.atomic(
        path / "state.json",
        dict(job_id=job_id, phase="running", current="WF-04", results=[], index=1, total=1),
    )
    external = tmp_path / "external"
    external.mkdir()
    j.atomic(external / "state.json", dict(phase="running"))
    (root / ("c" * 32)).symlink_to(external, target_is_directory=True)
    manager.close()
    reopened = j.Jobs(root, plots=False)
    try:
        assert j.read(external / "state.json") == dict(phase="running")
        state = reopened.get(job_id)
        assert (
            state["phase"] == "failed"
            and "No test was restarted" in state["error"]
            and not state["active"]
        )
    finally:
        reopened.close()


def test_http_starts_native_job_and_serves_only_sealed_artifacts(http_server, manager):
    _, _, request, _, _ = http_server(manager)
    key = next(iter(manager.catalog()[0]))
    with request(
        "/api/jobs", dict(profile_key=key, workflows=["WF-04"], operator="HTTP operator")
    ) as response:
        job = json.load(response)
    result = wait(manager, job["job_id"])
    assert result["phase"] == "finished"
    with request("/artifacts/" + job["job_id"] + "/report.pdf") as response:
        assert response.headers["Content-Type"] == "application/pdf" and response.read().startswith(
            b"%PDF-"
        )
    with request("/artifacts/" + job["job_id"] + "/package.zip") as response:
        assert "attachment" in response.headers[
            "Content-Disposition"
        ] and response.read().startswith(b"PK")
    for path in ("../request.json", "%2e%2e/request.json", "worker.log", "/etc/passwd"):
        with pytest.raises(urllib.error.HTTPError):
            request("/artifacts/" + job["job_id"] + "/" + path)
    (manager.root / job["job_id"] / "report/report.pdf").write_bytes(b"changed")
    with pytest.raises(urllib.error.HTTPError):
        request("/artifacts/" + job["job_id"] + "/report.pdf")


def test_progress_observer_sees_boundaries_without_new_capture_policy(tmp_path):
    events = []
    cap = u.run(
        t.example(),
        tmp_path / "capture",
        workflows=["WF-04", "WF-05"],
        plots=False,
        progress=events.append,
    )
    assert [item["event"] for item in events] == ["workflow_started", "workflow_finished"] * 2
    assert [item["result"] for item in events if "result" in item] == cap["results"]
    assert cap["status"] == "completed" and u.load(tmp_path / "capture")[0] == cap
