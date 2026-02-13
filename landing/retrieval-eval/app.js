(() => {
  const API = (window.localStorage.getItem("retrieval_eval_api") || "http://127.0.0.1:8020").replace(/\/+$/, "");

  const $ = (id) => document.getElementById(id);
  const suiteSelect = $("suite-select");
  const apiStatus = $("api-status");
  const docsSelect = $("spec-docs");

  async function api(path, opts) {
    const url = API + path;
    const res = await fetch(url, {
      headers: { "Content-Type": "application/json" },
      ...opts,
    });
    const text = await res.text();
    let data;
    try {
      data = text ? JSON.parse(text) : {};
    } catch {
      data = { raw: text };
    }
    if (!res.ok) {
      const msg = (data && (data.detail || data.error)) ? (data.detail || data.error) : `HTTP ${res.status}`;
      throw new Error(msg);
    }
    return data;
  }

  function setApiOk(ok, msg) {
    apiStatus.textContent = ok ? `API: up` : `API: down`;
    apiStatus.title = msg || "";
    apiStatus.style.borderColor = ok ? "rgba(34,197,94,0.35)" : "rgba(239,68,68,0.35)";
  }

  async function ping() {
    try {
      await api("/health");
      setApiOk(true);
    } catch (e) {
      setApiOk(false, String(e && e.message ? e.message : e));
    }
  }

  function suiteId() {
    return suiteSelect.value || "";
  }

  function readSpec() {
    const spec = {};
    const authority = $("spec-authority").value.trim();
    if (authority) spec.document_authority_level = authority;
    // Selected documents
    try {
      const selected = Array.from(docsSelect.selectedOptions || []).map((o) => o.value).filter(Boolean);
      if (selected.length) spec.document_ids = selected;
    } catch {}
    const topk = parseInt($("spec-topk").value || "10", 10);
    if (Number.isFinite(topk)) spec.top_k = topk;
    const limitqStr = $("spec-limitq").value.trim();
    if (limitqStr) {
      const limitq = parseInt(limitqStr, 10);
      if (Number.isFinite(limitq)) spec.limit_questions = limitq;
    }
    const bm25th = parseFloat($("spec-bm25th").value || "0.65");
    if (Number.isFinite(bm25th)) spec.bm25_answer_threshold = bm25th;
    const hierth = parseFloat($("spec-hierth").value || "0.88");
    if (Number.isFinite(hierth)) spec.hier_answer_threshold = hierth;
    return spec;
  }

  function writeSpec(spec) {
    spec = spec || {};
    $("spec-authority").value = spec.document_authority_level || "";
    // document_ids are stored in suite_spec; selection is set after docs load
    $("spec-topk").value = (spec.top_k != null ? String(spec.top_k) : "10");
    $("spec-limitq").value = (spec.limit_questions != null ? String(spec.limit_questions) : "");
    $("spec-bm25th").value = (spec.bm25_answer_threshold != null ? String(spec.bm25_answer_threshold) : "0.65");
    $("spec-hierth").value = (spec.hier_answer_threshold != null ? String(spec.hier_answer_threshold) : "0.88");
  }

  async function loadDocuments(opts) {
    opts = opts || {};
    const force = !!opts.force;
    const statusEl = $("docs-status");
    statusEl.textContent = "Loading docs…";
    statusEl.style.color = "";
    try {
      const q = ($("doc-search").value || "").trim();
      const qs = [];
      qs.push(`limit=500`);
      if (q) qs.push(`search=${encodeURIComponent(q)}`);
      // Force refresh: bypass stale-cache fallback so the user can tell when DB is saturated.
      qs.push(`allow_stale=${force ? "0" : "1"}`);
      if (force) qs.push(`cache_bust=${Date.now()}`);
      const data = await api(`/api/documents?${qs.join("&")}`);
      const docs = data.documents || [];
      const currentSpec = readSpec();
      const selectedIds = new Set((currentSpec.document_ids || []).map(String));

      // Detect duplicates by label so we can disambiguate with short document_id.
      const labelCounts = new Map();
      for (const d of docs) {
        const label = (d.document_label || d.document_display_name || d.document_filename || d.document_id || "").trim();
        labelCounts.set(label, (labelCounts.get(label) || 0) + 1);
      }

      docsSelect.innerHTML = "";
      for (const d of docs) {
        const opt = document.createElement("option");
        opt.value = d.document_id;
        const label = (d.document_label || d.document_display_name || d.document_filename || d.document_id || "").trim();
        const dup = (labelCounts.get(label) || 0) > 1;
        const shortId = String(d.document_id || "").slice(0, 8);
        const name = dup ? `${label} (${shortId})` : label;
        const hier = d.hierarchical_rows != null ? `hier=${d.hierarchical_rows}` : "";
        const fact = d.fact_rows != null ? `fact=${d.fact_rows}` : "";
        const payer = d.document_payer ? `payer=${d.document_payer}` : "";
        const state = d.document_state ? `state=${d.document_state}` : "";
        const program = d.document_program ? `program=${d.document_program}` : "";
        opt.textContent = `${name} — ${[hier, fact, payer, state, program].filter(Boolean).join(" ")}`.trim();
        opt.dataset.authority = d.document_authority_level || "";
        opt.dataset.payer = d.document_payer || "";
        opt.dataset.state = d.document_state || "";
        opt.dataset.program = d.document_program || "";
        opt.title = [
          `document_id=${d.document_id}`,
          d.document_authority_level ? `authority_level=${d.document_authority_level}` : "",
          d.document_filename ? `filename=${d.document_filename}` : "",
          d.updated_at ? `updated_at=${d.updated_at}` : "",
        ].filter(Boolean).join("\n");
        if (selectedIds.has(String(d.document_id))) opt.selected = true;
        docsSelect.appendChild(opt);
      }
      const stale = !!data.stale;
      const staleMsg = stale ? ` — STALE (cached_at=${data.cached_at || "?"})` : "";
      statusEl.textContent = docs.length
        ? `Docs loaded: ${docs.length}${staleMsg}`
        : `Docs loaded: 0${staleMsg} (check published_rag_metadata sync)`;
      if (stale) {
        statusEl.style.color = "var(--warning, #f59e0b)";
        statusEl.title = data.error ? String(data.error) : "Using cached docs due to DB error";
      } else {
        statusEl.title = "";
      }
    } catch (e) {
      statusEl.textContent = `Failed to load docs: ${String(e && e.message ? e.message : e)}`;
      statusEl.style.color = "var(--danger)";
      docsSelect.innerHTML = "";
    }
  }

  async function loadSuites(selectSuiteId) {
    const data = await api("/api/suites");
    const suites = data.suites || [];
    suiteSelect.innerHTML = "";
    for (const s of suites) {
      const opt = document.createElement("option");
      opt.value = s.id;
      opt.textContent = s.name;
      suiteSelect.appendChild(opt);
    }
    if (selectSuiteId) suiteSelect.value = selectSuiteId;
    if (!suiteSelect.value && suites.length) suiteSelect.value = suites[0].id;
    await loadSuiteDetails();
  }

  async function loadSuiteDetails() {
    const id = suiteId();
    if (!id) return;
    const data = await api(`/api/suites/${encodeURIComponent(id)}`);
    const suite = data.suite || {};
    writeSpec(suite.suite_spec || {});
    // Ensure docs are loaded then apply selection from suite_spec.document_ids
    try {
      await loadDocuments();
      const spec = suite.suite_spec || {};
      const sel = new Set((spec.document_ids || []).map(String));
      for (const o of Array.from(docsSelect.options || [])) {
        o.selected = sel.has(String(o.value));
      }
    } catch {}
    $("import-status").textContent = `Questions: ${(data.questions || []).length}`;
    await loadRuns();
  }

  function fmtDate(s) {
    if (!s) return "";
    try { return new Date(s).toLocaleString(); } catch { return String(s); }
  }

  async function loadRuns() {
    const id = suiteId();
    if (!id) return;
    const data = await api(`/api/runs?suite_id=${encodeURIComponent(id)}&limit=50`);
    const runs = data.runs || [];
    const wrap = $("runs");
    wrap.innerHTML = "";
    if (!runs.length) {
      wrap.innerHTML = `<div class="muted small">No runs yet.</div>`;
      return;
    }
    for (const r of runs) {
      const el = document.createElement("div");
      el.className = "run";
      const status = r.status || "unknown";
      const created = fmtDate(r.created_at);
      const err = r.error ? `<div class="muted small" style="color:var(--danger)">${escapeHtml(r.error)}</div>` : "";
      let summary = "";
      try {
        const s = r.summary || {};
        if (s && s.bm25 && s.hier && (s.questions_with_gold != null)) {
          const bm = s.bm25;
          const hi = s.hier;
          const bm3 = bm.hit_at_3 != null ? (Number(bm.hit_at_3) * 100).toFixed(1) + "%" : "—";
          const hi3 = hi.hit_at_3 != null ? (Number(hi.hit_at_3) * 100).toFixed(1) + "%" : "—";
          const goldN = s.questions_with_gold != null ? String(s.questions_with_gold) : "";
          summary = `<div class="muted small">Hit@3: BM25 ${escapeHtml(bm3)} • Hier ${escapeHtml(hi3)} • gold_q=${escapeHtml(goldN)}</div>`;
        }
      } catch {}
      el.innerHTML = `
        <div class="meta">
          <div class="status"><b>${escapeHtml(status)}</b> — <span class="muted">${created}</span></div>
          <div class="id">${escapeHtml(r.id)}</div>
          ${summary}
          ${err}
        </div>
        <div class="actions">
          <button data-open="${escapeAttr(r.id)}">Open</button>
        </div>
      `;
      el.querySelector("button[data-open]").onclick = () => openRun(r.id);
      wrap.appendChild(el);
    }
  }

  function escapeHtml(s) {
    return String(s || "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }
  function escapeAttr(s) { return escapeHtml(s).replace(/"/g, "&quot;"); }

  async function openRun(runId) {
    const data = await api(`/api/runs/${encodeURIComponent(runId)}`);
    const run = data.run || {};
    const rows = data.questions || [];

    $("run-view").style.display = "";
    $("qdetail").style.display = "none";
    $("run-title").textContent = `Run ${run.id}`;
    $("run-subtitle").textContent = `${run.status || ""} • created ${fmtDate(run.created_at)} • suite ${run.suite_id}`;

    const tbody = $("run-table").querySelector("tbody");
    tbody.innerHTML = "";
    for (const r of rows) {
      const tr = document.createElement("tr");
      const bmRank = r.bm25_gold_rank;
      const hRank = r.hier_gold_rank;
      const bmMax = r.bm25_max_norm_score;
      const hTop1 = r.hier_top1_similarity;
      const good = (typeof bmRank === "number" && bmRank <= 3) || (typeof hRank === "number" && hRank <= 3);
      tr.className = good ? "good" : "bad";
      tr.innerHTML = `
        <td class="qid">${escapeHtml(r.qid)}</td>
        <td>${escapeHtml(String(r.question || "").slice(0, 220))}</td>
        <td>${bmRank == null ? "" : escapeHtml(bmRank)}</td>
        <td>${bmMax == null ? "" : escapeHtml(Number(bmMax).toFixed(3))}</td>
        <td>${hRank == null ? "" : escapeHtml(hRank)}</td>
        <td>${hTop1 == null ? "" : escapeHtml(Number(hTop1).toFixed(3))}</td>
        <td><button data-q="${escapeAttr(r.qid)}">View</button></td>
      `;
      tr.querySelector("button[data-q]").onclick = () => openQuestion(runId, r.qid);
      tbody.appendChild(tr);
    }
  }

  async function openQuestion(runId, qid) {
    const data = await api(`/api/runs/${encodeURIComponent(runId)}/questions/${encodeURIComponent(qid)}`);
    const metric = data.metric || {};
    const rows = data.rows || [];

    $("qdetail").style.display = "";
    $("qdetail-title").textContent = `${metric.qid} — detail`;
    $("qdetail-subtitle").textContent = metric.question || "";

    const bm = rows.filter((r) => r.method === "bm25");
    const hi = rows.filter((r) => r.method === "hier");

    $("bm25-metric").textContent = `gold_rank=${metric.bm25_gold_rank ?? "—"} max_norm=${metric.bm25_max_norm_score != null ? Number(metric.bm25_max_norm_score).toFixed(3) : "—"}`;
    $("hier-metric").textContent = `gold_rank=${metric.hier_gold_rank ?? "—"} top1_sim=${metric.hier_top1_similarity != null ? Number(metric.hier_top1_similarity).toFixed(3) : "—"}`;

    $("bm25-rows").innerHTML = bm.map(renderItem).join("");
    $("hier-rows").innerHTML = hi.map(renderItem).join("");
  }

  function renderItem(r) {
    const rank = r.rank != null ? `#${r.rank}` : "";
    const score = r.score != null ? Number(r.score).toFixed(3) : "";
    const page = r.page_number != null ? `p${r.page_number}` : "";
    const matched = r.match ? "match" : "";
    const why = r.match_why ? `(${escapeHtml(r.match_why)})` : "";
    return `
      <div class="item">
        <div class="top">
          <div>${escapeHtml(rank)} <span class="muted">${escapeHtml(page)}</span> <span class="muted">${escapeHtml(matched)} ${why}</span></div>
          <div>${escapeHtml(score)}</div>
        </div>
        <div class="txt">${escapeHtml(r.snippet || "")}</div>
        <div class="muted small" style="margin-top:.25rem;">id: <span class="qid">${escapeHtml(r.item_id)}</span></div>
      </div>
    `;
  }

  async function createSuite() {
    const name = $("suite-name").value.trim();
    if (!name) return alert("Suite name is required");
    const res = await api("/api/suites", { method: "POST", body: JSON.stringify({ name, suite_spec: {} }) });
    $("suite-name").value = "";
    await loadSuites(res.suite_id);
  }

  async function saveSpec() {
    const id = suiteId();
    if (!id) return;
    const spec = readSpec();
    if (!spec.document_authority_level && (!spec.document_ids || !spec.document_ids.length)) {
      return alert("Select at least one document (or provide authority level).");
    }
    await api(`/api/suites/${encodeURIComponent(id)}/spec`, { method: "POST", body: JSON.stringify({ suite_spec: spec }) });
    await loadSuiteDetails();
  }

  async function importYaml() {
    const id = suiteId();
    if (!id) return;
    const y = $("yaml").value;
    if (!y.trim()) return alert("Paste YAML first");
    const res = await api(`/api/suites/${encodeURIComponent(id)}/questions/import-yaml`, { method: "POST", body: JSON.stringify({ yaml: y }) });
    $("import-status").textContent = `Imported. inserted=${res.inserted} updated=${res.updated} total=${res.total}` + (res.errors && res.errors.length ? ` (errors=${res.errors.length})` : "");
  }

  async function autoGenerate() {
    const id = suiteId();
    if (!id) return;
    const spec = readSpec();
    if (!spec.document_authority_level && (!spec.document_ids || !spec.document_ids.length)) {
      return alert("Select at least one document (or provide authority level) first.");
    }
    const total = parseInt($("gen-total").value || "20", 10);
    const canonical = parseInt($("gen-canonical").value || "6", 10);
    const out = parseInt($("gen-out").value || "3", 10);
    const statusEl = $("gen-status");
    statusEl.textContent = "Generating…";
    statusEl.style.color = "";
    try {
      const res = await api(`/api/suites/${encodeURIComponent(id)}/questions/auto-generate`, {
        method: "POST",
        body: JSON.stringify({ n_total: total, n_canonical: canonical, n_out_of_manual: out }),
      });
      if (res && res.yaml) {
        $("yaml").value = res.yaml;
      }
      const imp = (res && res.import) ? res.import : {};
      statusEl.textContent = `Done. inserted=${imp.inserted ?? "?"} updated=${imp.updated ?? "?"} total=${imp.total ?? "?"} evidence=${res.evidence_count ?? "?"}`;
      await loadSuiteDetails();
    } catch (e) {
      statusEl.textContent = `Failed: ${String(e && e.message ? e.message : e)}`;
      statusEl.style.color = "var(--danger)";
      throw e;
    }
  }

  async function runEval() {
    const id = suiteId();
    if (!id) return;
    const spec = readSpec();
    if (!spec.document_authority_level && (!spec.document_ids || !spec.document_ids.length)) {
      return alert("Select at least one document (or provide authority level).");
    }
    // Start run and immediately refresh runs list
    const res = await api(`/api/suites/${encodeURIComponent(id)}/runs`, { method: "POST", body: JSON.stringify({ suite_spec_override: spec }) });
    await loadRuns();
    // Poll run status until complete/failed (lightweight)
    pollRun(res.run_id);
  }

  async function pollRun(runId) {
    const started = Date.now();
    for (;;) {
      await new Promise((r) => setTimeout(r, 1500));
      let run;
      try {
        const data = await api(`/api/runs/${encodeURIComponent(runId)}`);
        run = data.run;
      } catch (e) {
        break;
      }
      if (!run) break;
      if (run.status === "completed" || run.status === "failed") {
        await loadRuns();
        return;
      }
      if (Date.now() - started > 10 * 60 * 1000) {
        return;
      }
    }
  }

  function loadSample() {
    $("yaml").value = `questions:\n- id: Q001\n  intent: factual\n  bucket: in_manual\n  question: What is the timely filing limit for initial claims submission?\n  gold:\n    expect_in_manual: true\n    parent_metadata_ids:\n    - 00000000-0000-0000-0000-000000000000\n- id: Q002\n  intent: canonical\n  bucket: in_manual\n  question: Summarize the key guidance in the provider manual section: \"Secure Provider Portal\".\n  gold:\n    expect_in_manual: true\n    crux_contains:\n    - \"Secure Provider Portal\"\n`;
  }

  function bind() {
    $("btn-create-suite").onclick = () => createSuite().catch((e) => alert(e.message));
    $("btn-refresh-suites").onclick = () => loadSuites().catch((e) => alert(e.message));
    suiteSelect.onchange = () => loadSuiteDetails().catch((e) => alert(e.message));
    $("btn-save-spec").onclick = () => saveSpec().catch((e) => alert(e.message));
    $("btn-import-yaml").onclick = () => importYaml().catch((e) => alert(e.message));
    $("btn-load-sample").onclick = () => loadSample();
    $("btn-auto-generate").onclick = () => autoGenerate().catch((e) => alert(e.message));
    $("btn-run").onclick = () => runEval().catch((e) => alert(e.message));
    $("btn-refresh-runs").onclick = () => loadRuns().catch((e) => alert(e.message));
    $("btn-refresh-docs").onclick = () => loadDocuments({ force: true }).catch((e) => alert(e.message));
    $("btn-clear-docs").onclick = () => { for (const o of Array.from(docsSelect.options || [])) o.selected = false; };
    $("doc-search").addEventListener("keydown", (ev) => { if (ev.key === "Enter") loadDocuments().catch((e) => alert(e.message)); });
    $("btn-close-run").onclick = () => { $("run-view").style.display = "none"; $("qdetail").style.display = "none"; };
    $("btn-close-qdetail").onclick = () => { $("qdetail").style.display = "none"; };
  }

  async function main() {
    bind();
    await ping();
    await loadDocuments();
    await loadSuites();
  }

  main().catch((e) => {
    setApiOk(false, String(e && e.message ? e.message : e));
  });
})();

