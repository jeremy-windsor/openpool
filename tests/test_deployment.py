from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parents[1]
PORT_ENTRY_RE = re.compile(
    r"^\s*-\s*[\"']?([^\"'#\n]*5280[^\"'#\n]*)[\"']?\s*$",
    re.MULTILINE,
)


def test_repository_compose_files_bind_openpool_to_loopback():
    for filename in (
        "docker-compose.yml",
        "docker-compose.ghcr.yml",
        "docker-compose.postgres.yml",
    ):
        compose = (ROOT / filename).read_text()
        assert PORT_ENTRY_RE.findall(compose) == ["127.0.0.1:5280:5280"], filename


def test_ghcr_compose_supports_immutable_image_override():
    compose = (ROOT / "docker-compose.ghcr.yml").read_text()
    assert "${OPENPOOL_IMAGE:-ghcr.io/jeremy-windsor/openpool:latest}" in compose


def test_docker_build_context_is_allowlisted():
    rules = [
        line.strip()
        for line in (ROOT / ".dockerignore").read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]

    assert rules == [
        "**",
        "!Dockerfile",
        "!README.md",
        "!pyproject.toml",
        "!uv.lock",
        "!openpool/",
        "!openpool/*.py",
        "!openpool/chemistry/",
        "!openpool/chemistry/*.py",
        "!openpool/routers/",
        "!openpool/routers/*.py",
        "!openpool/templates/",
        "!openpool/templates/*.html",
        "!openpool/static/",
        "!openpool/static/*.css",
        "!openpool/static/*.html",
        "!openpool/static/*.js",
        "!openpool/static/*.png",
        "!openpool/static/*.svg",
        "!openpool/static/*.webmanifest",
    ]
