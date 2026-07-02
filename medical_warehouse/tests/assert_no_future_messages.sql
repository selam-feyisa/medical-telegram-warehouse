select message_id
from {{ ref('stg_telegram_messages') }}
where message_date > now()
