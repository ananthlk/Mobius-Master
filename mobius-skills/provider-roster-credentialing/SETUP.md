# Provider Roster Credentialing — Setup

## Python dependencies

```bash
pip install -r requirements.txt
```

## WeasyPrint (PDF generation)

PDF reports require WeasyPrint and its system libraries. Install system deps once on the host:

```bash
./scripts/setup_weasyprint_deps.sh
```

- **Ubuntu/Debian**: Installs `libpango`, `libharfbuzz-subset`, etc. via apt
- **macOS**: Run `brew install pango` then `pip install weasyprint`. If you see "Cannot install under Rosetta 2", use native ARM: `arch -arm64 brew install pango`
- **Alpine/Docker**: Script adds minimal libs; see [WeasyPrint docs](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html) for full Alpine setup

Verify:

```bash
weasyprint --info
```

If PDF generation fails, check logs for `"PDF generation failed; check weasyprint and system deps"`.

## Matplotlib + Seaborn (chart images)

Charts are generated via matplotlib/seaborn. These are in `requirements.txt`. If charts are empty, ensure both are installed in the runtime environment.
