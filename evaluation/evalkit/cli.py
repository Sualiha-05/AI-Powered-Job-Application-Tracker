"""Pieces shared by the command-line tools."""
import datetime
import json
import sys
from pathlib import Path

from . import _paths  # noqa: F401
from app.llm_extract import default_model, get_llm_client, provider

RESULTS = Path(__file__).resolve().parents[1] / "results"


def stamp() -> str:
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


def llm_setup(log=print):
    """Returns (client, provider, model), or exits with a clear message when no AI provider key is configured."""
    client = get_llm_client()
    if client is None:
        log("No AI provider is configured. Set GEMINI_API_KEY (or ANTHROPIC_API_KEY), or leave out --llm.")
        raise SystemExit(2)
    return client, provider(), default_model()


def confirm_llm(n_calls: int, prov: str, model: str, yes: bool, log=print, ask=input) -> None:
    """Sending texts to an AI provider needs an explicit yes: it uses quota and shares the texts with a third party."""
    if n_calls == 0:
        log("All AI results are already cached: no calls will be made.")
        return
    log(f"\nThis will send {n_calls} resume + job description texts to {prov} ({model}).")
    log("  - Use only your own or made-up resumes.")
    log("  - On Gemini's free tier Google may use what you send to improve its products.")
    log("  - Free quotas are limited; a run stops early on repeated errors and can be resumed (results are cached).")
    if yes:
        return
    if not sys.stdin.isatty():
        log("Not running interactively: add --yes to confirm.")
        raise SystemExit(2)
    if ask("Type 'yes' to continue: ").strip().lower() != "yes":
        log("Cancelled.")
        raise SystemExit(1)


def write_outputs(out_dir: Path, name: str, result: dict, markdown: str) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    js, md = out_dir / f"{name}.json", out_dir / f"{name}.md"
    js.write_text(json.dumps(result, indent=2, default=list), encoding="utf-8")
    md.write_text(markdown, encoding="utf-8")
    return js, md
