# Medical Warehouse dbt Project

This dbt project transforms the raw Telegram warehouse into staging and mart models for analytics.

## Models
- staging/stg_telegram_messages.sql: standardizes raw Telegram messages
- marts/dim_channels.sql: channel dimension
- marts/dim_dates.sql: date dimension
- marts/fct_messages.sql: message fact table

## Tests
- Unique and not null tests on surrogate keys
- Custom tests for future-dated messages and non-negative views
