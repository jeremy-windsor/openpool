from __future__ import annotations

from urllib.parse import urlparse

from fastapi import Request
from fastapi.responses import PlainTextResponse, Response

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
DEFAULT_PORTS = {"http": 80, "https": 443}


def _normalized_origin(value: str) -> tuple[str, str, int | None] | None:
    parsed = urlparse(value)
    if not parsed.scheme or not parsed.hostname or parsed.username or parsed.password:
        return None
    scheme = parsed.scheme.lower()
    try:
        port = parsed.port
    except ValueError:
        return None
    normalized_port = port if port is not None else DEFAULT_PORTS.get(scheme)
    return scheme, parsed.hostname.lower().rstrip("."), normalized_port


def _same_origin(request: Request, candidate: str | None) -> bool:
    if not candidate:
        return True
    request_origin = _normalized_origin(str(request.url))
    candidate_origin = _normalized_origin(candidate)
    return request_origin is not None and candidate_origin == request_origin


def _add_security_headers(response: Response) -> Response:
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    return response


async def reject_cross_origin_writes(request: Request, call_next):
    if request.method in UNSAFE_METHODS:
        origin = request.headers.get("origin")
        referer = request.headers.get("referer")
        if not _same_origin(request, origin) or not _same_origin(request, referer):
            return _add_security_headers(
                PlainTextResponse("cross-origin writes are not allowed", status_code=403)
            )
    response = _add_security_headers(await call_next(request))
    if not request.url.path.startswith("/static/"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response
