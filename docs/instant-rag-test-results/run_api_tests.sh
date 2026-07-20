#!/usr/bin/env bash
# Automated instant-RAG API tests: upload each doc to RAG, poll until searchable,
# check retrieval of the verification phrase + key facts. Re-runnable.
RAG="https://mobius-rag-ortabkknqa-uc.a.run.app"
DL="$HOME/Downloads"
OUT="/Users/ananth/Mobius/docs/instant-rag-test-results/raw/api_results.txt"
: > "$OUT"
run_case () {
  local id="$1" file="$2" query="$3" phrase="$4" facts="$5" maxwait="$6"
  echo "===== CASE $id : $file =====" >> "$OUT"
  local sz; sz=$(wc -c < "$DL/$file" 2>/dev/null)
  local t0; t0=$(date +%s)
  local resp; resp=$(curl -sS -X POST "$RAG/upload?ttl_days=7&agent_scope=chat&payer=instant-rag" -F "file=@$DL/$file" --max-time 120 2>/dev/null)
  local did; did=$(echo "$resp" | grep -o '"document_id":"[^"]*"' | head -1 | cut -d'"' -f4)
  local ul=$(( $(date +%s) - t0 ))
  echo "size_bytes=$sz  upload_latency_s=$ul  document_id=$did" >> "$OUT"
  local found_phrase="NO" found_facts="NO" tts="TIMEOUT"
  for i in $(seq 1 $((maxwait/2))); do
    local hit; hit=$(curl -sS -X POST "$RAG/api/query" -H "Content-Type: application/json" \
      -d "{\"query\":\"$query\",\"document_id\":\"$did\",\"k\":5}" --max-time 20 2>/dev/null)
    if echo "$hit" | grep -qiF "$phrase"; then found_phrase="YES"; fi
    local fok="YES"; for f in $facts; do echo "$hit" | grep -qiF "$f" || fok="NO"; done
    found_facts="$fok"
    if [ "$found_phrase" = "YES" ]; then tts=$(( $(date +%s) - t0 )); echo "$hit" > "/Users/ananth/Mobius/docs/instant-rag-test-results/raw/${id}_query.json"; break; fi
    sleep 2
  done
  echo "time_to_searchable_s=$tts  phrase_retrieved=$found_phrase  facts_retrieved=$found_facts  (facts checked: $facts)" >> "$OUT"
  echo "" >> "$OUT"
}
echo "RUN START $(date -u +%FT%TZ)  |  RAG rev: $(gcloud run services describe mobius-rag --region=us-central1 --project=mobius-os-dev --format='value(status.traffic[0].revisionName)' 2>/dev/null)" >> "$OUT"
echo "" >> "$OUT"
run_case A_small_txt        t_alpha_quickfacts.txt "Cedar Point Wellness clients counties copper falcon" "copper falcon 12" "CPW-5120 2,900" 60
run_case B_multifact_txt    t_bravo_payer.txt      "Harborline prior authorization window H2015 rate claim deadline indigo walrus" "indigo walrus 55" "18 27.30 120" 60
run_case C_html             t_charlie_policy.html  "Stonebridge covered services sessions bronze marmot" "bronze marmot 07" "52 SBC-9040" 60
run_case D_pdf              t_delta_auth.pdf        "Ridgeway authorization partial hospitalization scarlet heron" "scarlet heron 88" "RWH-AUTH-7719 25" 60
run_case E_large_1_6MB     t_foxtrot_large.txt     "Northwind entity code H0038 rate cobalt lynx" "cobalt lynx 91" "FOX-7788 18.90" 200
echo "RUN END $(date -u +%FT%TZ)" >> "$OUT"
