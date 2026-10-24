import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _requirements() -> set[str]:
    lines = (ROOT / "requirements.txt").read_text().splitlines()
    return {ln.strip() for ln in lines if ln.strip() and not ln.startswith("#")}


def test_pyproject_dependencies_match_requirements_txt():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert set(data["project"]["dependencies"]) == _requirements()


def test_vercel_entrypoint_points_at_the_fastapi_app():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text())
    module, attr = data["tool"]["vercel"]["entrypoint"].split(":")
    imported = __import__(module, fromlist=[attr])
    from fastapi import FastAPI

    assert isinstance(getattr(imported, attr), FastAPI)


def test_runtime_requirements_have_no_test_packages():
    assert not any(name in req.lower() for req in _requirements() for name in ("pytest", "httpx=="))
