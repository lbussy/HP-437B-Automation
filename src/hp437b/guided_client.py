"""Local orchestration client for explicitly started, point-confirmed guided sweeps."""

import argparse
import http.cookiejar
import json
import re
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

from . import provenance as p


class Client:
    """Use the same service actions as the browser; each confirm authorizes one point."""

    def __init__(self, url):
        parts = urlsplit(url)
        p.require(
            parts.scheme == "http"
            and parts.hostname == "127.0.0.1"
            and parts.port is not None
            and parts.path in ("", "/")
            and not parts.query
            and not parts.fragment
            and not parts.username,
            "Use the printed http://127.0.0.1:PORT URL",
        )
        self.url = url.rstrip("/")
        self.http = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
        )
        with self.http.open(self.url + "/", timeout=15) as response:
            match = re.search(
                r'name="operator-token" content="([0-9a-f]{64})"', response.read().decode()
            )
        p.require(match is not None, "Operator session token was not found")
        self.token = match.group(1)

    def request(self, path, body=None):
        headers = {"X-Operator-Token": self.token}
        data = None
        if body is not None:
            headers.update(Origin=self.url, **{"Content-Type": "application/json"})
            data = json.dumps(body, allow_nan=False).encode()
        with self.http.open(
            urllib.request.Request(self.url + path, data=data, headers=headers), timeout=15
        ) as response:
            return json.load(response)

    def state(self):
        return self.request("/api/state")

    def start(self, plan, *, operator=None, meter_mode="synthetic", prepared=None):
        return self.request(
            "/api/guided",
            dict(
                plan=plan,
                operator=operator,
                meter_mode=meter_mode,
                prepared=prepared if prepared is not None else {},
            ),
        )

    def confirm(self, job_id, prompt, *, operator=None):
        """Call only after the caller has verified the supplied frequency/drive labels."""
        p._keys(prompt, ("point_id", "frequency", "drive", "token"))
        return self.request(
            "/api/guided-confirm",
            dict(
                job_id=job_id,
                confirmation={
                    **prompt,
                    "operator": operator,
                    "frequency_confirmed": True,
                    "drive_confirmed": True,
                },
            ),
        )

    def stop(self, job_id):
        return self.request("/api/cancel", dict(job_id=job_id))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("state")
    start = sub.add_parser("start")
    start.add_argument("--plan", type=Path, required=True)
    start.add_argument("--operator")
    start.add_argument("--meter-mode", choices=("synthetic", "physical"), default="synthetic")
    start.add_argument("--prepared", type=Path, help="Fresh physical setup confirmation JSON")
    confirm = sub.add_parser("confirm")
    confirm.add_argument("--job-id", required=True)
    confirm.add_argument("--point-id", required=True)
    confirm.add_argument("--frequency", required=True)
    confirm.add_argument("--drive", required=True)
    confirm.add_argument("--operator")
    stop = sub.add_parser("stop")
    stop.add_argument("--job-id", required=True)
    args = parser.parse_args(argv)
    client = Client(args.url)
    if args.action == "state":
        result = client.state()
    elif args.action == "start":
        p.require(args.plan.stat().st_size <= 32 * 1024, "Plan exceeds limit")
        prepared = None
        if args.prepared:
            p.require(args.prepared.stat().st_size <= 8192, "Preparation exceeds limit")
            prepared = p._json(args.prepared.read_bytes())
        result = client.start(
            p._json(args.plan.read_bytes()),
            operator=args.operator,
            meter_mode=args.meter_mode,
            prepared=prepared,
        )
    elif args.action == "stop":
        result = client.stop(args.job_id)
    else:
        job = next((job for job in client.state()["jobs"] if job["job_id"] == args.job_id), None)
        p.require(
            job is not None and job.get("phase") == "waiting" and job.get("prompt"),
            "No point is waiting",
        )
        prompt = job["prompt"]
        p.require(
            (prompt["point_id"], prompt["frequency"], prompt["drive"])
            == (args.point_id, args.frequency, args.drive),
            "Requested labels do not match the pending point",
        )
        result = client.confirm(args.job_id, prompt, operator=args.operator)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
