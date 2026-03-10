-- Step 1 address search: NPPES (static template for zip5 + 2 street words).
-- Python org_search.py builds this dynamically; params @zip5, @sw0, @sw1, @lim.
-- Matches: state + ZIP5 + street address contains each word.

SELECT
  CAST(n.npi AS STRING) AS npi,
  TRIM(CASE WHEN CAST(n.entity_type_code AS STRING) = '2'
    THEN COALESCE(n.provider_organization_name_legal_business_name,'')
    ELSE TRIM(CONCAT(COALESCE(n.provider_last_name_legal_name,''), ', ', COALESCE(n.provider_first_name,'')))
  END) AS name,
  CASE WHEN CAST(n.entity_type_code AS STRING) = '2' THEN 'organization' ELSE 'individual' END AS entity_type,
  TRIM(COALESCE(n.provider_first_line_business_practice_location_address,'')) AS address_line_1,
  TRIM(COALESCE(n.provider_business_practice_location_address_city_name,'')) AS city,
  TRIM(COALESCE(n.provider_business_practice_location_address_state_name,'')) AS state,
  SUBSTR(REGEXP_REPLACE(COALESCE(n.provider_business_practice_location_address_postal_code,''), r'[^0-9]', ''), 1, 5) AS zip5
FROM `bigquery-public-data.nppes.npi_raw` n
WHERE UPPER(TRIM(COALESCE(n.provider_business_practice_location_address_state_name,''))) IN ('FL','FLORIDA')
  AND SUBSTR(REGEXP_REPLACE(COALESCE(n.provider_business_practice_location_address_postal_code,''), r'[^0-9]', ''), 1, 5) = @zip5
  AND LOWER(COALESCE(n.provider_first_line_business_practice_location_address,'')) LIKE CONCAT('%', LOWER(@sw0), '%')
  AND LOWER(COALESCE(n.provider_first_line_business_practice_location_address,'')) LIKE CONCAT('%', LOWER(@sw1), '%')
ORDER BY n.entity_type_code, name
LIMIT @lim;
