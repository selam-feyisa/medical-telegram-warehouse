select
    s.message_id,
    c.channel_key,
    to_char(s.message_date, 'YYYYMMDD')::int as date_key,
    d.image_category,
    d.confidence_score,
    d.image_path
from {{ ref('stg_telegram_messages') }} s
left join (
    select message_id, image_category, confidence_score, image_path
    from raw.image_detections
    where 1 = 0
) d on d.message_id = s.message_id
left join {{ ref('dim_channels') }} c on c.channel_name = s.channel_name
