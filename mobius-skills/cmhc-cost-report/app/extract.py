"""
Extract: Download CMHC HCRIS zip from CMS and upload to GCS.
Usage: python -m app.extract [vintage]
  vintage: 2088-17 (default) or 2088-92
"""
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from app.config import GCS_BUCKET, CMS_CMHC17_URL, CMS_CMHC92_URL, GCS_RAW_PREFIX


def main() -> int:
    import httpx
    from google.cloud import storage

    vintage = (sys.argv[1] if len(sys.argv) > 1 else "2088-17").strip()
    if vintage == "2088-17":
        url = CMS_CMHC17_URL
        filename = "CMHC17-ALL-YEARS.zip"
    elif vintage == "2088-92":
        url = CMS_CMHC92_URL
        if not url:
            print("Set CMS_CMHC92_URL in .env for 2088-92 extract.", file=sys.stderr)
            return 1
        filename = "CMHC92-ALL-YEARS.zip"
    else:
        print("Usage: python -m app.extract [2088-17|2088-92]", file=sys.stderr)
        return 1

    if not GCS_BUCKET:
        print("Set GCS_BUCKET in .env", file=sys.stderr)
        return 1

    print(f"Downloading {url} ...", flush=True)
    try:
        with httpx.Client(follow_redirects=True, timeout=300) as client:
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.content
    except Exception as e:
        print(f"Download failed: {e}", file=sys.stderr)
        return 1

    print(f"Uploading to gs://{GCS_BUCKET}/{GCS_RAW_PREFIX}/{vintage}/{filename} ...", flush=True)
    try:
        client = storage.Client()
        bucket = client.bucket(GCS_BUCKET)
        blob = bucket.blob(f"{GCS_RAW_PREFIX}/{vintage}/{filename}")
        blob.upload_from_string(data, content_type="application/zip")
    except Exception as e:
        print(f"Upload failed: {e}", file=sys.stderr)
        return 1

    print("Done.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
