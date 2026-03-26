from __future__ import annotations

import json
import re
import html as html_lib
from typing import Any


CURVE_COLORS = [
    "#76b900", "#00b4d8", "#fbbf24", "#f87171",
    "#a78bfa", "#34d399", "#fb923c", "#e879f9",
]


def parse_ibdb_export(html_content: str) -> list[dict[str, Any]]:
    """
    Parse an IBDB Plotly HTML export and return a list of curve dicts.

    Each dict: {label, hardware, framework, precision, points}
    points: list of {x, y, ...metadata from hover text}

    Returns [] if no Plotly.newPlot call found or JSON is malformed.
    """
    match = re.search(
        r'Plotly\.newPlot\s*\(\s*["\'][^"\']*["\']\s*,\s*(\[)',
        html_content,
    )
    if not match:
        return []

    start = match.start(1)
    try:
        decoder = json.JSONDecoder()
        traces, _ = decoder.raw_decode(html_content, start)
    except (json.JSONDecodeError, ValueError):
        return []

    result = []
    for trace in traces:
        if not isinstance(trace, dict):
            continue

        hardware = trace.get("legendgroup", "")
        name = trace.get("name", "")
        label = name.replace("Accelerator: ", "").strip() if "Accelerator: " in name else (hardware or name)

        x_vals = trace.get("x", [])
        y_vals = trace.get("y", [])
        texts = trace.get("text", [])

        points = []
        for i, (x, y) in enumerate(zip(x_vals, y_vals)):
            meta = _parse_hover_text(texts[i]) if i < len(texts) else {}
            points.append({"x": float(x), "y": float(y), **meta})

        first = points[0] if points else {}
        result.append({
            "label": label,
            "hardware": hardware,
            "framework": _extract_framework(name, hardware),
            "precision": first.get("precision"),
            "points": points,
        })

    return result


def _parse_hover_text(html_text: str) -> dict[str, str]:
    """Extract key-value metadata from IBDB hover HTML text."""
    meta = {}
    parts = re.split(r'<br\s*/?>', html_text, flags=re.IGNORECASE)
    for part in parts:
        clean = re.sub(r'<[^>]+>', '', part).strip()
        clean = html_lib.unescape(clean)
        if ': ' in clean:
            key, _, val = clean.partition(': ')
            key_norm = key.strip().lower().replace(' ', '_').replace('/', '_')
            val = val.strip()
            if key_norm and val and val != 'N/A':
                meta[key_norm] = val
    return meta


def _extract_framework(series_name: str, hardware: str) -> str | None:
    """
    Extract framework from a series name like 'SGLang-Public-H200'.
    Strips the hardware suffix, returns the first dash-separated segment.
    Returns None if pattern doesn't match.
    """
    if not hardware or not series_name:
        return None
    name = series_name.replace("Accelerator: ", "").strip()
    if name.endswith(f"-{hardware}"):
        prefix = name[: -len(hardware) - 1]
        parts = prefix.split("-")
        return parts[0] if parts else None
    return None
