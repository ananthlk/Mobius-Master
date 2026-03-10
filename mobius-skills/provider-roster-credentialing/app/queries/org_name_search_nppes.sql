-- Step 1 org search: NPPES (static template for 2 search words).
-- Python org_search.py builds this dynamically; params @w0, @w1, @lim.
-- Replace @w0/@w1 with actual values for ad-hoc runs.

WITH base AS (
  SELECT
    CAST(n.npi AS STRING) AS npi,
    TRIM(CASE
      WHEN CAST(n.entity_type_code AS STRING) = '2' THEN COALESCE(n.provider_organization_name_legal_business_name,'')
      ELSE TRIM(CONCAT(COALESCE(n.provider_last_name_legal_name,''), ', ', COALESCE(n.provider_first_name,'')))
    END) AS name_raw,
    CASE WHEN CAST(n.entity_type_code AS STRING) = '2' THEN 'organization' ELSE 'individual' END AS entity_type
  FROM `bigquery-public-data.nppes.npi_raw` n
  WHERE UPPER(TRIM(COALESCE(n.provider_business_practice_location_address_state_name,''))) IN ('FL','FLORIDA')
)
SELECT base.npi, base.name_raw AS name, base.entity_type
FROM base
WHERE LOWER(base.name_raw) LIKE CONCAT('%', LOWER(@w0), '%')
  AND LOWER(base.name_raw) LIKE CONCAT('%', LOWER(@w1), '%')
ORDER BY base.entity_type, base.name_raw
LIMIT @lim;
