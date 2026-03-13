"""FastAPI app: Provider Roster / Credentialing report. POST /report, POST /report-from-steps, POST /search/org-names, POST /search/org-by-address, POST /find-locations."""
from __future__ import annotations

# Load env from mobius-config and skill dir so report LLM (Gemini/Vertex) credentials are available
from pathlib import Path as _Path
_skill_root = _Path(__file__).resolve().parent.parent
_workspace_root = _skill_root.parent.parent
for _env_path in (
    _workspace_root / "mobius-config" / ".env",
    _workspace_root / ".env",
    _skill_root.parent / ".env",
    _skill_root / ".env",
):
    if _env_path.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(_env_path, override=False)
        except Exception:
            pass

import base64
import logging
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import queue
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.associate_providers import find_associated_providers
from app.core import TAXONOMY_CODE_LABELS, build_full_report
from app.historic_billing import get_historic_billing_patterns
from app.pml_validation import validate_pml_rows
from app.missing_pml_enrollment import find_missing_pml_enrollment
from app.potential_revenue import estimate_potential_revenue
from app.opportunity_sizing import compute_opportunity_sizing
from app.utilization_benchmarks import (
    compute_org_benchmark,
    export_benchmarks_rows,
    fetch_hcpcs_state_benchmarks,
    populate_benchmarks_table,
)
from app.report_pipeline import run_narrative_critic
from app.waterfall_report import (
    TickAndTieError,
    build_report_context,
    generate_waterfall_draft,
    run_waterfall_composer,
    run_waterfall_validator,
)
from app.location_identification import find_locations_for_org
from app.org_search import search_org_names, search_org_by_address
from app.services_by_location import find_services_by_location

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Provider Roster / Credentialing API",
    version="0.1.0",
    description="Provider Roster / Credentialing report per organization (locations, NPIs, readiness, invalid combos, ghost billing). Org search by name or address.",
)


def _get_bq_client():
    from google.cloud import bigquery
    project = os.environ.get("BQ_PROJECT", "mobius-os-dev")
    return bigquery.Client(project=project)


def _get_datasets():
    project = os.environ.get("BQ_PROJECT", "mobius-os-dev")
    landing = os.environ.get("BQ_LANDING_MEDICAID_DATASET") or "landing_medicaid_npi_dev"
    return project, landing


class ReportRequest(BaseModel):
    """Request body for report generation."""

    org_name: str
    location_ids: list[str] | None = None
    locations_override: list[dict[str, Any]] | None = None
    npi_overrides: dict[str, dict[str, Any]] | None = None


class StepOutputItem(BaseModel):
    """Single step output for report-from-steps."""

    step_id: str
    label: str
    csv_content: str
    row_count: int


class ReportFromStepsRequest(BaseModel):
    """Request body for report-from-steps (waterfall pipeline from step outputs)."""

    org_name: str
    step_outputs: list[StepOutputItem]


class ReportValidateRequest(BaseModel):
    """Request for /report-from-steps/validate."""

    org_name: str
    step_outputs: list[StepOutputItem]
    draft_md: str


class ReportComposeRequest(BaseModel):
    """Request for /report-from-steps/compose."""

    org_name: str
    step_outputs: list[StepOutputItem]
    draft_md: str
    validation_report: str
    critique_report: str | None = None


class ReportChartsPdfRequest(BaseModel):
    """Request for /report-from-steps/charts-pdf."""

    org_name: str
    step_outputs: list[StepOutputItem]
    final_md: str


class SearchOrgNamesRequest(BaseModel):
    """Request body for org name search."""

    name: str
    state: str = "FL"
    limit: int = 20
    include_pml: bool = True
    entity_type_filter: str | None = "2"


class SearchOrgByAddressRequest(BaseModel):
    """Request body for org address search."""

    address_raw: str | None = None
    address_line_1: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    limit: int = 20
    include_pml: bool = True
    use_google: bool = True
    entity_type_filter: str | None = "2"


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "provider-roster-credentialing"}


@app.get("/health/charts-pdf")
async def health_charts_pdf() -> dict[str, Any]:
    """Report if charts (matplotlib) and PDF (weasyprint) are available."""
    charts_ok = False
    pdf_ok = False
    charts_err = ""
    pdf_err = ""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import seaborn as sns
        plt.figure()
        plt.close()
        charts_ok = True
    except ImportError as e:
        charts_err = str(e)
    except Exception as e:
        charts_err = str(e)
    try:
        from weasyprint import HTML
        html = HTML(string="<html><body><p>Test</p></body></html>")
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            pdf_path = Path(f.name)
        try:
            html.write_pdf(pdf_path)
            pdf_ok = True
        finally:
            pdf_path.unlink(missing_ok=True)
    except ImportError as e:
        pdf_err = str(e)
    except Exception as e:
        pdf_err = str(e)
    return {
        "charts_available": charts_ok,
        "pdf_available": pdf_ok,
        "charts_error": charts_err or None,
        "pdf_error": pdf_err or None,
    }


