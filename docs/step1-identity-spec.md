# Step 1 — Establish Organization Identity
## Feature Spec & Test Scenarios

---

## What This Step Must Achieve

When the user leaves this page, the pipeline should have:
- A confirmed, persisted list of org NPIs that will anchor every downstream step
- Any deactivated / excluded NPIs explicitly flagged (not just "not selected")
- An audit note (optional, but available) explaining the selection
- A clear "Done" state so the user knows they can safely move on

---

## Feature Inventory

### ✅ EXISTS AND WORKING
| Feature | Notes |
|---|---|
| NPPES org search by name | Searches FL by default, returns up to 20 candidates |
| NPI card grid display | Shows name, address, phone, taxonomy, Active badge |
| Multi-select checkboxes | Toggle per card, count shown |
| Pre-select from prior validation | If previously confirmed, those NPIs are pre-checked |
| "Previously confirmed on [date]" badge | Shows at top when prior assertion exists |
| Confirm button → persist | POST `/validate` with `org_npis: [...]` |
| Per-card task creation (📋 icon) | Opens popover with context pre-filled |
| Step mission banner | Question + status chips (org NPIs confirmed) |

### ❌ MISSING — Must Build Before Step 1 Is Complete
| Feature | Why It Matters |
|---|---|
| **Manual NPI entry** | NPPES search misses some orgs; user may already know the NPI |
| **Re-search by different name** | Search returns wrong results; user shouldn't need a new run |
| **Explicit NPI exclusion / deactivation** | "Not selected" is ambiguous — was it overlooked or intentionally excluded? |
| **Deactivation reason** | Audit trail: "Location closed", "Merged", "Wrong entity" etc. |
| **NPI Type badge** (Type 1 = individual, Type 2 = org) | For org identity step, Type 2 is expected; surfacing helps user verify |
| **Completion summary on re-visit** | When navigating back to a done step, show "You confirmed: [list]" prominently |
| **Audit note for the step** | Free-text: "Selected NPIs 1-4; NPI 5 excluded — merged into main entity" |
| **NPPES data freshness warning** | If NPPES response was cached >30 days, warn to re-verify |
| **Empty state recovery action** | "No results" currently shows static text — needs "Try different name" input inline |

### 🟡 PARTIAL — Works But Needs Polish
| Feature | Gap |
|---|---|
| NPI card detail | Missing: entity type (Type 1/2), enumeration date, last updated date |
| Status badge | "Active" shown but "Inactive / Deactivated" not shown distinctly in red |
| Selection count | Updates correctly but doesn't warn if 0 selected before confirming |
| Confirm button label | Says "Confirm selected NPIs" but doesn't mention the count until after first toggle |

---

## Full Feature List (Complete Page Spec)

### 1. Org Search
- Search by org name (current)
- **Re-search input** — inline field to try a different name without leaving the step
- **Search by NPI** — if user knows the NPI, let them type it directly

### 2. NPI Card Display
Each card shows:
- ✅ Org name (from NPPES)
- ✅ NPI number (monospace)
- ✅ Active / Inactive status badge
- ❌ **Entity type** — Type 1 (Individual) / Type 2 (Organization) — flag Type 1 as unusual for org step
- ✅ Address + phone
- ✅ Taxonomy + code
- ❌ **Enumeration date** — when the NPI was created
- ❌ **Last NPPES update date**
- ✅ Task creation icon

### 3. Selection & Decisions
- ✅ Select / deselect toggle
- ✅ Bulk: select all / deselect all
- ❌ **Explicit exclusion** — mark NPI as "Not ours" with reason (different from just not selecting)
  - Reasons: Wrong entity, Location closed, Merged into another NPI, Retired
- ❌ **Manual add** — type an NPI number → fetches NPPES data → adds card

### 4. Confirmation & Persistence
- ✅ Confirm button → POST `/validate` with selected NPIs
- ❌ **Step note** — optional free-text note saved with the assertion
- ✅ After confirm: step marked done, moves to Step 2
- ❌ **Completion summary** when revisiting: "Confirmed [N] NPIs on [date]" + expandable list

