"""ASGI entrypoint (60_DEPLOYMENT.md).

Run with::

    uvicorn detective_monkey.interfaces.rest.asgi:app --host 0.0.0.0 --port 8000

or ``python -m detective_monkey.interfaces.rest.asgi`` for local development.
The app is stateless (DEP-05) and reads configuration externally (DEP-06).
"""

from __future__ import annotations

import os

from .app import create_app

app = create_app()


def run() -> None:  # pragma: no cover - thin runtime wrapper
    import uvicorn

    uvicorn.run(
        app,
        host=os.environ.get("DM_HOST", "0.0.0.0"),
        port=int(os.environ.get("DM_PORT", "8000")),
    )


if __name__ == "__main__":  # pragma: no cover
    run()