@app.post("/report")
async def report(req: ReportRequest) -> dict[str, Any]:
    """
    Generate Provider Roster / Credentialing report for the given org name.
    Optional: location_ids to restrict locations, npi_overrides per location_id (add/remove NPIs).
    """
    org_name = (req.org_name or "").strip()
    if not org_name:
        raise HTTPException(status_code=400, detail="org_name is required")
    project = os.environ.get("BQ_PROJECT", "mobius-os-dev")
    marts_dataset = os.environ.get("BQ_MARTS_MEDICAID_DATASET", "mobius_medicaid_npi_dev")
    landing_dataset = os.environ.get("BQ_LANDING_MEDICAID_DATASET", "landing_medicaid_npi_dev")
    try:
        from google.cloud import bigquery
        bq_client = bigquery.Client(project=project)
    except ImportError as e:
        logger.exception("BigQuery not available")
        raise HTTPException(status_code=503, detail="BigQuery client not available") from e
    except Exception as e:
        logger.exception("BigQuery client init failed")
        raise HTTPException(status_code=503, detail=str(e)) from e
    try:
        result = build_full_report(
            bq_client,
            org_name=org_name,
            project=project,
            marts_dataset=marts_dataset,
            landing_dataset=landing_dataset,
            location_ids=req.location_ids,
            locations_override=req.locations_override,
            npi_overrides=req.npi_overrides,
            state_filter=getattr(req, "state", None) or "FL",
        )
        return result
    except Exception as e:
        logger.exception("Report build failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/report-from-steps")
async def report_from_steps(req: ReportFromStepsRequest) -> dict[str, Any]:
    """
    Generate credentialing report from step outputs (draft → validator → composer).
    Returns draft_md, validation_report, final_md, charts[], pdf_path, pdf_base64.
    """
    org_name = (req.org_name or "").strip()
    if not org_name:
        raise HTTPException(status_code=400, detail="org_name is required")

    step_outputs = [
        {"step_id": s.step_id, "label": s.label, "csv_content": s.csv_content or "", "row_count": s.row_count}
        for s in (req.step_outputs or [])
    ]

    context = _build_report_context_or_422(step_outputs)

    try:
        from app.report_pdf import markdown_to_pdf
        from app.report_visuals import generate_charts, get_chart_spec_from_llm
    except ImportError as e:
        logger.warning("report_pdf/report_visuals import failed: %s", e)
        raise HTTPException(status_code=503, detail="Report PDF/charts not available") from e

    try:
        return _run_report_from_steps(org_name, context, step_outputs)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("report-from-steps failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


def _run_report_from_steps(org_name: str, context: dict[str, Any], step_outputs: list[dict]) -> dict[str, Any]:
    """Execute report pipeline (draft → validator → composer → deterministic check).
    Retries: up to 3 fresh drafts on validation BLOCK; up to 3 composer runs on chart reconcile + provider JSON."""
    from app.report_pdf import markdown_to_pdf
    from app.report_visuals import generate_charts, get_chart_spec_from_llm
    from app.step_output_validation import (
        get_source_provider_names_from_context,
        reconcile_report_waterfall_to_totals,
        validate_pipeline_values_preserved,
        validate_provider_tables_json,
    )

    wt = context.get("waterfall_totals") or {}

    provider, model = _report_llm_provider_and_model()

    draft_md = ""
    validation_report = ""
    critique_report = ""
    draft_max_tries = 3

    for draft_attempt in range(draft_max_tries):
        draft_md = generate_waterfall_draft(context, org_name, provider=provider, model=model)
        with ThreadPoolExecutor(max_workers=2) as ex:
            fut_numbers = ex.submit(run_waterfall_validator, draft_md, context, provider=provider, model=model)
            fut_narrative = ex.submit(run_narrative_critic, draft_md, provider=provider, model=model)
            validation_report = fut_numbers.result()
            critique_report = fut_narrative.result()

        if "Validation Status: BLOCK" not in (validation_report or ""):
            break
        logger.warning(
            "Draft validation BLOCK (attempt %d/%d), retrying with fresh draft",
            draft_attempt + 1,
            draft_max_tries,
        )
        if draft_attempt == draft_max_tries - 1:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": f"Report validation blocked after {draft_max_tries} draft attempts — truncation or cross-section contradictions",
                    "attempts": draft_max_tries,
                    "validation_report": validation_report,
                },
            )

    max_tries = 3
    additional_fixes: list[str] = []
    final_md = ""
    last_deterministic_errors: list[str] = []
    source_names = get_source_provider_names_from_context(context)

    for attempt in range(max_tries):
        final_md = run_waterfall_composer(
            draft_md,
            validation_report,
            context,
            org_name,
            critique_report=critique_report or "",
            additional_fixes=additional_fixes if attempt > 0 else None,
            provider=provider,
            model=model,
        )

        chart_reconcile = reconcile_report_waterfall_to_totals(final_md, wt)
        provider_errors, final_md_cleaned = validate_provider_tables_json(final_md, source_names)
        final_md = final_md_cleaned  # Strip JSON block before charts/delivery
        pipeline_preserved_errors = validate_pipeline_values_preserved(final_md, context)

        combined_errors = list(chart_reconcile or []) + list(provider_errors or []) + list(pipeline_preserved_errors or [])
        if not combined_errors:
            break

        last_deterministic_errors = combined_errors
        for err in combined_errors:
            logger.warning("Post-compose check (attempt %d/%d): %s", attempt + 1, max_tries, err)
        if attempt < max_tries - 1:
            additional_fixes = combined_errors
            logger.info("Retrying composer with %d fixes (chart + provider validation)", len(additional_fixes))

    if last_deterministic_errors:
        for err in last_deterministic_errors:
            logger.error("Chart reconciliation: %s", err)
        raise HTTPException(
            status_code=422,
            detail={
                "block": "chart_section_mismatch",
                "message": last_deterministic_errors[0],
                "errors": last_deterministic_errors,
                "attempts": max_tries,
            },
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir)
        prefix = "credentialing_report"
        report_for_charts = {"executive_summary": {"org_name": org_name}, "waterfall_totals": wt}
        metrics_for_charts = {"waterfall_totals": wt}
        chart_ids = get_chart_spec_from_llm(report_for_charts, metrics_for_charts, provider=provider, model=model)
        if not chart_ids and wt:
            chart_ids = ["revenue_waterfall"]
        charts = generate_charts(
            report_for_charts,
            metrics_for_charts,
            out_dir,
            prefix,
            chart_ids=chart_ids or None,
        )

        charts_section = ""
        charts_section_for_pdf = ""
        if charts:
            parts_base64 = []
            parts_file = []
            for c in charts:
                fn = c.get("filename")
                title = c.get("title", c.get("id", ""))
                if fn:
                    png_path = out_dir / fn
                    if png_path.exists():
                        b64 = base64.b64encode(png_path.read_bytes()).decode("ascii")
                        parts_base64.append(f"![{title}](data:image/png;base64,{b64})")
                        parts_file.append(f"![{title}]({fn})")
                    else:
                        fallback = f"*({title} — chart file not found)*"
                        parts_base64.append(fallback)
                        parts_file.append(fallback)
                else:
                    fallback = f"*({title})*"
                    parts_base64.append(fallback)
                    parts_file.append(fallback)
            charts_section = "\n\n## Charts\n\n" + "\n\n".join(parts_base64)
            charts_section_for_pdf = "\n\n## Charts\n\n" + "\n\n".join(parts_file)
        report_md = final_md + charts_section
        md_path = out_dir / f"{prefix}.md"
        md_path.write_text(report_md, encoding="utf-8")
        md_for_pdf = out_dir / f"{prefix}_pdf.md"
        md_for_pdf.write_text(final_md + charts_section_for_pdf, encoding="utf-8")
        pdf_path = out_dir / f"{prefix}.pdf"
        pdf_ok = markdown_to_pdf(md_for_pdf, pdf_path)
        pdf_base64 = ""
        if pdf_ok and pdf_path.exists():
            pdf_base64 = base64.b64encode(pdf_path.read_bytes()).decode("ascii")

        return {
            "draft_md": draft_md,
            "validation_report": validation_report,
            "critique_report": critique_report,
            "final_md": report_md,
            "charts": [{"id": c.get("id"), "filename": c.get("filename"), "title": c.get("title")} for c in charts],
            "pdf_base64": pdf_base64 if pdf_ok else None,
        }


