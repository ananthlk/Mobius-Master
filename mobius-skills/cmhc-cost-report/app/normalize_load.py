"""
Normalize + load: Read CMHC HCRIS zip (from GCS or local), parse RPT/NMRC/Alpha, load to BigQuery landing.
Usage: python -m app.normalize_load [gcs_path_or_local_zip] [vintage]
  If no path given, uses latest object under gs://<bucket>/cmhc-hcris/raw/<vintage>/
  vintage defaults to 2088-17.
"""
import io
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from app.config import GCS_BUCKET, BQ_PROJECT, BQ_LANDING_DATASET, GCS_RAW_PREFIX
from app.parser import parse_hcris_zip


def _get_zip_bytes(path_or_none: str | None, vintage: str) -> tuple[bytes, str]:
    """Return (zip_bytes, form_vintage). Path can be gs://... or local path."""
    if path_or_none and path_or_none.startswith("gs://"):
        from google.cloud import storage
        parts = path_or_none.replace("gs://", "").split("/", 1)
        bucket_name, blob_path = parts[0], parts[1]
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_path)
        return blob.download_as_bytes(), vintage
    if path_or_none and Path(path_or_none).exists():
        return Path(path_or_none).read_bytes(), vintage
    if not path_or_none and GCS_BUCKET:
        from google.cloud import storage
        client = storage.Client()
        bucket = client.bucket(GCS_BUCKET)
        prefix = f"{GCS_RAW_PREFIX}/{vintage}/"
        blobs = list(bucket.list_blobs(prefix=prefix))
        # Prefer .zip
        zips = [b for b in blobs if b.name.endswith(".zip")]
        if not zips:
            raise FileNotFoundError(f"No zip under gs://{GCS_BUCKET}/{prefix}")
        latest = max(zips, key=lambda b: b.updated or b.time_created)
        return latest.download_as_bytes(), vintage
    raise FileNotFoundError("Provide a local path, gs:// path, or set GCS_BUCKET and run extract first.")


def _ensure_dataset_and_tables(client, dataset_id: str):
    """Create dataset and tables if they do not exist (so we can run without bq CLI)."""
    from google.cloud import bigquery

    try:
        client.get_dataset(dataset_id)
    except Exception:
        client.create_dataset(bigquery.Dataset(dataset_id), exists_ok=True)
    full = f"{BQ_PROJECT}.{BQ_LANDING_DATASET}"
    for table_name, schema in [
        ("hcris_rpt", [
            bigquery.SchemaField("report_record_key", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("provider_ccn", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("fiscal_year_start", "DATE", mode="NULLABLE"),
            bigquery.SchemaField("fiscal_year_end", "DATE", mode="NULLABLE"),
            bigquery.SchemaField("report_status", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("form_vintage", "STRING", mode="NULLABLE"),
        ]),
        ("hcris_nmrc", [
            bigquery.SchemaField("report_record_key", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("worksheet", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("line", "INT64", mode="NULLABLE"),
            bigquery.SchemaField("column", "INT64", mode="NULLABLE"),
            bigquery.SchemaField("value", "FLOAT64", mode="NULLABLE"),
        ]),
        ("hcris_alpha", [
            bigquery.SchemaField("report_record_key", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("worksheet", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("line", "INT64", mode="NULLABLE"),
            bigquery.SchemaField("column", "INT64", mode="NULLABLE"),
            bigquery.SchemaField("value", "STRING", mode="NULLABLE"),
        ]),
    ]:
        table_ref = f"{full}.{table_name}"
        try:
            client.get_table(table_ref)
        except Exception:
            client.create_table(bigquery.Table(table_ref, schema=schema), exists_ok=True)


def main() -> int:
    from google.cloud import bigquery

    path_arg = sys.argv[1] if len(sys.argv) > 1 else None
    vintage = (sys.argv[2] if len(sys.argv) > 2 else "2088-17").strip()

    if not BQ_LANDING_DATASET:
        print("Set BQ_LANDING_DATASET in .env", file=sys.stderr)
        return 1

    print("Loading zip...", flush=True)
    try:
        zip_bytes, form_vintage = _get_zip_bytes(path_arg, vintage)
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        return 1

    print("Parsing RPT / NMRC / Alpha...", flush=True)
    rpt_rows, nmrc_rows, alpha_rows = parse_hcris_zip(io.BytesIO(zip_bytes), form_vintage=form_vintage)
    print(f"  RPT: {len(rpt_rows)}, NMRC: {len(nmrc_rows)}, Alpha: {len(alpha_rows)}", flush=True)

    client = bigquery.Client(project=BQ_PROJECT)
    dataset_ref = f"{BQ_PROJECT}.{BQ_LANDING_DATASET}"
    print("Ensuring dataset and tables exist...", flush=True)
    _ensure_dataset_and_tables(client, dataset_ref)
    dataset = dataset_ref

    schema_rpt = [
        bigquery.SchemaField("report_record_key", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("provider_ccn", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("fiscal_year_start", "DATE", mode="NULLABLE"),
        bigquery.SchemaField("fiscal_year_end", "DATE", mode="NULLABLE"),
        bigquery.SchemaField("report_status", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("form_vintage", "STRING", mode="NULLABLE"),
    ]
    schema_nmrc = [
        bigquery.SchemaField("report_record_key", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("worksheet", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("line", "INT64", mode="NULLABLE"),
        bigquery.SchemaField("column", "INT64", mode="NULLABLE"),
        bigquery.SchemaField("value", "FLOAT64", mode="NULLABLE"),
    ]
    schema_alpha = [
        bigquery.SchemaField("report_record_key", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("worksheet", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("line", "INT64", mode="NULLABLE"),
        bigquery.SchemaField("column", "INT64", mode="NULLABLE"),
        bigquery.SchemaField("value", "STRING", mode="NULLABLE"),
    ]

    # Convert date strings to BQ DATE (YYYY-MM-DD is valid)
    def _rpt_for_bq(r: dict) -> dict:
        return {**r}

    if rpt_rows:
        table_id = f"{dataset}.hcris_rpt"
        job_config = bigquery.LoadJobConfig(schema=schema_rpt, write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE)
        job = client.load_table_from_json(rpt_rows, table_id, job_config=job_config)
        job.result()
        print(f"Loaded {len(rpt_rows)} rows into {table_id}", flush=True)
    if nmrc_rows:
        table_id = f"{dataset}.hcris_nmrc"
        job_config = bigquery.LoadJobConfig(schema=schema_nmrc, write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE)
        job = client.load_table_from_json(nmrc_rows, table_id, job_config=job_config)
        job.result()
        print(f"Loaded {len(nmrc_rows)} rows into {table_id}", flush=True)
    if alpha_rows:
        table_id = f"{dataset}.hcris_alpha"
        job_config = bigquery.LoadJobConfig(schema=schema_alpha, write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE)
        job = client.load_table_from_json(alpha_rows, table_id, job_config=job_config)
        job.result()
        print(f"Loaded {len(alpha_rows)} rows into {table_id}", flush=True)

    print("Done.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
