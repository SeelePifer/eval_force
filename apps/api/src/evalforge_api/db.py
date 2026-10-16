import asyncpg

MIGRATION_SQL = """
CREATE TABLE IF NOT EXISTS datasets (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    sha256 TEXT NOT NULL UNIQUE,
    cases JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS runs (
    id UUID PRIMARY KEY,
    dataset_sha256 TEXT NOT NULL,
    manifest JSONB NOT NULL,
    results JSONB NOT NULL,
    report_html TEXT NOT NULL,
    passed BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS runs_created_at_idx ON runs (created_at DESC);
"""


async def migrate(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as connection:
        await connection.execute(MIGRATION_SQL)
