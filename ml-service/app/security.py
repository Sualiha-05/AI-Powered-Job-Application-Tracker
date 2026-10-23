import os
import secrets

from fastapi import Header, HTTPException


def require_key(x_api_key: str | None = Header(default=None)) -> None:
    """Shared-secret check between the backend and this service.

    If ML_API_KEY is not set the check is disabled (local development). In production
    set the same long random value on the backend and here, because this service is
    publicly reachable on free hosting and /extract can spend your LLM budget.
    """
    expected = os.getenv("ML_API_KEY")
    if expected and not secrets.compare_digest((x_api_key or "").encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="Invalid API key")
