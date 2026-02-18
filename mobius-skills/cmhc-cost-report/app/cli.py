"""
CLI to run CMHC cost report skill queries.
Usage:
  python -m app.cli list_cmhcs [--state FL] [--fy-start YYYY-MM-DD] [--fy-end YYYY-MM-DD]
  python -m app.cli get_report --ccn CCN [--fy YYYY-MM-DD]
  python -m app.cli get_worksheet --key REPORT_RECORD_KEY --worksheet WKSHT
  python -m app.cli get_cell --key KEY --worksheet W --line L --column C
  python -m app.cli compare_to_peers --ccn CCN --fy YYYY-MM-DD --state FL [--worksheet W --line L --column C]
"""
import argparse
import json
import sys
from pathlib import Path

# Load .env and ensure app is on path
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

try:
    from dotenv import load_dotenv
    load_dotenv(_root / ".env")
except ImportError:
    pass

from app.skills import (
    get_report,
    list_cmhcs,
    get_worksheet,
    get_cell,
    compare_to_peers,
    get_full_report_by_name,
)


def _json_out(obj):
    print(json.dumps(obj, indent=2, default=str))


def cmd_list_cmhcs(args):
    out = list_cmhcs(
        state=args.state or None,
        fiscal_year_end_start=args.fy_start or None,
        fiscal_year_end_end=args.fy_end or None,
    )
    _json_out(out)


def cmd_get_report(args):
    out = get_report(
        provider_ccn=args.ccn or None,
        fiscal_year_end=args.fy or None,
    )
    _json_out(out)


def cmd_get_worksheet(args):
    out = get_worksheet(
        report_record_key=args.key,
        worksheet_code=args.worksheet,
        include_alpha=not args.no_alpha,
    )
    _json_out(out)


def cmd_get_cell(args):
    out = get_cell(
        report_record_key=args.key,
        worksheet=args.worksheet,
        line=int(args.line),
        column=int(args.column),
    )
    _json_out(out)


def cmd_compare_to_peers(args):
    out = compare_to_peers(
        provider_ccn=args.ccn,
        fiscal_year_end=args.fy,
        state=args.state,
        worksheet=args.worksheet or None,
        line=int(args.line) if args.line is not None else None,
        column=int(args.column) if args.column is not None else None,
    )
    _json_out(out)


def cmd_full_report_by_name(args):
    out = get_full_report_by_name(
        name_substring=args.name,
        state=args.state or None,
        fiscal_year_end=args.fy or None,
    )
    _json_out(out)


def main():
    parser = argparse.ArgumentParser(description="CMHC cost report skill queries")
    sub = parser.add_subparsers(dest="command", required=True)

    # list_cmhcs
    p_list = sub.add_parser("list_cmhcs", help="List CMHCs with cost reports")
    p_list.add_argument("--state", default=None, help="State (e.g. FL)")
    p_list.add_argument("--fy-start", dest="fy_start", default=None, help="Fiscal year end start (YYYY-MM-DD)")
    p_list.add_argument("--fy-end", dest="fy_end", default=None, help="Fiscal year end end (YYYY-MM-DD)")
    p_list.set_defaults(run=cmd_list_cmhcs)

    # get_report
    p_report = sub.add_parser("get_report", help="Get cost report for one CMHC")
    p_report.add_argument("--ccn", required=True, help="Provider CCN")
    p_report.add_argument("--fy", default=None, help="Fiscal year end (YYYY-MM-DD)")
    p_report.set_defaults(run=cmd_get_report)

    # get_worksheet
    p_ws = sub.add_parser("get_worksheet", help="Get worksheet as grid")
    p_ws.add_argument("--key", required=True, help="Report record key")
    p_ws.add_argument("--worksheet", required=True, help="Worksheet code (e.g. A)")
    p_ws.add_argument("--no-alpha", action="store_true", help="Exclude alpha cells")
    p_ws.set_defaults(run=cmd_get_worksheet)

    # get_cell
    p_cell = sub.add_parser("get_cell", help="Get one cell value")
    p_cell.add_argument("--key", required=True, help="Report record key")
    p_cell.add_argument("--worksheet", required=True, help="Worksheet code")
    p_cell.add_argument("--line", required=True, help="Line number")
    p_cell.add_argument("--column", required=True, help="Column number")
    p_cell.set_defaults(run=cmd_get_cell)

    # full_report_by_name
    p_full = sub.add_parser("full_report_by_name", help="Load full cost report by provider name (searches Alpha)")
    p_full.add_argument("--name", required=True, help="Provider name or substring (e.g. Aspire Health)")
    p_full.add_argument("--state", default=None, help="State filter (e.g. FL)")
    p_full.add_argument("--fy", default=None, help="Fiscal year end (YYYY-MM-DD); if not set, uses most recent")
    p_full.set_defaults(run=cmd_full_report_by_name)

    # compare_to_peers
    p_compare = sub.add_parser("compare_to_peers", help="Compare CMHC to state peers")
    p_compare.add_argument("--ccn", required=True, help="Provider CCN")
    p_compare.add_argument("--fy", required=True, help="Fiscal year end (YYYY-MM-DD)")
    p_compare.add_argument("--state", required=True, help="State (e.g. FL)")
    p_compare.add_argument("--worksheet", default=None, help="Worksheet for metric")
    p_compare.add_argument("--line", default=None, help="Line for metric")
    p_compare.add_argument("--column", default=None, help="Column for metric")
    p_compare.set_defaults(run=cmd_compare_to_peers)

    args = parser.parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
