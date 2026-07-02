select
    s.message_id,
    c.channel_key,
    to_char(s.message_date, 'YYYYMMDD')::int as date_key,
    s.message_text,
    s.message_length,
    s.views,
    s.forwards,
    s.has_image
from {{ ref('stg_telegram_messages') }} s
left join {{ ref('dim_channels') }} c on s.channel_name = c.channel_name