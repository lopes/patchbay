"""One-time Spotify authorization using Authorization Code + PKCE.

Run with:  uv run patchbay-auth

Opens your browser, you approve access, and the resulting tokens are cached to
config.TOKEN_PATH (default ~/.patchbay/token.json). PKCE means there is NO client
secret involved. Re-run any time you change scopes or revoke access.
"""

import base64
import hashlib
import http.server
import json
import os
import secrets
import time
import urllib.parse
import webbrowser

from . import _http, config


def _pkce_pair() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(64)).rstrip(b"=").decode()
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


_callback_result: dict = {}


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        _callback_result.clear()
        _callback_result.update({k: v[0] for k, v in params.items()})
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(
            b"<h2>patchbay: Spotify authorization complete.</h2>"
            b"<p>You can close this tab and return to your terminal.</p>"
        )

    def log_message(self, *args):
        pass


def _wait_for_callback(port: int) -> dict:
    _callback_result.clear()  # in case main() is invoked more than once
    server = http.server.HTTPServer(("127.0.0.1", port), _CallbackHandler)
    try:
        server.handle_request()  # blocks until exactly one request completes
    finally:
        server.server_close()
    return dict(_callback_result)


def _save_tokens(payload: dict) -> None:
    data = {
        "access_token": payload["access_token"],
        "refresh_token": payload["refresh_token"],
        "expires_at": time.time() + int(payload.get("expires_in", 3600)) - 60,
        "scope": payload.get("scope", config.SCOPES),
        "client_id": config.CLIENT_ID,
        "redirect_uri": config.REDIRECT_URI,
    }
    config.TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.TOKEN_PATH.write_text(json.dumps(data, indent=2))
    try:
        os.chmod(config.TOKEN_PATH, 0o600)
    except OSError:
        pass


def main() -> None:
    if not config.CLIENT_ID:
        raise SystemExit(
            "SPOTIFY_CLIENT_ID is not set. Copy .env.example to .env and add your "
            "Client ID from https://developer.spotify.com/dashboard"
        )

    port = urllib.parse.urlparse(config.REDIRECT_URI).port or 8888
    verifier, challenge = _pkce_pair()
    state = secrets.token_urlsafe(16)

    authorize_url = f"{config.AUTH_URL}?" + urllib.parse.urlencode(
        {
            "client_id": config.CLIENT_ID,
            "response_type": "code",
            "redirect_uri": config.REDIRECT_URI,
            "scope": config.SCOPES,
            "code_challenge_method": "S256",
            "code_challenge": challenge,
            "state": state,
        }
    )

    print("Opening your browser to authorize Spotify access...")
    print("If it doesn't open, paste this URL manually:\n")
    print(authorize_url, "\n")
    webbrowser.open(authorize_url)

    result = _wait_for_callback(port)
    if result.get("state") != state:
        raise SystemExit("State mismatch — aborting for safety. Please try again.")
    if "error" in result:
        raise SystemExit(f"Spotify returned an error: {result['error']}")
    if "code" not in result:
        raise SystemExit("No authorization code received. Please try again.")

    print("Exchanging the authorization code for tokens...")
    status, _headers, raw = _http.request(
        "POST",
        config.TOKEN_URL,
        form={
            "grant_type": "authorization_code",
            "code": result["code"],
            "redirect_uri": config.REDIRECT_URI,
            "client_id": config.CLIENT_ID,
            "code_verifier": verifier,
        },
    )
    if status != 200:
        raise SystemExit(f"Token exchange failed ({status}): {raw.decode(errors='replace')}")

    _save_tokens(json.loads(raw))
    print(f"\nSuccess. Tokens saved to {config.TOKEN_PATH}")
    print("Now wire patchbay into Claude Desktop (see the README) and restart it.")


if __name__ == "__main__":
    main()
