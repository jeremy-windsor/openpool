from __future__ import annotations

from urllib.parse import urlparse

from fastapi import Request
from fastapi.responses import PlainTextResponse, Response

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _same_host(request: Request, candidate: str | None) -> bool:
    if not candidate:
        return True
    parsed = urlparse(candidate)
    return parsed.netloc == request.headers.get("host")


def _add_security_headers(response: Response) -> Response:
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    return response


async def reject_cross_origin_writes(request: Request, call_next):
    if request.method in UNSAFE_METHODS:
        origin = request.headers.get("origin")
        referer = request.headers.get("referer")
        if not _same_host(request, origin) or not _same_host(request, referer):
            return _add_security_headers(
                PlainTextResponse("cross-origin writes are not allowed", status_code=403)
            )
    return _add_security_headers(await call_next(request))
