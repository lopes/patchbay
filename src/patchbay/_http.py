"""Minimal HTTP helper built on the standard library (urllib).

Deliberately tiny: one function covering the JSON and form-encoded requests
patchbay makes. 4xx/5xx responses are returned like any other response rather
than raised, so callers inspect the status uniformly.
"""

import json
import urllib.error
import urllib.parse
import urllib.request


def request(
    method: str,
    url: str,
    headers: dict | None = None,
    params: dict | None = None,
    json_body=None,
    form: dict | None = None,
    timeout: int = 30,
):
    """Return (status: int, headers, body: bytes).

    `headers` in the return value is the response header object, whose `.get()`
    is case-insensitive (handy for e.g. Retry-After).
    """
    headers = dict(headers or {})
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"

    body = None
    if json_body is not None:
        body = json.dumps(json_body).encode()
        headers.setdefault("Content-Type", "application/json")
    elif form is not None:
        body = urllib.parse.urlencode(form).encode()
        headers.setdefault("Content-Type", "application/x-www-form-urlencoded")

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.headers, resp.read()
    except urllib.error.HTTPError as e:  # 4xx/5xx arrive here, not as raises
        return e.code, e.headers, e.read()
