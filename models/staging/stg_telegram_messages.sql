with source as (
    select * from {{ source('raw', 'telegram_messages') }}
)
select
    message_id::bigint                     as message_id,
    channel_name::text                     as channel_name,
    message_date::timestamp                as message_date,
    trim(message_text)                     as message_text,
    length(trim(message_text))             as message_length,
    has_media::boolean                     as has_media,
    image_path::text                       as image_path,
    coalesce(views, 0)::int                as views,
    coalesce(forwards, 0)::int             as forwards,
    case when image_path is not null then true else false end as has_image
from source
where message_text is not null and trim(message_text) != ''