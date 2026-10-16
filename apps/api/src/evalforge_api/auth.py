import os
from typing import Annotated

from fastapi import Header, HTTPException


def require_bearer(authorization: Annotated[str | None, Header()] = None) -> None:
    expected = os.environ.get("EVALFORGE_API_KEY", "")
    if not expected or authorization != f"Bearer {expected}":
        raise HTTPException(status_code=401, detail="Unauthorized")
