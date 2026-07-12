from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_repository_compose_files_bind_openpool_to_loopback():
    for filename in (
        "docker-compose.yml",
        "docker-compose.ghcr.yml",
        "docker-compose.postgres.yml",
    ):
        compose = (ROOT / filename).read_text()
        assert '"127.0.0.1:5280:5280"' in compose, filename
        assert '"5280:5280"' not in compose, filename


def test_ghcr_compose_supports_immutable_image_override():
    compose = (ROOT / "docker-compose.ghcr.yml").read_text()
    assert "${OPENPOOL_IMAGE:-ghcr.io/jeremy-windsor/openpool:latest}" in compose
