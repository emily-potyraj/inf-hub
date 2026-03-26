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


def parse_ibdb_excel(content: bytes) -> list[dict[str, Any]]:
    """
    Parse an IBDB Excel (.xlsx) export and return a list of curve dicts.

    Axes:
      x = d_tput_genphase_tps_per_user  (interactivity — generation TPS / user)
      y = d_tput_output_tps_per_acc     (throughput — output TPS / accelerator)

    Groups rows by (s_accelerator_name, s_framework_name, s_precision).
    Returns [] on any parse error.
    """
    try:
        import io
        import openpyxl
    except ImportError:
        return []

    try:
        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        wb.close()
    except Exception:
        return []

    if len(rows) < 2:
        return []

    headers = [str(h) if h is not None else "" for h in rows[0]]

    def _get(row: tuple, name: str):
        try:
            return row[headers.index(name)]
        except (ValueError, IndexError):
            return None

    # Group points by (hardware, framework, precision, isl, osl)
    from collections import Counter, OrderedDict
    groups: dict = OrderedDict()

    for row in rows[1:]:
        hardware = _get(row, "s_accelerator_name")
        x = _get(row, "d_tput_genphase_tps_per_user")
        y = _get(row, "d_tput_output_tps_per_acc")

        if hardware is None or x is None or y is None:
            continue

        framework = _get(row, "s_framework_name")
        precision = _get(row, "s_precision")
        isl_val = _get(row, "l_max_input_length")
        osl_val = _get(row, "l_max_output_length")
        isl = int(isl_val) if isl_val is not None else None
        osl = int(osl_val) if osl_val is not None else None
        key = (str(hardware), str(framework) if framework else None, str(precision) if precision else None, isl, osl)

        if key not in groups:
            groups[key] = []

        point: dict[str, Any] = {"x": float(x), "y": float(y)}

        concurrency = _get(row, "l_concurrency")
        if concurrency is not None:
            point["concurrency"] = str(int(concurrency))

        ts = _get(row, "ts_timestamp")
        if ts is not None:
            # ts may be a datetime object or string; take first 10 chars for date
            point["date"] = str(ts)[:10]

        exp_id = _get(row, "s_experiment_id")
        if exp_id is not None:
            point["experiment_id"] = str(exp_id)

        model = _get(row, "s_model_name")
        if model is not None:
            point["model"] = str(model)

        groups[key].append(point)

    # Count hardware occurrences to determine if label suffix is needed
    hw_counts = Counter(key[0] for key in groups)

    result = []
    for (hardware, framework, precision, isl, osl), points in groups.items():
        # Sort by concurrency ascending (numeric sort)
        def _conc_key(p: dict) -> int:
            v = p.get("concurrency", "0")
            return int(v) if str(v).isdigit() else 0

        points_sorted = sorted(points, key=_conc_key)
        label = hardware
        if hw_counts[hardware] > 1 and isl is not None and osl is not None:
            label = f"{hardware} ({isl}/{osl})"
        result.append({
            "label": label,
            "hardware": hardware,
            "framework": framework,
            "precision": precision,
            "isl": isl,
            "osl": osl,
            "points": points_sorted,
        })

    return result
