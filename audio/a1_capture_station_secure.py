from __future__ import annotations

import argparse
import webbrowser
from http import HTTPStatus
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from audio.a1_capture_station import (
    ALLOWED_HOSTS,
    CaptureHandler,
    CaptureStore,
)

SECURE_SERVER_VERSION = "A1.2-browser-capture-secure-v0"
JSON_POST_PATHS = {
    "/api/start",
}
JSON_POST_PREFIXES = (
    "/api/reserve-audio/",
    "/api/finalize/",
)
AUDIO_POST_PREFIX = "/api/audio/"


def _normalise_hostname(hostname: str | None) -> str:
    if hostname is None:
        raise ValueError("Host header is required")
    lowered = hostname.lower()
    if lowered not in ALLOWED_HOSTS:
        raise ValueError("request Host must resolve to an allowed loopback hostname")
    return lowered


def validate_host_header(host_header: str | None, server_port: int) -> tuple[str, int]:
    if not host_header:
        raise ValueError("Host header is required")
    try:
        parsed = urlsplit(f"//{host_header}")
        hostname = _normalise_hostname(parsed.hostname)
        port = parsed.port
    except ValueError as exc:
        raise ValueError(f"invalid Host header: {exc}") from exc
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("userinfo is not allowed in Host header")
    effective_port = 80 if port is None else port
    if effective_port != server_port:
        raise ValueError("request Host port does not match capture-station port")
    return hostname, effective_port


def validate_post_request(
    *,
    path: str,
    host_header: str | None,
    origin_header: str | None,
    sec_fetch_site: str | None,
    content_type: str | None,
    server_port: int,
) -> None:
    host, port = validate_host_header(host_header, server_port)

    if not origin_header:
        raise ValueError("Origin header is required for state-changing requests")
    try:
        origin = urlsplit(origin_header)
        origin_host = _normalise_hostname(origin.hostname)
        origin_port = 80 if origin.port is None else origin.port
    except ValueError as exc:
        raise ValueError(f"invalid Origin header: {exc}") from exc
    if origin.scheme != "http":
        raise ValueError("capture-station Origin must use http on loopback")
    if origin.username is not None or origin.password is not None:
        raise ValueError("userinfo is not allowed in Origin")
    if origin.path not in ("", "/") or origin.query or origin.fragment:
        raise ValueError("Origin must not contain path/query/fragment data")
    if origin_host != host or origin_port != port:
        raise ValueError("cross-origin state-changing request rejected")

    if sec_fetch_site not in (None, "same-origin", "none"):
        raise ValueError("cross-site state-changing request rejected")

    media_type = (content_type or "").split(";", 1)[0].strip().lower()
    if path == AUDIO_POST_PREFIX[:-1] or path.startswith(AUDIO_POST_PREFIX):
        if media_type not in {"audio/wav", "audio/x-wav", "audio/wave"}:
            raise ValueError("audio upload requires Content-Type audio/wav")
        return

    if path in JSON_POST_PATHS or path.startswith(JSON_POST_PREFIXES):
        if media_type != "application/json":
            raise ValueError("JSON API requires Content-Type application/json")
        return

    # Unknown POST routes are still required to be same-origin, but their
    # method/path handling remains with the core handler so they produce 404.


class SecureCaptureHandler(CaptureHandler):
    """Same-origin HTTP shell around the tested local capture state machine.

    Loopback binding is necessary but not sufficient: browsers can issue some
    cross-origin requests to localhost even when response reading is blocked by
    SOP/CORS. Host + Origin + Content-Type checks therefore run before every
    state-changing core-handler call.
    """

    server_version = "A1CaptureStationSecure/0"

    def _server_port(self) -> int:
        return int(self.server.server_address[1])

    def _reject_security(self, message: str) -> None:
        self._error(HTTPStatus.FORBIDDEN, message)

    def _validate_host_only(self) -> bool:
        try:
            validate_host_header(self.headers.get("Host"), self._server_port())
        except ValueError as exc:
            self._reject_security(str(exc))
            return False
        return True

    def do_GET(self) -> None:
        if not self._validate_host_only():
            return
        super().do_GET()

    def do_OPTIONS(self) -> None:
        if not self._validate_host_only():
            return
        super().do_OPTIONS()

    def do_POST(self) -> None:
        if not self._validate_host_only():
            return
        try:
            validate_post_request(
                path=urlsplit(self.path).path,
                host_header=self.headers.get("Host"),
                origin_header=self.headers.get("Origin"),
                sec_fetch_site=self.headers.get("Sec-Fetch-Site"),
                content_type=self.headers.get("Content-Type"),
                server_port=self._server_port(),
            )
        except ValueError as exc:
            self._reject_security(str(exc))
            return
        super().do_POST()


def secure_handler_for(store: CaptureStore) -> type[SecureCaptureHandler]:
    class BoundSecureCaptureHandler(SecureCaptureHandler):
        pass

    BoundSecureCaptureHandler.store = store
    return BoundSecureCaptureHandler


def serve_secure(
    store: CaptureStore,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser_window: bool = False,
) -> None:
    if host not in ALLOWED_HOSTS:
        raise ValueError("A1.2 capture station may bind only to localhost/loopback")
    if not 1 <= port <= 65535:
        raise ValueError("port must be in 1..65535")
    server = ThreadingHTTPServer((host, port), secure_handler_for(store))
    url = f"http://{host}:{server.server_address[1]}/"
    print(f"A1.2 secure capture station: {url}")
    print(f"Local data directory: {store.root}")
    print("Host/Origin/Content-Type checks are enabled; no model inference is performed.")
    if open_browser_window:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the same-origin-hardened localhost A1.2 browser capture station"
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--subject-id", required=True)
    parser.add_argument("--household-id", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--open-browser", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    store = CaptureStore(
        args.output_dir,
        subject_id=args.subject_id,
        household_id=args.household_id,
        session_id=args.session_id,
    )
    serve_secure(
        store,
        host=args.host,
        port=args.port,
        open_browser_window=args.open_browser,
    )


if __name__ == "__main__":
    main()
