-- ============================================================
-- Marzban VPN Bot — MySQL Schema
-- ============================================================

CREATE DATABASE IF NOT EXISTS marzban_bot
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE marzban_bot;

-- ---------- users ----------
CREATE TABLE IF NOT EXISTS users (
    id              BIGINT UNSIGNED  PRIMARY KEY COMMENT 'Telegram user ID',
    username        VARCHAR(64)      DEFAULT NULL,
    full_name       VARCHAR(255)     NOT NULL,
    language_code   VARCHAR(10)      DEFAULT 'ru',
    referrer_id     BIGINT UNSIGNED  DEFAULT NULL,
    referral_code   VARCHAR(32)      NOT NULL UNIQUE,
    bonus_days      INT UNSIGNED     NOT NULL DEFAULT 0,
    trial_used      TINYINT(1)       NOT NULL DEFAULT 0,
    is_admin        TINYINT(1)       NOT NULL DEFAULT 0,
    is_blocked      TINYINT(1)       NOT NULL DEFAULT 0,
    created_at      DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_referrer (referrer_id),
    INDEX idx_referral_code (referral_code),
    CONSTRAINT fk_user_referrer FOREIGN KEY (referrer_id)
        REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- ---------- tariffs ----------
CREATE TABLE IF NOT EXISTS tariffs (
    id              INT UNSIGNED     AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(128)     NOT NULL,
    duration_days   INT UNSIGNED     NOT NULL,
    device_limit    INT UNSIGNED     NOT NULL,
    price_stars     INT UNSIGNED     NOT NULL,
    is_active       TINYINT(1)       NOT NULL DEFAULT 1,
    created_at      DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- Pre-fill tariffs
INSERT INTO tariffs (name, duration_days, device_limit, price_stars) VALUES
    ('1 month / 2 devices',   30, 2,  99),
    ('3 months / 3 devices',  90, 3, 249),
    ('6 months / 4 devices', 180, 4, 499),
    ('12 months / 5 devices',365, 5, 999);

-- ---------- subscriptions ----------
CREATE TABLE IF NOT EXISTS subscriptions (
    id              BIGINT UNSIGNED  AUTO_INCREMENT PRIMARY KEY,
    user_id         BIGINT UNSIGNED  NOT NULL,
    tariff_id       INT UNSIGNED     DEFAULT NULL,
    marzban_username VARCHAR(128)    NOT NULL,
    subscription_url TEXT            DEFAULT NULL,
    device_limit    INT UNSIGNED     NOT NULL DEFAULT 2,
    is_trial        TINYINT(1)       NOT NULL DEFAULT 0,
    starts_at       DATETIME         NOT NULL,
    expires_at      DATETIME         NOT NULL,
    is_active       TINYINT(1)       NOT NULL DEFAULT 1,
    notified_3d     TINYINT(1)       NOT NULL DEFAULT 0,
    notified_1d     TINYINT(1)       NOT NULL DEFAULT 0,
    created_at      DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_user (user_id),
    INDEX idx_expires (expires_at),
    INDEX idx_active (is_active),
    CONSTRAINT fk_sub_user FOREIGN KEY (user_id)
        REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_sub_tariff FOREIGN KEY (tariff_id)
        REFERENCES tariffs (id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- ---------- payments ----------
CREATE TABLE IF NOT EXISTS payments (
    id                  BIGINT UNSIGNED  AUTO_INCREMENT PRIMARY KEY,
    user_id             BIGINT UNSIGNED  NOT NULL,
    tariff_id           INT UNSIGNED     DEFAULT NULL,
    subscription_id     BIGINT UNSIGNED  DEFAULT NULL,
    telegram_payment_id VARCHAR(255)     DEFAULT NULL,
    amount_stars        INT UNSIGNED     NOT NULL,
    discount_stars      INT UNSIGNED     NOT NULL DEFAULT 0,
    promo_code_id       BIGINT UNSIGNED  DEFAULT NULL,
    status              ENUM('pending','completed','refunded','failed')
                        NOT NULL DEFAULT 'pending',
    created_at          DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_pay_user (user_id),
    INDEX idx_pay_status (status),
    CONSTRAINT fk_pay_user FOREIGN KEY (user_id)
        REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_pay_tariff FOREIGN KEY (tariff_id)
        REFERENCES tariffs (id) ON DELETE SET NULL,
    CONSTRAINT fk_pay_sub FOREIGN KEY (subscription_id)
        REFERENCES subscriptions (id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- ---------- promo_codes ----------
CREATE TABLE IF NOT EXISTS promo_codes (
    id              BIGINT UNSIGNED  AUTO_INCREMENT PRIMARY KEY,
    code            VARCHAR(64)      NOT NULL UNIQUE,
    discount_type   ENUM('percent','fixed') NOT NULL DEFAULT 'percent',
    discount_value  INT UNSIGNED     NOT NULL COMMENT 'percent (1-100) or fixed stars amount',
    max_uses        INT UNSIGNED     DEFAULT NULL COMMENT 'NULL = unlimited',
    used_count      INT UNSIGNED     NOT NULL DEFAULT 0,
    valid_from      DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
    valid_until     DATETIME         DEFAULT NULL,
    is_active       TINYINT(1)       NOT NULL DEFAULT 1,
    created_at      DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ---------- promo_usage ----------
CREATE TABLE IF NOT EXISTS promo_usage (
    id              BIGINT UNSIGNED  AUTO_INCREMENT PRIMARY KEY,
    promo_code_id   BIGINT UNSIGNED  NOT NULL,
    user_id         BIGINT UNSIGNED  NOT NULL,
    used_at         DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE KEY uk_promo_user (promo_code_id, user_id),
    CONSTRAINT fk_pu_promo FOREIGN KEY (promo_code_id)
        REFERENCES promo_codes (id) ON DELETE CASCADE,
    CONSTRAINT fk_pu_user FOREIGN KEY (user_id)
        REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ---------- referrals ----------
CREATE TABLE IF NOT EXISTS referrals (
    id              BIGINT UNSIGNED  AUTO_INCREMENT PRIMARY KEY,
    referrer_id     BIGINT UNSIGNED  NOT NULL,
    referred_id     BIGINT UNSIGNED  NOT NULL,
    bonus_days      INT UNSIGNED     NOT NULL DEFAULT 3,
    is_rewarded     TINYINT(1)       NOT NULL DEFAULT 0,
    created_at      DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE KEY uk_referral (referrer_id, referred_id),
    CONSTRAINT fk_ref_referrer FOREIGN KEY (referrer_id)
        REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_ref_referred FOREIGN KEY (referred_id)
        REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ---------- broadcasts ----------
CREATE TABLE IF NOT EXISTS broadcasts (
    id              BIGINT UNSIGNED  AUTO_INCREMENT PRIMARY KEY,
    admin_id        BIGINT UNSIGNED  NOT NULL,
    message_text    TEXT             NOT NULL,
    total_users     INT UNSIGNED     NOT NULL DEFAULT 0,
    sent_count      INT UNSIGNED     NOT NULL DEFAULT 0,
    failed_count    INT UNSIGNED     NOT NULL DEFAULT 0,
    status          ENUM('pending','in_progress','completed','cancelled')
                    NOT NULL DEFAULT 'pending',
    created_at      DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at    DATETIME         DEFAULT NULL,

    CONSTRAINT fk_bc_admin FOREIGN KEY (admin_id)
        REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB;
