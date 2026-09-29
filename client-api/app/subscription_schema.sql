CREATE TABLE IF NOT EXISTS customer_accounts (
    id            BIGSERIAL PRIMARY KEY,
    email         VARCHAR(320) NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS subscription_plans (
    code             VARCHAR(40) PRIMARY KEY,
    name             VARCHAR(100) NOT NULL,
    description      TEXT NOT NULL,
    amount_minor     INTEGER NOT NULL CHECK (amount_minor >= 0),
    currency         CHAR(3) NOT NULL DEFAULT 'ZAR',
    billing_interval VARCHAR(20) NOT NULL DEFAULT 'month',
    is_active        BOOLEAN NOT NULL DEFAULT TRUE
);

INSERT INTO subscription_plans (code, name, description, amount_minor, currency)
VALUES
    ('free', 'Free', 'Starter plan for exploring the service.', 0, 'ZAR'),
    ('professional', 'Professional', 'Indicative individual plan price; billing is not enabled.', 29900, 'ZAR'),
    ('business', 'Business', 'Indicative team plan price; billing is not enabled.', 99900, 'ZAR')
ON CONFLICT (code) DO NOTHING;

CREATE TABLE IF NOT EXISTS subscriptions (
    id                   BIGSERIAL PRIMARY KEY,
    customer_id          BIGINT NOT NULL REFERENCES customer_accounts(id) ON DELETE CASCADE,
    plan_code            VARCHAR(40) NOT NULL REFERENCES subscription_plans(code),
    status               VARCHAR(20) NOT NULL DEFAULT 'pending'
                         CHECK (status IN ('pending', 'active', 'cancelled', 'expired')),
    billing_provider     VARCHAR(30) NOT NULL DEFAULT 'mock',
    provider_reference   VARCHAR(100) NOT NULL UNIQUE,
    current_period_start TIMESTAMPTZ,
    current_period_end   TIMESTAMPTZ,
    cancelled_at         TIMESTAMPTZ,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS one_open_subscription_per_customer
    ON subscriptions (customer_id)
    WHERE status IN ('pending', 'active');

CREATE INDEX IF NOT EXISTS idx_subscriptions_customer_created
    ON subscriptions (customer_id, created_at DESC);