### 5. Re-visit (Completed Step)
- ❌ Show confirmed NPI cards highlighted in green
- ❌ Show any explicitly excluded NPIs in grey with reason
- ❌ "Re-confirm" button to update selections (triggers re-validation)
- ❌ Show step note if one was entered

---

## Test Scenarios

### Scenario 1: Happy Path — All NPIs Found and Correct
```
GIVEN a new run for "David Lawrence Center"
WHEN Step 1 runs
THEN 6 NPI cards are displayed with name, address, taxonomy
AND each card shows Active/Inactive status
AND all 6 are pre-selected
WHEN user reviews and clicks "Confirm 6 NPIs"
THEN POST /validate is called with org_npis: [list of 6]
AND step advances to Step 2
AND completed_steps now includes "identify_org"
WHEN user navigates back to Step 1
THEN "Previously confirmed on [date]" badge is shown
AND the 6 confirmed NPIs are pre-selected (green)
```

### Scenario 2: Partial Selection — Some NPIs Don't Belong
```
GIVEN Step 1 shows 6 NPIs for "David Lawrence Center"
AND 2 of them are a different Florida org with same name fragment
WHEN user deselects the 2 incorrect NPIs
AND clicks "Confirm 4 NPIs"
THEN only 4 NPIs are persisted
AND Step 2 (locations) uses only those 4 NPIs for address lookup
```

### Scenario 3: Manual NPI Entry — NPI Not in Search Results
```
GIVEN Step 1 runs and returns 3 NPIs
AND the user knows there is a 4th NPI not in the results
WHEN user clicks "Add NPI manually"
AND enters "1234567890"
THEN system fetches NPI from NPPES
AND a new card appears with the fetched details
AND the card is pre-selected
WHEN user confirms
THEN all 4 NPIs (3 found + 1 manual) are persisted
```

### Scenario 4: No Results — Empty State Recovery
```
GIVEN user starts run for "DLC Behavioral Health" (slight variation)
WHEN Step 1 runs and returns 0 NPIs
THEN empty state is shown: "No NPIs found for this name"
AND an inline input is shown: "Try a different name" or "Enter NPI directly"
WHEN user types "David Lawrence Center" in the re-search input
THEN a new NPPES search runs
AND results are displayed without creating a new run
```

### Scenario 5: Re-search — Wrong Results
```
GIVEN Step 1 returns NPIs but all are for a different entity
WHEN user clicks "Search different name"
AND enters a new org name
THEN new NPPES search fires
AND cards are replaced with new results
AND previous selections are cleared
```

### Scenario 6: Explicit Deactivation / Exclusion
```
GIVEN previously confirmed 6 NPIs
WHEN user returns to Step 1 to update selections
AND one NPI is for a location that has closed
WHEN user clicks "Exclude" on that NPI card
AND selects reason: "Location closed"
THEN that NPI is marked as excluded (not just unselected)
AND reason is persisted
AND downstream steps (locations, NPPES) do not use this NPI
WHEN user navigates back to Step 1 later
THEN excluded NPI shows in grey with reason label
```

### Scenario 7: Re-confirm After Prior Validation
```
GIVEN Step 1 was completed, "Previously confirmed on Mar 15" badge shows
AND user is re-running to update (e.g. new location added new NPI)
WHEN user adds a new NPI card and re-confirms
THEN the assertion is updated with the new NPI list
AND updated_at timestamp is refreshed
AND Step 2 re-runs using the updated NPI list
```

### Scenario 8: Step Note / Audit Trail
```
GIVEN user has selected 4 NPIs
AND types note: "Excluded NPI 1234567890 — merged into 9876543210 on 3/1/26"
WHEN user confirms
THEN note is persisted alongside the NPI selection
WHEN user revisits Step 1
THEN note is displayed under the confirmed NPI list
```