def _build_report_context_or_422(step_outputs: list[dict[str, Any]]) -> dict[str, Any]:
    """Build report context; raise 422 on tick-and-tie failure."""
    try:
        return build_report_context(step_outputs)
    except TickAndTieError as e:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "Tick-and-tie validation failed — input data inconsistent",
                "tick_and_tie_errors": e.errors,
            },
        ) from e


def _report_llm_provider_and_model() -> tuple[str, str]:
    """Resolve LLM provider and model for report generation (shared by report endpoints)."""
    provider = os.environ.get("REPORT_LLM_PROVIDER", "openai")
    if provider == "openai" and not (os.environ.get("OPENAI_API_KEY") or "").strip():
        provider = "gemini"
        logger.info("OPENAI_API_KEY not set; using Gemini for report generation")
    model = os.environ.get("REPORT_LLM_MODEL") or (
        "gpt-4o" if provider == "openai"
        else (os.getenv("VERTEX_MODEL") or os.getenv("CHAT_VERTEX_MODEL") or "gemini-2.5-flash")
    )
    if provider == "gemini":
        has_key = bool((os.environ.get("GEMINI_API_KEY") or "").strip())
        has_vertex = bool((os.environ.get("BQ_PROJECT") or os.environ.get("VERTEX_PROJECT_ID") or "").strip())
        if not has_key and not has_vertex:
            raise HTTPException(503, "Gemini needs GEMINI_API_KEY or BQ_PROJECT/VERTEX_PROJECT_ID for Vertex.")
    return provider, model


