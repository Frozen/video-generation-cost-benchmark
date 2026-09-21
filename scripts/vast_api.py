"""Small stdlib transport shared by local and instance-scoped Vast guards."""

import json
import os
from pathlib import Path
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

ORIGIN = "https://console.vast.ai"


class SafetyError(RuntimeError):
    """A locally generated, safe-to-publish admission or ownership failure."""


class APIError(RuntimeError):
    def __init__(self, status=None, cause=None):
        self.status = status
        if isinstance(cause, URLError) and isinstance(cause.reason, BaseException):
            cause = cause.reason
        self.cause_type = type(cause).__name__ if cause is not None else None
        detail = "HTTP %s" % status if status else "transport/response"
        if self.cause_type:
            detail += ": " + self.cause_type
        super().__init__("Vast API request failed (" + detail + ")")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class API:
    """Single-shot mutations; bounded transient-read recovery; no redirects or secret logging."""

    def __init__(self, key):
        if not isinstance(key, str) or not key or any(ord(c) < 33 or ord(c) > 126 for c in key):
            raise SafetyError("Vast credential missing or invalid")
        self._key = key
        self._opener = build_opener(NoRedirect())

    def request(self, method, path, payload=None):
        if not path.startswith("/api/") or "#" in path:
            raise SafetyError("Invalid API path")
        body = None if payload is None else json.dumps(payload).encode()
        request = Request(ORIGIN + path, data=body, method=method,
                          headers={"Authorization": "Bearer " + self._key,
                                   "Content-Type": "application/json", "Accept": "application/json"})
        deadline = time.monotonic() + 8 if method == "GET" else None
        for attempt in range(3):
            try:
                timeout = min(3, max(0.001, deadline - time.monotonic())) if deadline is not None else 20
                with self._opener.open(request, timeout=timeout) as reply:
                    raw = reply.read(8 * 1024 * 1024 + 1)
                    if len(raw) > 8 * 1024 * 1024:
                        raise APIError()
                    return json.loads(raw)
            except HTTPError as exc:
                exc.close()
                if method == "GET" and exc.code == 429 and attempt < 2 and deadline - time.monotonic() > 1.5:
                    time.sleep(1.5)
                    continue
                raise APIError(exc.code) from None
            except (URLError, TimeoutError, OSError) as exc:
                if method == "GET" and attempt < 2 and deadline - time.monotonic() > 0.5:
                    time.sleep(0.5)
                    continue
                raise APIError(cause=exc) from None
            except ValueError as exc:
                raise APIError(cause=exc) from None

    def pages(self, path, field, query=None):
        query = dict(query or {})
        rows, tokens, identifiers = [], set(), set()
        for _ in range(1000):
            result = self.request("GET", path + "?" + urlencode(query))
            if not isinstance(result, dict) or result.get("success") is not True or not isinstance(result.get(field), list):
                raise SafetyError("Incomplete paginated Vast listing")
            for row in result[field]:
                if not isinstance(row, dict):
                    raise SafetyError("Invalid Vast listing row")
                if field == "instances":
                    identifier = row.get("id")
                    if type(identifier) is not int or identifier in identifiers:
                        raise SafetyError("Unstable Vast instance pagination")
                    identifiers.add(identifier)
                rows.append(row)
            if "next_token" not in result:
                raise SafetyError("Missing Vast pagination completion marker")
            token = result["next_token"]
            if token is None:
                if field == "instances" and result.get("total_instances") != len(rows):
                    raise SafetyError("Vast instance count changed during pagination")
                return rows
            if not isinstance(token, str) or not token or token in tokens:
                raise SafetyError("Invalid or repeated Vast pagination token")
            tokens.add(token)
            query["after_token"] = token
        raise SafetyError("Vast pagination did not terminate")

    def instances(self):
        # Raw rows remain in memory only. Callers must persist explicit allowlists.
        return self.pages("/api/v1/instances/", "instances", {"limit": 25})


def save(path, data):
    """Atomic, private and durable journal, with distinct temporary files per writer."""
    path = Path(path)
    descriptor, temporary = tempfile.mkstemp(prefix="." + path.name + ".", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as stream:
            json.dump(data, stream, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
