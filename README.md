# Marzban VPN Bot

Telegram-бот для продажи VPN-подписок с интеграцией панели [Marzban](https://github.com/Gozargah/Marzban).

## Возможности

- **Продажа подписок** — выбор тарифа → оплата Telegram Stars → автоматическая выдача конфигурации
- **Пробный период** — 3 дня бесплатно (1 устройство)
- **Реферальная программа** — бонусные дни за приглашённых друзей
- **Промокоды** — процентная или фиксированная скидка
- **Уведомления** — за 3 и 1 день до окончания подписки
- **Авто-блокировка** — автоматическое отключение в Marzban по истечении срока
- **Админ-панель** — статистика, пользователи, платежи, рассылки, управление промокодами

## Тарифы

| Тариф | Срок | Устройства | Цена |
|-------|------|------------|------|
| Базовый | 1 месяц | 2 | 99 ⭐ |
| Стандарт | 3 месяца | 3 | 249 ⭐ |
| Премиум | 6 месяцев | 4 | 499 ⭐ |
| Годовой | 12 месяцев | 5 | 999 ⭐ |

## Технологический стек

| Компонент | Технология |
|-----------|------------|
| Бот | aiogram 3.x (async) |
| БД | MySQL 8.0 |
| Оплата | Telegram Stars (XTR) |
| VPN-панель | Marzban REST API |
| HTTP-клиент | aiohttp |
| Контейнеризация | Docker + Docker Compose |

## Структура проекта

```
marzban-vpn-bot/
├── bot/
│   ├── main.py              # Точка входа
│   ├── config.py            # Настройки из .env
│   ├── db/
│   │   ├── database.py      # Пул соединений MySQL
│   │   └── queries.py       # SQL-запросы
│   ├── marzban/
│   │   └── client.py        # Клиент Marzban API
│   ├── handlers/
│   │   ├── start.py         # /start, главное меню
│   │   ├── tariffs.py       # Выбор тарифа
│   │   ├── payment.py       # Оплата Telegram Stars
│   │   ├── subscription.py  # Мои подписки
│   │   ├── trial.py         # Пробный период
│   │   ├── referral.py      # Реферальная программа
│   │   ├── promo.py         # Промокоды
│   │   └── admin.py         # Админ-панель
│   ├── keyboards/
│   │   └── inline.py        # Inline-клавиатуры
│   ├── middlewares/
│   │   └── db.py            # Middleware
│   ├── scheduler/
│   │   └── tasks.py         # Планировщик (уведомления, блокировка)
│   └── utils/
│       └── helpers.py       # Утилиты
├── migrations/
│   └── schema.sql           # Схема БД MySQL
├── .env.example
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── README.md
```

## Быстрый старт

### 1. Клонирование

```bash
git clone https://github.com/flawder31/marzban-vpn-bot.git
cd marzban-vpn-bot
```

### 2. Настройка `.env`

```bash
cp .env.example .env
nano .env
```

Заполните:
- `BOT_TOKEN` — токен бота от [@BotFather](https://t.me/BotFather)
- `ADMIN_IDS` — Telegram ID администраторов (через запятую)
- `MYSQL_PASSWORD` / `MYSQL_ROOT_PASSWORD` — пароли MySQL
- `MARZBAN_BASE_URL` — адрес панели Marzban (например, `https://vpn.example.com:8443`)
- `MARZBAN_USERNAME` / `MARZBAN_PASSWORD` — учётные данные админа Marzban

### 3. Запуск через Docker

```bash
docker compose up -d --build
```

Схема БД применится автоматически при первом запуске.

### 4. Проверка

```bash
docker compose logs -f bot
```

### Запуск без Docker (локально)

```bash
# Установите MySQL 8.0 и создайте БД
mysql -u root -p < migrations/schema.sql

# Создайте виртуальное окружение
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Настройте .env (MYSQL_HOST=127.0.0.1)
cp .env.example .env
nano .env

# Запуск
python -m bot.main
```

## Команды бота

### Пользовательские
- `/start` — главное меню
- `/start <ref_code>` — регистрация по реферальной ссылке

### Администраторские
- `/admin` — админ-панель
- `/user_info <telegram_id>` — информация о пользователе
- `/cancel` — отмена текущего действия

## Marzban API

Бот использует следующие эндпоинты Marzban:

| Метод | Эндпоинт | Назначение |
|-------|----------|------------|
| POST | `/api/admin/token` | Получение токена авторизации |
| GET | `/api/inbounds` | Список inbound'ов для конфигурации |
| POST | `/api/user` | Создание пользователя VPN |
| GET | `/api/user/{username}` | Получение данных пользователя |
| PUT | `/api/user/{username}` | Изменение пользователя (продление, блокировка) |
| DELETE | `/api/user/{username}` | Удаление пользователя |
| GET | `/api/system` | Системная статистика |

## Архитектура

1. Пользователь нажимает «Купить VPN» → выбирает тариф
2. Бот формирует invoice с Telegram Stars (currency: XTR)
3. После успешной оплаты (`successful_payment`):
   - Создаётся пользователь в Marzban через REST API
   - Генерируется subscription URL
   - Сохраняется подписка в MySQL
   - Пользователю отправляется ссылка для подключения
4. Планировщик каждые 10 минут:
   - Проверяет подписки, истекающие через 3/1 день → отправляет уведомления
   - Находит истёкшие подписки → блокирует в Marzban → деактивирует в БД

## Лицензия

MIT