def _draft_sse_generator(
    context: dict[str, Any],
    org_name: str,
    provider: str,
    model: str,
) -> Any:
    """Generator yielding SSE events: progress messages and final draft_md."""
    import threading
    q: queue.Queue = queue.Queue()
    KEEPALIVE_INTERVAL = 12  # seconds — yield comment to avoid proxy/client timeout during long LLM calls

    def _emit(msg: str) -> None:
        logger.debug("draft_sse: emitter %s", msg[:80])
        q.put({"type": "progress", "message": msg})

    def _run() -> None:
        try:
            logger.info("draft_sse: thread started, generating draft for %s", org_name[:50])
            draft_md = generate_waterfall_draft(
                context, org_name, provider=provider, model=model, emitter=_emit
            )
            q.put({"type": "complete", "draft_md": draft_md})
            logger.info("draft_sse: thread complete, draft len=%d", len(draft_md or ""))
        except Exception as e:
            logger.exception("draft_sse: thread error %s", e)
            q.put({"type": "error", "error": str(e)})

    t = threading.Thread(target=_run)
    t.start()
    # Yield immediately so client receives bytes and avoids IncompleteRead
    yield "data: {\"type\": \"progress\", \"message\": \"Starting draft…\"}\n\n"
    logger.debug("draft_sse: yielded starting event")
    while True:
        try:
            ev = q.get(timeout=KEEPALIVE_INTERVAL)
        except queue.Empty:
            # Send keepalive comment so proxy/client doesn't timeout during long LLM calls
            yield ": keepalive\n\n"
            logger.debug("draft_sse: keepalive")
            continue
        logger.debug("draft_sse: yielding event type=%s", ev.get("type"))
        yield f"data: {json.dumps(ev)}\n\n"
        if ev.get("type") in ("complete", "error"):
            break


@app.post("/report-from-steps/draft")
async def report_from_steps_draft(
    req: ReportFromStepsRequest,
    stream: bool = False,
) -> Any:
    """Step 11a: Generate draft report. Use ?stream=1 for SSE progress events."""
    org_name = (req.org_name or "").strip()
    if not org_name:
        raise HTTPException(status_code=400, detail="org_name is required")
    step_outputs = [{"step_id": s.step_id, "label": s.label, "csv_content": s.csv_content or "", "row_count": s.row_count} for s in (req.step_outputs or [])]
    provider, model = _report_llm_provider_and_model()
    context = _build_report_context_or_422(step_outputs)
    if stream:
        return StreamingResponse(
            _draft_sse_generator(context, org_name, provider, model),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    draft_md = generate_waterfall_draft(context, org_name, provider=provider, model=model)
    return {"draft_md": draft_md}


@app.post("/report-from-steps/validate")
async def report_from_steps_validate(req: ReportValidateRequest) -> dict[str, Any]:
    """Step 11b: Run number validation + narrative critique in parallel. Returns both."""
    org_name = (req.org_name or "").strip()
    if not org_name or not (req.draft_md or "").strip():
        raise HTTPException(status_code=400, detail="org_name and draft_md required")
    step_outputs = [{"step_id": s.step_id, "label": s.label, "csv_content": s.csv_content or "", "row_count": s.row_count} for s in (req.step_outputs or [])]
    provider, model = _report_llm_provider_and_model()
    context = _build_report_context_or_422(step_outputs)
    with ThreadPoolExecutor(max_workers=2) as ex:
        fut_numbers = ex.submit(run_waterfall_validator, req.draft_md, context, provider=provider, model=model)
        fut_narrative = ex.submit(run_narrative_critic, req.draft_md, provider=provider, model=model)
        validation_report = fut_numbers.result()
        critique_report = fut_narrative.result()
    return {"validation_report": validation_report, "critique_report": critique_report}


@app.post("/report-from-steps/compose")
async def report_from_steps_compose(req: ReportComposeRequest) -> dict[str, Any]:
    """Step 11c: Produce final report from draft + number validation + narrative critique."""
    org_name = (req.org_name or "").strip()
    if not org_name or not (req.draft_md or "").strip() or not (req.validation_report or "").strip():
        raise HTTPException(status_code=400, detail="org_name, draft_md, validation_report required")
    if "Validation Status: BLOCK" in (req.validation_report or ""):
        raise HTTPException(
            status_code=422,
            detail={
                "error": "Report validation blocked — composer cannot fix (truncation, cross-section contradictions)",
                "validation_report": req.validation_report,
            },
        )
    step_outputs = [{"step_id": s.step_id, "label": s.label, "csv_content": s.csv_content or "", "row_count": s.row_count} for s in (req.step_outputs or [])]
    provider, model = _report_llm_provider_and_model()
    context = _build_report_context_or_422(step_outputs)
    final_md = run_waterfall_composer(
        req.draft_md,
        req.validation_report,
        context,
        org_name,
        critique_report=req.critique_report or "",
        provider=provider,
        model=model,
    )
    return {"final_md": final_md}


@app.post("/report-from-steps/charts-pdf")
async def report_from_steps_charts_pdf(req: ReportChartsPdfRequest) -> dict[str, Any]:
    """Step 11d: Generate charts and PDF from final markdown. Call from orchestrator with progress emission."""
    org_name = (req.org_name or "").strip()
    final_md = (req.final_md or "").strip()
    if not org_name or not final_md:
        raise HTTPException(status_code=400, detail="org_name and final_md required")
    step_outputs = [{"step_id": s.step_id, "label": s.label, "csv_content": s.csv_content or "", "row_count": s.row_count} for s in (req.step_outputs or [])]
    provider, model = _report_llm_provider_and_model()
    context = _build_report_context_or_422(step_outputs)
    wt = context.get("waterfall_totals") or {}
    try:
        from app.report_pdf import markdown_to_pdf
        from app.report_visuals import generate_charts, get_chart_spec_from_llm
        from app.step_output_validation import reconcile_report_waterfall_to_totals
    except ImportError as e:
        logger.warning("report_pdf/report_visuals import failed: %s", e)
        raise HTTPException(status_code=503, detail="Report PDF/charts not available") from e

    # Chart-to-section reconciliation: ensure report text matches waterfall_totals before embedding chart
    chart_reconcile_errors = reconcile_report_waterfall_to_totals(final_md, wt)
    if chart_reconcile_errors:
        for err in chart_reconcile_errors:
            logger.error("Chart reconciliation: %s", err)
        raise HTTPException(
            status_code=422,
            detail={
                "block": "chart_section_mismatch",
                "message": chart_reconcile_errors[0],
                "errors": chart_reconcile_errors,
            },
        )

    report_for_charts = {"executive_summary": {"org_name": org_name}, "waterfall_totals": wt}
    metrics_for_charts = {"waterfall_totals": wt}
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir)
        prefix = "credentialing_report"
        chart_ids = get_chart_spec_from_llm(report_for_charts, metrics_for_charts, provider=provider, model=model)
        if not chart_ids and wt:
            chart_ids = ["revenue_waterfall"]
        charts = generate_charts(report_for_charts, metrics_for_charts, out_dir, prefix, chart_ids=chart_ids or None)
        if not charts and wt:
            logger.info("Charts empty but waterfall_totals present; check matplotlib/seaborn install and has_waterfall")
        charts_section = ""
        charts_section_for_pdf = ""
        if charts:
            parts_base64 = []
            parts_file = []
            for c in charts:
                fn = c.get("filename")
                title = c.get("title", c.get("id", ""))
                if fn:
                    png_path = out_dir / fn
                    if png_path.exists():
                        b64 = base64.b64encode(png_path.read_bytes()).decode("ascii")
                        parts_base64.append(f"![{title}](data:image/png;base64,{b64})")
                        parts_file.append(f"![{title}]({fn})")
                    else:
                        fallback = f"*({title} — chart file not found)*"
                        parts_base64.append(fallback)
                        parts_file.append(fallback)
                else:
                    fallback = f"*({title})*"
                    parts_base64.append(fallback)
                    parts_file.append(fallback)
            charts_section = "\n\n## Charts\n\n" + "\n\n".join(parts_base64)
            charts_section_for_pdf = "\n\n## Charts\n\n" + "\n\n".join(parts_file)
        report_md = final_md + charts_section
        md_path = out_dir / f"{prefix}.md"
        md_path.write_text(report_md, encoding="utf-8")
        md_for_pdf = out_dir / f"{prefix}_pdf.md"
        md_for_pdf.write_text(final_md + charts_section_for_pdf, encoding="utf-8")
        pdf_path = out_dir / f"{prefix}.pdf"
        pdf_ok = markdown_to_pdf(md_for_pdf, pdf_path)
        if not pdf_ok:
            logger.warning("PDF generation failed; check weasyprint and system deps (cairo, pango)")
        pdf_base64 = ""
        if pdf_ok and pdf_path.exists():
            pdf_base64 = base64.b64encode(pdf_path.read_bytes()).decode("ascii")
        return {
            "final_md": report_md,
            "charts": [{"id": c.get("id"), "filename": c.get("filename"), "title": c.get("title")} for c in charts],
            "pdf_base64": pdf_base64 if pdf_ok else None,
        }


