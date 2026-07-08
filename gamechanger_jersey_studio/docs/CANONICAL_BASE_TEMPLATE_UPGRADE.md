# Canonical Base Template Upgrade — `base_template.psd`

**Milestone:** Production Template Upgrade — Canonical Base Template  
**Date:** 2026-07-03  
**Canonical source:** `/Volumes/04_GRAPHICS/03_JERSEYS/02_ENGLISH_FOOTBALL_JERSEYS/base_template.psd`  
**Template:** `GARMENT_ENGLISH_FOOTBALL_BASE_0001`  
**Tools:** `scripts/upgrade_base_template_assets.py`, `scripts/compare_base_template_upgrade.py`, `scripts/zoom_base_template_upgrade.py`  
**Evidence:** `output/renders/milestones/milestone_base_template/`

---

## Objective

Adopt `base_template.psd` as the single authoritative production master and regenerate the offline Template Definition assets from it at the highest practical fidelity — **without redesigning the renderer** and **without opening any PSD at runtime**. The renderer continues to consume only extracted PNG assets and the Template Definition.

---

## What the canonical master is

`base_template.psd` is a **full production master**, not the legacy stripped template:

| Property | Legacy `base.psd` | Canonical `base_template.psd` |
|----------|-------------------|-------------------------------|
| File size | 17.3 MB | 1.26 GB |
| Canvas | 1200 × 1200 | **8190 × 8190** |
| Layers | 63 | ~200 |
| Modules | Shirt base, Short Sleeves, V Neck Collar 1 | Same 3 **active** + BG, Embossed Logos, Long Sleeves, V-neck Collar 2, Round Collar (Big), Polo Collar, Round Collar |
| Dynamic lighting SO | Absent | Present per module (Screen @ ~64%) |
| Collar inline `Shadow` | Absent | Present (Linear Burn, inside Editable parts) |

The three runtime-active modules (`Shirt base`, `Short Sleeves`, `V Neck Collar 1`) are visible in the master; variant collars, long sleeves, background and embossed-logo groups are toggled off — matching today's render configuration exactly.

---

## Approach (why it is safe)

The current template is a strict **subset** of the master's three active modules — every layer path the renderer uses today exists in the master. The upgrade therefore preserves structure and only lifts asset quality:

1. **Structural parity** — same modules, panels, effect layers, stitches, dynamic-lighting layers and SO anchors. The Template Definition's logical coordinates (1200-space bounds) are **unchanged**, so runtime geometry and the `scale = render_width / canvas.width` maths are byte-for-byte identical.
2. **Resolution decoupled from the logical canvas** — assets are re-exported from the 8190² master at production resolution (capped to a memory-safe long edge). The logical canvas stays 1200² purely as a coordinate system; the loader downsamples assets to render size exactly as before. This satisfies "do not constrain extraction to the legacy 1200×1200 canvas" while keeping the runtime untouched.
3. **Precise masks** — panel masks are now exported from the layer's **true alpha channel** instead of the colour-luminance of the shape fill. This flows through the existing `AssetLoader` (`convert("L")`) unchanged, but replaces a fragile, fill-colour-dependent mask with accurate coverage.
4. **No renderer changes** — no pipeline, service, or parameter was modified. The only change is the regenerated PNG assets plus provenance metadata in the definition's `extraction` block.

### Resolution ceiling

Assets are capped at a **2048 px long edge** (configurable via `--max-edge`, `0` = full 8190² resolution). Rationale:

- The highest render tier is High (600 × 750); 2048 px gives >3× headroom for crisp downsampling and future high-resolution output tiers.
- Keeps the runtime asset cache bounded while still delivering a large fidelity increase over the legacy ~800 px-and-smaller assets.

---

## Results

### Resolution increase

| Metric | Value |
|--------|-------|
| Assets regenerated | **53 / 53** (0 missing) |
| Higher resolution than legacy | 50 |
| Median pixel-count increase | **7.9×** |
| Panel masks | 13 (e.g. Shirt `559×785 → 1455×2048`) |
| Shadow layers | 19 (e.g. Base Shadows `558×808 → 1417×2048`) |
| Highlight layers | 16 |
| Dynamic lighting | 3 (normalized to the 2048 ceiling for consistency/memory) |
| On-disk asset size | 2.84 MB → 21.8 MB |

Full per-asset table: `output/renders/milestones/milestone_base_template/extraction_report.json`.

### Alpha / mask precision

Panel masks changed from **colour-luminance of the shape** to **true alpha coverage**:

