#!/usr/bin/env python3
"""Template Engine performance summary for GJS-010 deliverables."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from services.template_manager_service import TemplateManagerService


def main() -> None:
    started = time.perf_counter()
    service = TemplateManagerService()
    load_ms = service.manager.last_load_ms
    published = service.manager.publish_mappings("TEMPLATE_BROADCAST_0001")
    publish_ms = (time.perf_counter() - started) * 1000.0 - load_ms
    validation = service.manager.validation("TEMPLATE_BROADCAST_0001")
    out = {
        "template_load_ms": load_ms,
        "publish_mappings_ms": round(publish_ms, 2),
        "template_count": len(service.manager.list_templates()),
        "mapping_count": len(published.mappings) if published else 0,
        "anchor_count": len(published.anchors) if published else 0,
        "validation_valid": validation.valid if validation else False,
        "issue_count": len(validation.issues) if validation else 0,
    }
    target = ROOT / "docs" / "examples" / "GJS010_PERFORMANCE.json"
    target.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
