CREATE TABLE IF NOT EXISTS email_update_subscriptions (
    id            BIGSERIAL PRIMARY KEY,
    email         VARCHAR(320) NOT NULL UNIQUE,
    status        VARCHAR(20) NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending', 'active', 'unsubscribed')),
    confirmation_token_hash TEXT,
    confirmation_expires_at TIMESTAMPTZ,
    subscribed_at TIMESTAMPTZ,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE email_update_subscriptions
    ADD COLUMN IF NOT EXISTS confirmation_token_hash TEXT,
    ADD COLUMN IF NOT EXISTS confirmation_expires_at TIMESTAMPTZ,
    ALTER COLUMN subscribed_at DROP NOT NULL;

ALTER TABLE email_update_subscriptions
    ALTER COLUMN status SET DEFAULT 'pending';

ALTER TABLE email_update_subscriptions
    DROP CONSTRAINT IF EXISTS email_update_subscriptions_status_check;

ALTER TABLE email_update_subscriptions
    ADD CONSTRAINT email_update_subscriptions_status_check
    CHECK (status IN ('pending', 'active', 'unsubscribed'));

CREATE INDEX IF NOT EXISTS idx_email_update_subscriptions_status
    ON email_update_subscriptions (status);
