# Reference Image Validation Rules

Live validation runs on import and collection changes.

---

## Collection warnings

| Rule | Message |
|------|---------|
| No images | No reference images have been imported |
| Missing Front View | Missing required category: Front View |

---

## Per-image warnings

| Rule | Field |
|------|-------|
| Duplicate checksum | `checksum` |
| Very small image (< 400px) | `dimensions` |
| Large file (> 20 MB) | `file_size` |
| Unsupported colour profile | `colour_profile` |
| Missing category tag | `tags` |

---

## Status

| Condition | Status |
|-----------|--------|
| No images | Not started |
| Warnings only | Pending |
| Errors | Failed |
| No issues | Passed |

Validation status is written to each image record and project manifest.
