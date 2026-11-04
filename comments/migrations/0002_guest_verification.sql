-- Verification belongs to the server-side browser session, never a reusable Turnstile token.
ALTER TABLE sessions ADD COLUMN human_verified_until INTEGER NOT NULL DEFAULT 0;
-- Existing guest sessions were created only after a successful check. Credit the first 24 hours
-- of their original 30-day lifetime, without extending old or expired verification.
UPDATE sessions SET human_verified_until = MAX(0, expires_at - 29 * 86400000)
WHERE user_id IN (SELECT id FROM users WHERE kind = 'guest');
