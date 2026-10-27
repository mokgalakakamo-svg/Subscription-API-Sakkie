import asyncpg
import json
from pathlib import Path
from datetime import datetime
from typing import Optional

from .config import get_settings

settings = get_settings()
DB_DSN = settings.database_url


def _parse_ts(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    for fmt in (
        "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d",
        "%A, %d %B %Y - %H:%M", "%A, %d %B %Y",
        "%d/%m/%Y %H:%M", "%d/%m/%Y",
    ):
        try:
            return datetime.strptime(value.strip(), fmt)
        except (ValueError, AttributeError):
            continue
    return None


class TenderDB:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    @classmethod
    async def connect(cls) -> "TenderDB":
        pool = await asyncpg.create_pool(DB_DSN, min_size=1, max_size=10)
        return cls(pool)

    async def close(self):
        await self.pool.close()

    async def ensure_email_updates_schema(self):
        schema = Path(__file__).with_name("email_updates_schema.sql").read_text(encoding="utf-8")
        async with self.pool.acquire() as conn:
            await conn.execute(schema)

    async def request_email_updates_subscription(self, email: str, token_hash: str):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO email_update_subscriptions
                    (email, status, confirmation_token_hash, confirmation_expires_at)
                VALUES ($1, 'pending', $2, CURRENT_TIMESTAMP + INTERVAL '24 hours')
                ON CONFLICT (email) DO UPDATE
                SET status = CASE
                        WHEN email_update_subscriptions.status = 'active' THEN 'active'
                        ELSE 'pending'
                    END,
                    confirmation_token_hash = CASE
                        WHEN email_update_subscriptions.status = 'active' THEN NULL
                        ELSE EXCLUDED.confirmation_token_hash
                    END,
                    confirmation_expires_at = CASE
                        WHEN email_update_subscriptions.status = 'active' THEN NULL
                        ELSE EXCLUDED.confirmation_expires_at
                    END,
                    subscribed_at = CASE
                        WHEN email_update_subscriptions.status = 'active'
                            THEN email_update_subscriptions.subscribed_at
                        ELSE NULL
                    END,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING id, email, status, subscribed_at
                """,
                email,
                token_hash,
            )
            return dict(row)

    async def confirm_email_updates_subscription(self, token_hash: str):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE email_update_subscriptions
                SET status = 'active', subscribed_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE confirmation_token_hash = $1
                  AND confirmation_expires_at > CURRENT_TIMESTAMP
                  AND status = 'pending'
                RETURNING id, email
                """,
                token_hash,
            )
            if row:
                return dict(row)
            row = await conn.fetchrow(
                """
                SELECT id, email FROM email_update_subscriptions
                WHERE confirmation_token_hash = $1
                  AND confirmation_expires_at > CURRENT_TIMESTAMP
                  AND status = 'active'
                """,
                token_hash,
            )
            return dict(row) if row else None

    async def finish_email_updates_confirmation(self, token_hash: str):
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE email_update_subscriptions
                SET confirmation_token_hash = NULL,
                    confirmation_expires_at = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE confirmation_token_hash = $1 AND status = 'active'
                """,
                token_hash,
            )

    async def list_tenders(
        self,
        status: Optional[str] = None,
        province: Optional[str] = None,
        category: Optional[str] = None,
        organisation: Optional[str] = None,
        closing_before=None,
        closing_after=None,
        keyword: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ):
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM list_tenders(
                    $1::varchar, $2::varchar, $3::varchar, $4::varchar,
                    $5::timestamp, $6::timestamp, $7::varchar,
                    $8::integer, $9::integer
                )
                """,
                status, province, category, organisation,
                _parse_ts(closing_before), _parse_ts(closing_after),
                keyword, limit, offset,
            )
            return [dict(r) for r in rows]

    async def count_tenders(
        self,
        status: Optional[str] = None,
        province: Optional[str] = None,
        category: Optional[str] = None,
        organisation: Optional[str] = None,
        closing_before=None,
        closing_after=None,
        keyword: Optional[str] = None,
    ) -> int:
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                """
                SELECT count_tenders_filtered(
                    $1::varchar, $2::varchar, $3::varchar, $4::varchar,
                    $5::timestamp, $6::timestamp, $7::varchar
                )
                """,
                status, province, category, organisation,
                _parse_ts(closing_before), _parse_ts(closing_after),
                keyword,
            )

    async def get_tender_detail(self, tender_number: str):
        async with self.pool.acquire() as conn:
            raw = await conn.fetchval(
                "SELECT get_tender_detail($1::varchar)", tender_number
            )
            if raw is None:
                return None
            return json.loads(raw) if isinstance(raw, str) else raw

    async def get_dashboard_stats(self):
        async with self.pool.acquire() as conn:
            raw = await conn.fetchval("SELECT get_dashboard_stats()")
            if raw is None:
                return {}
            return json.loads(raw) if isinstance(raw, str) else raw
