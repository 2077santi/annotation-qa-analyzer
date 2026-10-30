"""Bake the pipeline results into a single static HTML page for GitHub Pages."""

import json
from pathlib import Path

TEMPLATE = Path(__file__).with_name("dashboard_template.html")


def build_dashboard(result: dict, path: Path) -> None:
    data = json.dumps(result, default=float).replace("</", "<\\/")
    html = TEMPLATE.read_text().replace("/*__DATA__*/null", data)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html)
