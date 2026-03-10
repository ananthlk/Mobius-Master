-- Step 1 org search: PML (static template for 2 search words).
-- Python org_search.py builds this dynamically; params @w0, @w1, @lim.
-- Table: {project}.{landing_dataset}.stg_pml

SELECT DISTINCT
  CAST(npi AS STRING) AS npi,
  TRIM(COALESCE(provider_name, '')) AS name
FROM `{project}.{landing_dataset}.stg_pml`
WHERE UPPER(TRIM(COALESCE(program_state, state, ''))) IN ('FL','FLORIDA')
  AND LOWER(COALESCE(provider_name,'')) LIKE CONCAT('%', LOWER(@w0), '%')
  AND LOWER(COALESCE(provider_name,'')) LIKE CONCAT('%', LOWER(@w1), '%')
ORDER BY name
LIMIT @lim;
