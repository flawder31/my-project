-- ============================================================
-- Migration 001: subscription_notifications table
-- Replaces hardcoded notified_3d / notified_1d columns
-- with a flexible table that supports any notification period.
-- ============================================================

CREATE TABLE IF NOT EXISTS subscription_notifications (
    id              BIGINT UNSIGNED  AUTO_INCREMENT PRIMARY KEY,
    subscription_id BIGINT UNSIGNED  NOT NULL,
    days_before     INT UNSIGNED     NOT NULL,
    notified_at     DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE KEY uk_sub_days (subscription_id, days_before),
    CONSTRAINT fk_sn_sub FOREIGN KEY (subscription_id)
        REFERENCES subscriptions (id) ON DELETE CASCADE
) ENGINE=InnoDB