- Legacy shirt mask loaded at max L ≈ 179, mean ≈ 9.6 (faint, banded — see `asset_zoom_masks_shirt_base_editable_parts_shirt.png`, left).
- Regenerated mask is clean white coverage at 1455 × 2048 (right), giving accurate, soft-edged panel fills.

### Visual quality (the real improvement)

At normal viewing size the collar and seams are visibly cleaner:

- `render_zoom_collar.png` — legacy collar is jagged/aliased with banding; the master-sourced collar is smooth with a properly defined band.
- `render_zoom_chest.png` — legacy side seam shows a stair-step black artifact; the master-sourced seam is smooth.

### Production Fidelity (before → after, identical specs, Standard tier)

| Reference | Before | After | Δ |
|-----------|--------|-------|---|
| base.psd | 62.75 | 62.47 | −0.28 |
| Coventry.psd | 73.16 | 73.33 | +0.17 |

**The aggregate score is intentionally flat.** The fidelity scorer aligns both images to ~900 px and the renderer previews at 400–500 px — far below both the legacy and new asset resolutions — so downsampled detail is comparable and the numeric score does not capture the edge-quality improvement. This is consistent with the milestone's stated goal: *"The objective is not to increase the Production Fidelity Score… [but] to reduce the remaining visual differences by reproducing the production Photoshop workflow more accurately."* The visible improvement (collar/seam smoothness, mask precision) and the high-resolution headroom are the deliverables here; the number confirms **no regression**.

---

## Runtime behaviour (unchanged)

- `test_no_psd_access_at_runtime` passes — no PSD is opened during rendering.
- Logical canvas remains 1200²; bounds unchanged; `scale` maths identical.
- Full renderer + template + validation suites: **20 passed**.
- Output is still a transparent RGBA garment (no baked background).

---

## Newly available in the master (not yet wired — future milestones)

The canonical master exposes production layers the renderer does not yet consume. These are **candidates for later milestones**, deliberately *not* activated in this resolution-only upgrade:

| Layer / group | Milestone relevance |
|---------------|---------------------|
| `V Neck Collar 1/Editable parts/Shadow` (Linear Burn) | Collar Rendering — inline collar shading |
| `Shirt base/Editable parts/Padding` | Collar/neck depth |
| Per-module `Dynamic lighting` (now sourced from the master) | Already wired (Milestone 1); now higher quality |
| `Embossed Logos Layer` (Depth SO + clipped S/H/R) | Embossed logo treatment |
| `Add Main Design Here`, `Shoulders Stripes`, `Bournemouth black lines` | Club design content pipeline |
| Variant collars (V-neck 2, Round, Polo) & Long Sleeves | Construction variants |

---

## Deliverables

| Deliverable | Location |
|-------------|----------|
| Regenerated Template Definition (provenance updated) | `config/garment_templates/definitions/GARMENT_ENGLISH_FOOTBALL_BASE_0001.json` |
| Regenerated production-resolution assets | `assets/garment_templates/GARMENT_ENGLISH_FOOTBALL_BASE_0001/` |
| Extraction quality report (per-asset old→new) | `output/renders/milestones/milestone_base_template/extraction_report.json` |
| Before/after fidelity + specs summary | `output/renders/milestones/milestone_base_template/before_after_summary.json` |
| Reference / before / after strips | `*_reference_before_after.png` |
| Render zoom crops (collar, chest) | `render_zoom_*.png` |
| Asset-level edge/alpha comparisons | `asset_zoom_*.png` |
| Legacy asset + definition backup | `output/renders/milestones/milestone_base_template/backup_legacy/` |

### Reproduce

```bash
# Regenerate assets from the canonical master (offline)
.venv/bin/python scripts/upgrade_base_template_assets.py \
    --report output/renders/milestones/milestone_base_template/extraction_report.json

# Before/after fidelity + comparison strips
.venv/bin/python scripts/compare_base_template_upgrade.py

# Zoomed visual evidence
.venv/bin/python scripts/zoom_base_template_upgrade.py

# Full library fidelity regression (long-running)
.venv/bin/python scripts/run_production_fidelity_regression.py
```

To extract at full 8190² resolution (no cap): add `--max-edge 0` (increases memory use substantially).

---

## Conclusion

`base_template.psd` is now the canonical source for `GARMENT_ENGLISH_FOOTBALL_BASE_0001`. Every reusable asset has been regenerated from it at production resolution (median 7.9× more pixels), panel masks now use true alpha coverage, and the runtime renderer is unchanged and still PSD-free. Perceived fidelity is unchanged at preview resolution (no regression) while collar/seam edge quality and mask precision are visibly improved — and the renderer now has the high-resolution source headroom required for the remaining refinement milestones.