@app.post("/search/org-names")
async def api_search_org_names(req: SearchOrgNamesRequest) -> dict[str, Any]:
    """Search NPPES and PML by org/provider name. Returns list of {npi, name, source, entity_type}."""
    name = (req.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    try:
        bq = _get_bq_client()
        project, landing = _get_datasets()
        results = search_org_names(
            bq,
            name,
            state_filter=req.state,
            limit=req.limit,
            include_pml=req.include_pml,
            entity_type_filter=req.entity_type_filter,
            project=project,
            landing_dataset=landing,
        )
        return {"results": results}
    except ImportError as e:
        raise HTTPException(status_code=503, detail="BigQuery client not available") from e
    except Exception as e:
        logger.exception("Org name search failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/search/org-by-address")
async def api_search_org_by_address(req: SearchOrgByAddressRequest) -> dict[str, Any]:
    """Search NPPES and PML by address. Pass address_raw or address_line_1/city/state/postal_code."""
    if not req.address_raw and not any([req.address_line_1, req.city, req.postal_code]):
        raise HTTPException(status_code=400, detail="address_raw or (address_line_1, city, state, postal_code) required")
    try:
        bq = _get_bq_client()
        project, landing = _get_datasets()
        norm, results = search_org_by_address(
            bq,
            address_raw=req.address_raw,
            address_line_1=req.address_line_1,
            city=req.city,
            state=req.state or "FL",
            postal_code=req.postal_code,
            limit=req.limit,
            include_pml=req.include_pml,
            use_google=req.use_google,
            entity_type_filter=req.entity_type_filter,
            project=project,
            landing_dataset=landing,
        )
        if norm is None:
            return {"normalized_address": None, "results": [], "error": "Could not normalize address (need valid ZIP5)"}
        return {"normalized_address": norm, "results": results}
    except ImportError as e:
        raise HTTPException(status_code=503, detail="BigQuery client not available") from e
    except Exception as e:
        logger.exception("Org address search failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


class FindLocationsRequest(BaseModel):
    """Request body for find locations (Step 2)."""

    org_npis: list[str]
    initial_sites: list[dict[str, Any]] | None = None
    state: str = "FL"


@app.post("/find-locations")
async def api_find_locations(req: FindLocationsRequest) -> dict[str, Any]:
    """Find all practice locations for an org. Input: org_npis (from Step 1 find-org), optional initial_sites."""
    if not req.org_npis:
        raise HTTPException(status_code=400, detail="org_npis required")
    try:
        bq = _get_bq_client()
        project, landing = _get_datasets()
        locations = find_locations_for_org(
            bq,
            req.org_npis,
            initial_sites=req.initial_sites,
            state_filter=req.state,
            project=project,
            landing_dataset=landing,
        )
        return {"locations": locations, "count": len(locations)}
    except ImportError as e:
        raise HTTPException(status_code=503, detail="BigQuery client not available") from e
    except Exception as e:
        logger.exception("Find locations failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


class FindAssociatedProvidersRequest(BaseModel):
    """Request body for find associated providers (Step 3)."""

    org_npis: list[str]
    locations: list[dict[str, Any]]
    org_name: str = ""


@app.post("/find-associated-providers")
async def api_find_associated_providers(req: FindAssociatedProvidersRequest) -> dict[str, Any]:
    """Find all associated facilities and providers per location. Step 3."""
    if not req.org_npis or not req.locations:
        raise HTTPException(status_code=400, detail="org_npis and locations required")
    try:
        bq = _get_bq_client()
        project, landing = _get_datasets()
        out = find_associated_providers(
            bq,
            req.locations,
            req.org_npis,
            project=project,
            landing_dataset=landing,
            state_filter="FL",
            org_name=req.org_name or "",
        )
        associated = out.get("associated_providers") or {}
        active_roster = out.get("active_roster") or {}
        total = sum(len(v) for v in associated.values())
        return {
            "associated_providers": associated,
            "active_roster": active_roster,
            "active_roster_cutoff": out.get("active_roster_cutoff"),
            "locations_count": len(associated),
            "providers_count": total,
        }
    except ImportError as e:
        raise HTTPException(status_code=503, detail="BigQuery client not available") from e
    except Exception as e:
        logger.exception("Find associated providers failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


class FindServicesByLocationRequest(BaseModel):
    """Request body for find services by location (Step 5)."""

    org_npis: list[str]
    locations: list[dict[str, Any]]
    associated_providers: dict[str, list[dict[str, Any]]]
    state: str = "FL"


class HistoricBillingRequest(BaseModel):
    """Request body for historic billing patterns (Step 5)."""

    associated_providers: dict[str, list[dict[str, Any]]]
    period_start: str = "2024-01"
    period_end: str = "2024-12"


class PmlValidationRequest(BaseModel):
    """Request body for PML validation (Step 6)."""

    org_npis: list[str]
    locations: list[dict[str, Any]]
    associated_providers: dict[str, list[dict[str, Any]]]
    program_state: str = "FL"
    product: str = "medicaid"


class MissingPmlEnrollmentRequest(BaseModel):
    """Request body for Step 7: missing PML enrollment."""

    locations: list[dict[str, Any]]
    active_roster: dict[str, list[dict[str, Any]]]


class EnsureBenchmarksRequest(BaseModel):
    """Request body for Step 9: ensure taxonomy_utilization_benchmarks table is populated."""

    period: str = "2024"
    state: str = "FL"


class OrgBenchmarkRequest(BaseModel):
    """Request body for org benchmark: utilization metrics for active roster NPIs."""

    active_roster: dict[str, list[dict[str, Any]]]
    period: str = "2024"


class OpportunitySizingRequest(BaseModel):
    """Request body for opportunity sizing (Step 10): revenue waterfall A–E."""

    validated: list[dict[str, Any]]
    flagged: list[dict[str, Any]]
    missing_enrollment: list[dict[str, Any]]
    org_benchmark: dict[str, Any] | None = None
    member_proxy: int = 100


class PotentialRevenueRequest(BaseModel):
    """Request body for Step 10: potential revenue for missed/errored NPIs."""

    missing_enrollment: list[dict[str, Any]]
    flagged: list[dict[str, Any]] | None = None
    member_proxy: int = 100
    org_benchmark: dict[str, Any] | None = None


@app.post("/ensure-benchmarks")
async def api_ensure_benchmarks(req: EnsureBenchmarksRequest) -> dict[str, Any]:
    """
    Step 9: Populate taxonomy_utilization_benchmarks table. Run at start of flow.
    Emit: "I am ensuring the revenue metrics are in place…" while running.
    """
    try:
        bq = _get_bq_client()
        project = os.environ.get("BQ_PROJECT", "mobius-os-dev")
        landing = os.environ.get("BQ_LANDING_MEDICAID_DATASET", "landing_medicaid_npi_dev")
        marts = os.environ.get("BQ_MARTS_MEDICAID_DATASET", "mobius_medicaid_npi_dev")
        result = populate_benchmarks_table(
            bq,
            project=project,
            landing_dataset=landing,
            marts_dataset=marts,
            period=req.period,
            state_filter=req.state,
        )
        return result
    except ImportError:
        raise HTTPException(status_code=503, detail="BigQuery client not available")
    except Exception as e:
        logger.exception("Ensure benchmarks failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


class BenchmarksExportRequest(BaseModel):
    """Request for benchmarks CSV export. Filter to client-relevant taxonomies and ZIPs."""

    period: str = "2024"
    taxonomy_codes: list[str] | None = None
    zip5_list: list[str] | None = None


@app.post("/benchmarks-export")
async def api_benchmarks_export(req: BenchmarksExportRequest) -> dict[str, Any]:
    """
    Export taxonomy_utilization_benchmarks as rows for CSV download.
    Optional taxonomy_codes and zip5_list filter to client-relevant rows only.
    Returns {"rows": [...], "count": int}.
    """
    try:
        bq = _get_bq_client()
        project = os.environ.get("BQ_PROJECT", "mobius-os-dev")
        marts = os.environ.get("BQ_MARTS_MEDICAID_DATASET", "mobius_medicaid_npi_dev")
        rows = export_benchmarks_rows(
            bq,
            project=project,
            marts_dataset=marts,
            period=req.period,
            taxonomy_codes=req.taxonomy_codes,
            zip5_list=req.zip5_list,
        )
        return {"rows": rows, "count": len(rows)}
    except ImportError:
        raise HTTPException(status_code=503, detail="BigQuery client not available")
    except Exception as e:
        logger.exception("Benchmarks export failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


class HcpcsStateBenchmarksRequest(BaseModel):
    """Request for FL HCPCS-level state benchmarks (revenue_per_claim by code)."""

    period: str = "2024"
    state: str = "FL"


@app.post("/hcpcs-state-benchmarks")
async def api_hcpcs_state_benchmarks(req: HcpcsStateBenchmarksRequest) -> dict[str, Any]:
    """
    Fetch HCPCS-level FL state benchmarks (revenue_per_claim) from DOGE.
    Used for Section E rate gap table: DLC avg vs FL state avg by HCPCS.
    Returns {"rows": [{hcpcs_code, claim_count, total_paid, revenue_per_claim}], "count": int}.
    """
    try:
        bq = _get_bq_client()
        project, landing = _get_datasets()
        marts = os.environ.get("BQ_MARTS_MEDICAID_DATASET", "mobius_medicaid_npi_dev")
        rows = fetch_hcpcs_state_benchmarks(
            bq,
            project=project,
            landing_dataset=landing,
            marts_dataset=marts,
            period=req.period,
            state_filter=req.state,
        )
        return {"rows": rows, "count": len(rows)}
    except ImportError:
        raise HTTPException(status_code=503, detail="BigQuery client not available")
    except Exception as e:
        logger.exception("HCPCS state benchmarks failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/org-benchmark")
async def api_org_benchmark(req: OrgBenchmarkRequest) -> dict[str, Any]:
    """
    Utilization metrics for active roster NPIs tied to this org (claims/member, revenue/member, revenue/claim).
    Computed on-the-fly from DOGE. Use as first fallback in Step 10 potential revenue.
    """
    if not req.active_roster:
        return {}
    npis = []
    for provs in req.active_roster.values():
        for p in provs or []:
            n = (p.get("npi") or p.get("servicing_npi") or "").strip().zfill(10)
            if n and n != "0000000000":
                npis.append(n)
    npis = list(dict.fromkeys(npis))
    if not npis:
        return {}
    try:
        bq = _get_bq_client()
        project, landing = _get_datasets()
        result = compute_org_benchmark(
            bq,
            npis,
            project=project,
            landing_dataset=landing,
            period=req.period,
        )
        return result
    except ImportError:
        raise HTTPException(status_code=503, detail="BigQuery client not available")
    except Exception as e:
        logger.exception("Org benchmark failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/potential-revenue")
async def api_potential_revenue(req: PotentialRevenueRequest) -> dict[str, Any]:
    """
    Step 10: Estimate potential revenue for NPIs not enrolled (Step 7) or flagged (Step 6).
    Uses taxonomy_utilization_benchmarks (populate via mobius-dbt/scripts/populate_utilization_benchmarks.py).
    """
    if not req.missing_enrollment and not req.flagged:
        return {"by_npi": [], "summary": {"total_npis": 0, "total_estimated_revenue": 0.0, "with_benchmark": 0}}
    try:
        bq = _get_bq_client()
        project = os.environ.get("BQ_PROJECT", "mobius-os-dev")
        marts = os.environ.get("BQ_MARTS_MEDICAID_DATASET", "mobius_medicaid_npi_dev")
        result = estimate_potential_revenue(
            bq,
            req.missing_enrollment,
            flagged=req.flagged,
            project=project,
            marts_dataset=marts,
            member_proxy=max(1, req.member_proxy),
            org_benchmark=req.org_benchmark,
        )
        return result
    except ImportError:
        raise HTTPException(status_code=503, detail="BigQuery client not available")
    except Exception as e:
        logger.exception("Potential revenue failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/opportunity-sizing")
async def api_opportunity_sizing(req: OpportunitySizingRequest) -> dict[str, Any]:
    """
    Step 10: Revenue waterfall & opportunity sizing (A–E).
    A=Guaranteed, B=At-risk, C=Enrollment, D=Taxonomy opt, E=Rate gap.
    """
    if not req.validated and not req.flagged and not req.missing_enrollment:
        return {
            "guaranteed_revenue": 0.0,
            "at_risk_revenue": 0.0,
            "missing_pml_revenue": 0.0,
            "taxonomy_optimization_opportunity": 0.0,
            "org_vs_state_opportunity": 0.0,
            "total_opportunity": 0.0,
            "provider_counts": {"A": 0, "B": 0, "C": 0},
            "methodology": "",
            "npi_detail": [],
        }
    try:
        bq = _get_bq_client()
        project, landing = _get_datasets()
        marts = os.environ.get("BQ_MARTS_MEDICAID_DATASET", "mobius_medicaid_npi_dev")
        result = compute_opportunity_sizing(
            bq,
            req.validated,
            req.flagged,
            req.missing_enrollment,
            project=project,
            landing_dataset=landing,
            marts_dataset=marts,
            member_proxy=max(1, req.member_proxy),
            org_benchmark=req.org_benchmark,
        )
        return result
    except ImportError:
        raise HTTPException(status_code=503, detail="BigQuery client not available")
    except Exception as e:
        logger.exception("Opportunity sizing failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/missing-pml-enrollment")
async def api_missing_pml_enrollment(req: MissingPmlEnrollmentRequest) -> dict[str, Any]:
    """
    Step 7: Find active roster NPIs not in PML. For each: suggest taxonomy + location for enrollment.
    """
    if not req.locations or not req.active_roster:
        return {"missing": [], "summary": {"total": 0}}
    try:
        bq = _get_bq_client()
        project, landing = _get_datasets()
        result = find_missing_pml_enrollment(
            bq,
            req.active_roster,
            req.locations,
            project=project,
            landing_dataset=landing,
            taxonomy_labels=TAXONOMY_CODE_LABELS,
        )
        return result
    except ImportError:
        raise HTTPException(status_code=503, detail="BigQuery client not available")
    except Exception as e:
        logger.exception("Missing PML enrollment failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/pml-validation")
async def api_pml_validation(req: PmlValidationRequest) -> dict[str, Any]:
    """
    Step 6: PML validation. Extracts PML rows for NPIs, validates NPI (NPPES+active), taxonomy (TML+NPPES), ZIP (9-digit, matches location), Medicaid ID.
    Returns validated and flagged rows with recommendations.
    """
    npis = list(req.org_npis or [])
    provider_names: dict[str, str] = {}
    for _, providers in (req.associated_providers or {}).items():
        for p in providers or []:
            n = (p.get("npi") or p.get("servicing_npi") or "").strip()
            if n:
                n = str(n).zfill(10)
                npis.append(n)
                name = (p.get("name") or p.get("provider_name") or "").strip()
                if name and n not in provider_names:
                    provider_names[n] = name
    npis = list(dict.fromkeys(npis))
    if not npis or not req.locations:
        return {
            "pml_rows": [],
            "validated": [],
            "flagged": [],
            "summary": {"total": 0, "valid": 0, "flagged": 0},
        }
    try:
        bq = _get_bq_client()
        project, landing = _get_datasets()
        result = validate_pml_rows(
            bq,
            npis,
            req.locations,
            project=project,
            landing_dataset=landing,
            program_state=req.program_state,
            product=req.product,
            provider_names=provider_names,
        )
        return result
    except ImportError:
        raise HTTPException(status_code=503, detail="BigQuery client not available")
    except Exception as e:
        logger.exception("PML validation failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/historic-billing-patterns")
async def api_historic_billing_patterns(req: HistoricBillingRequest) -> dict[str, Any]:
    """
    Step 5: Historic billing patterns for servicing NPIs.
    Returns breakdown by HCPCS/procedure code (facility vs professional), last 12 months from DOGE.
    """
    if not req.associated_providers:
        return {"summary": {"total_claims": 0, "total_paid": 0.0, "n_codes": 0}, "by_code": [], "entity_breakdown": {}}
    try:
        bq = _get_bq_client()
        project, landing = _get_datasets()
        result = get_historic_billing_patterns(
            bq,
            req.associated_providers,
            project=project,
            landing_dataset=landing,
            period_start=req.period_start,
            period_end=req.period_end,
        )
        return result
    except ImportError as e:
        raise HTTPException(status_code=503, detail="BigQuery client not available") from e
    except Exception as e:
        logger.exception("Historic billing patterns failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/find-services-by-location")
async def api_find_services_by_location(req: FindServicesByLocationRequest) -> dict[str, Any]:
    """
    Step 5: For each location, distinct taxonomies (NPPES all 15 + PML), descriptions, Medicaid approved.
    Output: services_by_location: { location_id -> [ taxonomy_code, taxonomy_description, medicaid_approved, location_address ] }.
    """
    if not req.locations or not req.associated_providers:
        return {"services_by_location": {}, "count": 0}
    try:
        bq = _get_bq_client()
        project, landing = _get_datasets()
        result = find_services_by_location(
            bq,
            req.locations,
            req.associated_providers,
            project=project,
            landing_dataset=landing,
            state_filter=req.state,
            taxonomy_labels_fallback=TAXONOMY_CODE_LABELS,
        )
        total = sum(len(v) for v in result.values())
        return {"services_by_location": result, "locations_count": len(result), "total_services": total}
    except ImportError as e:
        raise HTTPException(status_code=503, detail="BigQuery client not available") from e
    except Exception as e:
        logger.exception("Find services by location failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8010")),
        timeout_keep_alive=120,
    )
