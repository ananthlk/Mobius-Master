#!/usr/bin/env python3
"""
Helper: ingest a local PDF into mobius-rag, set authority_level, queue chunking, wait for embedding,
then publish to rag_published_embeddings.

This is intended for the Sunshine manual bake-off so retrieval eval can filter on:
  document_authority_level = <authority_level>

Requirements:
- mobius-rag API running
- chunking worker running
- embedding worker running
- RAG has access to GCS + extraction credentials (for /upload)
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx


def _require(s: str | None, name: str) -> str:
    v = (s or "").strip()
    if not v:
        raise ValueError(f"Missing required: {name}")
    return v


def _post_upload(client: httpx.Client, api_base: str, pdf_path: Path, payer: str | None, state: str | None, program: str | None) -> dict[str, Any]:
    url = f"{api_base.rstrip('/')}/upload"
    params = {}
    if payer:
        params["payer"] = payer
    if state:
        params["state"] = state
    if program:
        params["program"] = program
    with open(pdf_path, "rb") as f:
        files = {"file": (pdf_path.name, f, "application/pdf")}
        resp = client.post(url, params=params, files=files, timeout=600.0)
    resp.raise_for_status()
    return resp.json()


def _patch_document(client: httpx.Client, api_base: str, document_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    url = f"{api_base.rstrip('/')}/documents/{document_id}"
    resp = client.patch(url, json=patch, timeout=60.0)
    resp.raise_for_status()
    return resp.json()


def _start_chunking(
    client: httpx.Client,
    api_base: str,
    document_id: str,
    threshold: float | None,
    critique_enabled: bool | None,
    max_retries: int | None,
    extraction_enabled: bool | None,
    generator_id: str | None,
) -> dict[str, Any]:
    url = f"{api_base.rstrip('/')}/documents/{document_id}/chunking/start"
    body: dict[str, Any] = {}
    if threshold is not None:
        body["threshold"] = float(threshold)
    if critique_enabled is not None:
        body["critique_enabled"] = bool(critique_enabled)
    if max_retries is not None:
        body["max_retries"] = int(max_retries)
    if extraction_enabled is not None:
        body["extraction_enabled"] = bool(extraction_enabled)
    if generator_id is not None:
        body["generator_id"] = generator_id
    resp = client.post(url, json=body or None, timeout=60.0)
    resp.raise_for_status()
    return resp.json()


def _get_detail(client: httpx.Client, api_base: str, document_id: str) -> dict[str, Any]:
    url = f"{api_base.rstrip('/')}/documents/{document_id}/detail"
    resp = client.get(url, timeout=60.0)
    resp.raise_for_status()
    return resp.json()


def _publish(client: httpx.Client, api_base: str, document_id: str, published_by: str | None, generator_id: str | None) -> dict[str, Any]:
    url = f"{api_base.rstrip('/')}/documents/{document_id}/publish"
    body: dict[str, Any] = {}
    if published_by:
        body["published_by"] = published_by
    if generator_id:
        body["generator_id"] = generator_id
    resp = client.post(url, json=body or None, timeout=120.0)
    resp.raise_for_status()
    return resp.json()


def wait_for_processing(
    client: httpx.Client,
    api_base: str,
    document_id: str,
    poll_interval_sec: float,
    max_wait_sec: float,
) -> dict[str, Any]:
    start = time.monotonic()
    last = None
    while (time.monotonic() - start) < max_wait_sec:
        detail = _get_detail(client, api_base, document_id)
        last = detail
        chunking_status = (detail.get("chunking_status") or "").strip().lower()
        embedding_status = (detail.get("embedding_status") or "").strip().lower()
        # Accept either "completed" or "idle" for chunking when a doc had no content (rare).
        chunking_done = chunking_status in ("completed", "idle")
        embedding_done = embedding_status == "completed"
        if chunking_done and embedding_done:
            return detail
        time.sleep(poll_interval_sec)
    raise TimeoutError(f"Timed out waiting for chunking/embed to complete. Last detail: {last}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api-base", default=os.getenv("MOBIUS_RAG_API_BASE") or "http://localhost:8001")
    ap.add_argument("--pdf", required=True, help="Path to local PDF (Sunshine provider manual)")
    ap.add_argument("--display-name", default=None, help="Optional display_name override")
    ap.add_argument("--authority-level", required=True, help="Unique tag used for Vertex filtering (document_authority_level)")
    ap.add_argument("--payer", default=os.getenv("RAG_DOC_PAYER") or "Sunshine Health")
    ap.add_argument("--state", default=os.getenv("RAG_DOC_STATE") or None)
    ap.add_argument("--program", default=os.getenv("RAG_DOC_PROGRAM") or None)
    ap.add_argument("--effective-date", default=None)
    ap.add_argument("--termination-date", default=None)
    ap.add_argument("--generator-id", default="A")
    ap.add_argument("--threshold", type=float, default=None, help="Critique retry threshold (0-1); default uses server CRITIQUE_RETRY_THRESHOLD")
    ap.add_argument("--critique-enabled", type=int, default=None, help="1/0 override")
    ap.add_argument("--max-retries", type=int, default=None)
    ap.add_argument("--extraction-enabled", type=int, default=None, help="1/0 override")
    ap.add_argument("--poll-interval-sec", type=float, default=2.0)
    ap.add_argument("--max-wait-sec", type=float, default=3600.0)
    ap.add_argument("--published-by", default=os.getenv("USER") or "retrieval-eval")
    args = ap.parse_args()

    api_base = _require(args.api_base, "--api-base")
    pdf_path = Path(args.pdf).expanduser().resolve()
    if not pdf_path.exists():
        raise FileNotFoundError(str(pdf_path))

    critique_enabled = None if args.critique_enabled is None else bool(int(args.critique_enabled))
    extraction_enabled = None if args.extraction_enabled is None else bool(int(args.extraction_enabled))

    with httpx.Client() as client:
        print(f"Uploading PDF to mobius-rag: {pdf_path.name}")
        upload = _post_upload(client, api_base, pdf_path, payer=args.payer, state=args.state, program=args.program)
        document_id = upload.get("document_id")
        if not document_id:
            raise RuntimeError(f"Upload response missing document_id: {upload}")
        print(f"Uploaded. document_id={document_id} status={upload.get('status')}")

        patch: dict[str, Any] = {"authority_level": args.authority_level}
        if args.display_name:
            patch["display_name"] = args.display_name
        if args.effective_date:
            patch["effective_date"] = args.effective_date
        if args.termination_date:
            patch["termination_date"] = args.termination_date
        if args.payer:
            patch["payer"] = args.payer
        if args.state:
            patch["state"] = args.state
        if args.program:
            patch["program"] = args.program

        print(f"Patching document metadata (authority_level={args.authority_level})")
        _patch_document(client, api_base, document_id, patch)

        print("Queueing chunking job")
        start = _start_chunking(
            client,
            api_base,
            document_id,
            threshold=args.threshold,
            critique_enabled=critique_enabled,
            max_retries=args.max_retries,
            extraction_enabled=extraction_enabled,
            generator_id=args.generator_id,
        )
        print(f"Chunking queued: {start}")

        print("Waiting for chunking + embedding to complete...")
        detail = wait_for_processing(
            client,
            api_base,
            document_id,
            poll_interval_sec=float(args.poll_interval_sec),
            max_wait_sec=float(args.max_wait_sec),
        )
        print(f"Done. chunking_status={detail.get('chunking_status')} embedding_status={detail.get('embedding_status')}")

        print("Publishing document to rag_published_embeddings")
        pub = _publish(client, api_base, document_id, published_by=args.published_by, generator_id=args.generator_id)
        print(f"Publish result: {pub}")

        print("\nNext step: run mobius-dbt pipeline to sync into dev Vertex, then run retrieval_eval.py.")
        print(f"document_id={document_id}")
        return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
