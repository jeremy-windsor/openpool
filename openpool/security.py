from __future__ import annotations

from urllib.parse import urlparse

from fastapi import Request
from fastapi.responses import PlainTextResponse

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _same_host(request: Request, candidate: str | None) -> bool:
    if not candidate:
        return True
    parsed = urlparse(candidate)
    return parsed.netloc == request.headers.get("host")


async def reject_cross_origin_writes(request: Request, call_next):
    if request.method in UNSAFE_METHODS:
        origin = request.headers.get("origin")
        referer = request.headers.get("referer")
        if not _same_host(request, origin) or not _same_host(request, referer):
            return PlainTextResponse("cross-origin writes are not allowed", status_code=403)
    return await call_next(request)
