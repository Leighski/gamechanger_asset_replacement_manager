# Inspired Delivery Generator

Desktop app for building **Inspired-format** deliveries from ENGP MP4 inputs, with Iconik metadata resolution and packaged media outputs.

## Install

```bash
pip install -r requirements.txt
```

**CustomTkinter** powers the dark neon dashboard UI. If `pip install customtkinter` fails (unusual Python build, restricted environment), install a normal CPython 3.10+ build with Tk support, then retry.

### Optional

- **`tkinterdnd2`** — drag-and-drop MP4s onto the drop zone (`pip install tkinterdnd2`). Without it, use **Add MP4 Files**.
- **`openpyxl`** — full `.xlsx` report generation where applicable (`pip install openpyxl`).

## Run

```bash
python3 Inspired_Delivery_Generator.py
```

## Notes

- **Backend** (Iconik, FFmpeg, media packaging, XLSX, delivery folders) lives in the same script; the UI layer is CustomTkinter-only for the operator dashboard.
- Settings are stored under macOS Application Support (see in-app paths) or a fallback JSON in your home directory.
- **Team names** in `inspired_metadata.xlsx` are normalized to **3-letter abbreviations** via the shared `team_registry` package (data file: `../kiron_export_pipeline/config/team_registry.json`). See `docs/TEAM_NORMALIZATION_BEFORE_AFTER.md`.
