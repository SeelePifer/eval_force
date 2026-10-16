import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from evalforge_api.db import migrate
from evalforge_api.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required")
    pool = await asyncpg.create_pool(database_url, min_size=1, max_size=5)
    if pool is None:
        raise RuntimeError("database pool was not created")
    await migrate(pool)
    app.state.pool = pool
    yield
    await pool.close()


def create_app() -> FastAPI:
    app = FastAPI(title="EvalForge API", version="0.1.0", lifespan=lifespan)
    origins = [
        item.strip() for item in os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",") if item.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


app = create_app()
