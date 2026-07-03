"""ASGI entrypoint (60_DEPLOYMENT.md).

Run with::

    uvicorn detective_monkey.interfaces.rest.asgi:app --host 0.0.0.0 --port 8000

or ``python -m detective_monkey.interfaces.rest.asgi`` for local development.
The app is stateless (DEP-05) and reads configuration externally (DEP-06).

The deployed server persists the Student Evidence Profiles and the experiment
journal to SQLite (``DM_DB_PATH``, default ``detective_monkey.db`` in the
working directory) — a discovery product must not forget its students between
restarts. Set ``DM_DB_PATH=:memory:`` for an ephemeral instance.
"""

from __future__ import annotations

import os

from ...application import seed
from .app import create_app

_db_path = os.environ.get("DM_DB_PATH", "detective_monkey.db")
if _db_path == ":memory:":
    _db_path = None

app = create_app(seed.build_demo_backend(db_path=_db_path))


def run() -> None:  # pragma: no cover - thin runtime wrapper
    import uvicorn

    uvicorn.run(
        app,
        host=os.environ.get("DM_HOST", "0.0.0.0"),
        port=int(os.environ.get("DM_PORT", "8000")),
    )


if __name__ == "__main__":  # pragma: no cover
    run()
