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

    async def ensure_subscription_schema(self):
        schema = Path(__file__).with_name("subscription_schema.sql").read_text(encoding="utf-8")
        async with self.pool.acquire() as conn:
            await conn.execute(schema)

    async def create_customer(self, email: str, password_hash: str):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO customer_accounts (email, password_hash)
                VALUES ($1, $2)
                RETURNING id, email, created_at
                """,
                email,
                password_hash,
            )
            return dict(row)

    async def get_customer_by_email(self, email: str):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, email, password_hash FROM customer_accounts WHERE email = $1",
                email,
            )
            return dict(row) if row else None

    async def get_customer_by_id(self, customer_id: int):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, email, created_at FROM customer_accounts WHERE id = $1",
                customer_id,
            )
            return dict(row) if row else None

    async def list_subscription_plans(self):
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT code, name, description, amount_minor, currency, billing_interval
                FROM subscription_plans
                WHERE is_active = TRUE
                ORDER BY amount_minor, code
                """
            )
            return [dict(row) for row in rows]

    async def get_subscription_plan(self, plan_code: str):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT code, amount_minor, currency FROM subscription_plans WHERE code = $1 AND is_active = TRUE",
                plan_code,
            )
            return dict(row) if row else None

    async def create_subscription(self, customer_id: int, plan_code: str, provider_reference: str):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO subscriptions (customer_id, plan_code, provider_reference)
                SELECT $1, code, $3
                FROM subscription_plans
                WHERE code = $2 AND is_active = TRUE
                RETURNING id, customer_id, plan_code, status, billing_provider,
                          current_period_start, current_period_end, created_at
                """,
                customer_id,
                plan_code,
                provider_reference,
            )
            return dict(row) if row else None

    async def get_current_subscription(self, customer_id: int):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT s.id, s.plan_code, p.name AS plan_name, s.status,
                       s.billing_provider, p.amount_minor, p.currency,
                       p.billing_interval, s.current_period_start,
                       s.current_period_end, s.created_at
                FROM subscriptions s
                JOIN subscription_plans p ON p.code = s.plan_code
                WHERE s.customer_id = $1 AND s.status IN ('pending', 'active')
                ORDER BY s.created_at DESC
                LIMIT 1
                """,
                customer_id,
            )
            return dict(row) if row else None

    async def activate_mock_subscription(self, subscription_id: int, customer_id: int):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE subscriptions
                SET status = 'active',
                    current_period_start = CURRENT_TIMESTAMP,
                    current_period_end = CURRENT_TIMESTAMP + INTERVAL '1 month',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = $1 AND customer_id = $2 AND status = 'pending'
                RETURNING id, plan_code, status, billing_provider,
                          current_period_start, current_period_end, created_at
                """,
                subscription_id,
                customer_id,
            )
            return dict(row) if row else None

    async def cancel_subscription(self, customer_id: int):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE subscriptions
                SET status = 'cancelled', cancelled_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE customer_id = $1 AND status IN ('pending', 'active')
                RETURNING id, plan_code, status, billing_provider,
                          current_period_start, current_period_end, cancelled_at
                """,
                customer_id,
            )
            return dict(row) if row else None

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