### Scenario 9: Persistence Across Navigation
```
GIVEN user is on Step 1 in Copilot mode
AND selects 4 NPIs but does NOT yet click Confirm
WHEN user navigates to dashboard and returns to the run
THEN Step 1 is still in awaiting_validation state
AND the 4 selections are NOT preserved (selections are client-only until confirmed)
→ EXPECTED: user must re-select and confirm
```

### Scenario 10: Type 1 vs Type 2 NPI Warning
```
GIVEN Step 1 returns NPIs including one Type 1 (individual) NPI
THEN that card shows a warning: "Type 1 — Individual provider, not an org NPI"
AND the card is NOT pre-selected (Type 2 cards are pre-selected)
AND user must explicitly select it to include it
```

---

## API Test Script (curl)

```bash
#!/bin/bash
BASE="http://localhost:8000"

# 1. Create a new run
RUN=$(curl -s -X POST "$BASE/chat/credentialing-runs" \
  -H "Content-Type: application/json" \
  -d '{"org_name":"David Lawrence Center","mode":"copilot"}')
RUN_ID=$(echo $RUN | python3 -c "import sys,json; print(json.load(sys.stdin)['run_id'])")
echo "Run ID: $RUN_ID"

# 2. Poll until Step 1 is awaiting validation
sleep 15
STATE=$(curl -s "$BASE/chat/credentialing-runs/$RUN_ID?full=1")
PHASE=$(echo $STATE | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('phase',''))")
STEP=$(echo $STATE | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('pending_step_id',''))")
echo "Phase: $PHASE  Step: $STEP"

# 3. Get org NPIs with NPPES details
NPI_DATA=$(curl -s "$BASE/chat/credentialing-runs/$RUN_ID/org-npis")
echo "NPI data keys: $(echo $NPI_DATA | python3 -c "import sys,json; d=json.load(sys.stdin); print(list(d.keys()))")"
NPIS=$(echo $NPI_DATA | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('npis',[]))")
echo "NPIs found: $NPIS"

# 4. Confirm NPI selection (use first 2 if found)
SEL=$(echo $NPI_DATA | python3 -c "import sys,json; d=json.load(sys.stdin); npis=d.get('npis',[]); print(json.dumps(npis[:2]))")
VALIDATE=$(curl -s -X POST "$BASE/chat/credentialing-runs/$RUN_ID/validate" \
  -H "Content-Type: application/json" \
  -d "{\"step_id\":\"identify_org\",\"validated_output\":{\"org_npis\":$SEL}}")
echo "Validate response phase: $(echo $VALIDATE | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('phase',''))")"

# 5. Re-fetch and confirm step is done
sleep 3
FINAL=$(curl -s "$BASE/chat/credentialing-runs/$RUN_ID?full=1")
COMPLETED=$(echo $FINAL | python3 -c "import sys,json; d=json.load(sys.stdin); print(list((d.get('validated_outputs') or {}).keys()))")
echo "Completed steps: $COMPLETED"

# 6. Verify org_npis persisted in step draft
DRAFT_NPIS=$(echo $FINAL | python3 -c "import sys,json; d=json.load(sys.stdin); drafts=d.get('step_drafts',{}); id_draft=drafts.get('identify_org',{}); print(id_draft.get('org_npis',[]))")
echo "Persisted org_npis: $DRAFT_NPIS"

# 7. Delete the test run (cleanup)
curl -s -X DELETE "$BASE/chat/credentialing-runs/$RUN_ID"
echo "Run deleted."
```

---

## Build Priority

| Priority | Feature | Effort |
|---|---|---|
| 🔴 P0 | Manual NPI entry (add by typing NPI) | Medium |
| 🔴 P0 | Re-search by different name | Small |
| 🔴 P0 | Completion summary on re-visit (show confirmed list clearly) | Small |
| 🟡 P1 | Explicit exclusion with reason | Medium |
| 🟡 P1 | Entity type (Type 1 vs Type 2) badge on cards | Small |
| 🟡 P1 | Step note / audit text field | Small |
| 🟢 P2 | Enumeration date + last updated on card | Small |
| 🟢 P2 | NPPES data freshness warning | Small |
