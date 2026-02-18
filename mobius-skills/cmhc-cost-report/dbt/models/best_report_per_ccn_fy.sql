{{
  config(
    materialized='view',
    description='One row per (provider_ccn, fiscal_year_end) with the best report_record_key (prefer settled/amended).',
  )
}}

-- Best report per CMHC per fiscal year: prefer status 3 (settled), then 4 (amended), then 1 (as-submitted).
with ranked as (
  select
    report_record_key,
    provider_ccn,
    fiscal_year_start,
    fiscal_year_end,
    report_status,
    form_vintage,
    row_number() over (
      partition by provider_ccn, fiscal_year_end
      order by case report_status when '3' then 1 when '4' then 2 when '1' then 3 else 4 end
    ) as rn
  from {{ source('landing_cmhc', 'hcris_rpt') }}
)
select
  report_record_key,
  provider_ccn,
  fiscal_year_start,
  fiscal_year_end,
  report_status,
  form_vintage
from ranked
where rn = 1
