import pytest
from app.devzone_parser import parse_ibdb_export, _parse_hover_text, _extract_framework

# Minimal Plotly HTML that mirrors the IBDB export format.
MINIMAL_HTML = '''<div>
<div id="test-chart" class="plotly-graph-div"></div>
<script type="text/javascript">
Plotly.newPlot(
  "test-chart",
  [
    {
      "legendgroup": "H200",
      "name": "Accelerator: H200",
      "x": [50.0, 100.0, 200.0],
      "y": [30.0, 20.0, 10.0],
      "text": [
        "SGLang-H200<br> Precision: FP8<br> Concurrency: 4<br> Model: deepseek-r1<br> Date: 2026-03-13",
        "SGLang-H200<br> Precision: FP8<br> Concurrency: 8<br> Model: deepseek-r1<br> Date: 2026-03-13",
        "SGLang-H200<br> Precision: FP8<br> Concurrency: 16<br> Model: deepseek-r1<br> Date: 2026-03-13"
      ]
    },
    {
      "legendgroup": "B200",
      "name": "Accelerator: B200",
      "x": [80.0, 160.0, 320.0],
      "y": [50.0, 35.0, 18.0],
      "text": [
        "SGLang-B200<br> Precision: FP8<br> Concurrency: 4<br> Model: deepseek-r1<br> Date: 2026-03-13",
        "SGLang-B200<br> Precision: FP8<br> Concurrency: 8<br> Model: deepseek-r1<br> Date: 2026-03-13",
        "SGLang-B200<br> Precision: FP8<br> Concurrency: 16<br> Model: deepseek-r1<br> Date: 2026-03-13"
      ]
    }
  ],
  {},
  {}
)
</script>
</div>'''


def test_parse_finds_two_series():
    result = parse_ibdb_export(MINIMAL_HTML)
    assert len(result) == 2


def test_parse_extracts_hardware_from_legendgroup():
    result = parse_ibdb_export(MINIMAL_HTML)
    labels = {c["hardware"] for c in result}
    assert labels == {"H200", "B200"}


def test_parse_strips_accelerator_prefix_from_label():
    result = parse_ibdb_export(MINIMAL_HTML)
    labels = {c["label"] for c in result}
    assert labels == {"H200", "B200"}


def test_parse_extracts_xy_points():
    result = parse_ibdb_export(MINIMAL_HTML)
    h200 = next(c for c in result if c["hardware"] == "H200")
    assert len(h200["points"]) == 3
    assert h200["points"][0]["x"] == 50.0
    assert h200["points"][0]["y"] == 30.0


def test_parse_extracts_metadata_from_hover_text():
    result = parse_ibdb_export(MINIMAL_HTML)
    h200 = next(c for c in result if c["hardware"] == "H200")
    assert h200["points"][0]["concurrency"] == "4"
    assert h200["points"][0]["model"] == "deepseek-r1"


def test_parse_extracts_precision():
    result = parse_ibdb_export(MINIMAL_HTML)
    h200 = next(c for c in result if c["hardware"] == "H200")
    assert h200["precision"] == "FP8"


def test_parse_returns_empty_for_non_plotly_html():
    result = parse_ibdb_export("<html><body>no chart here</body></html>")
    assert result == []


def test_parse_returns_empty_for_malformed_json():
    bad_html = "Plotly.newPlot('x', [{broken json"
    result = parse_ibdb_export(bad_html)
    assert result == []


def test_parse_hover_text_extracts_key_value():
    text = "Label<br> Precision: FP8<br> Concurrency: 8<br> Model: deepseek-r1"
    meta = _parse_hover_text(text)
    assert meta["precision"] == "FP8"
    assert meta["concurrency"] == "8"
    assert meta["model"] == "deepseek-r1"


def test_parse_hover_text_ignores_na_values():
    text = "Label<br> KV Precision: N/A<br> Precision: FP8"
    meta = _parse_hover_text(text)
    assert "kv_precision" not in meta
    assert meta["precision"] == "FP8"


def test_extract_framework_strips_hardware_suffix():
    assert _extract_framework("SGLang-Public-H200", "H200") == "SGLang"


def test_extract_framework_returns_none_if_no_match():
    assert _extract_framework("Accelerator: H200", "H200") is None


def test_parse_extracts_framework_from_series_name():
    html_with_framework = MINIMAL_HTML.replace(
        '"name": "Accelerator: H200"',
        '"name": "SGLang-Public-H200"',
    )
    result = parse_ibdb_export(html_with_framework)
    h200 = next(c for c in result if c["hardware"] == "H200")
    assert h200["framework"] == "SGLang"


import io
import openpyxl


def _make_excel_bytes(rows: list[dict]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    headers = [
        "s_accelerator_name", "s_framework_name", "s_precision", "s_model_name",
        "l_concurrency", "d_tput_genphase_tps_per_user", "d_tput_output_tps_per_acc",
        "ts_timestamp", "s_experiment_id",
        "l_max_input_length", "l_max_output_length",
    ]
    ws.append(headers)
    for row in rows:
        ws.append([row.get(h) for h in headers])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


EXCEL_ROWS = [
    {"s_accelerator_name": "H200", "s_framework_name": "SGLang", "s_precision": "FP8",
     "s_model_name": "deepseek-r1", "l_concurrency": 4,
     "d_tput_genphase_tps_per_user": 50.0, "d_tput_output_tps_per_acc": 30.0,
     "ts_timestamp": "2026-03-13 00:00:00", "s_experiment_id": "EXP-001",
     "l_max_input_length": 1000, "l_max_output_length": 2000},
    {"s_accelerator_name": "H200", "s_framework_name": "SGLang", "s_precision": "FP8",
     "s_model_name": "deepseek-r1", "l_concurrency": 8,
     "d_tput_genphase_tps_per_user": 100.0, "d_tput_output_tps_per_acc": 20.0,
     "ts_timestamp": "2026-03-13 00:00:00", "s_experiment_id": "EXP-002",
     "l_max_input_length": 1000, "l_max_output_length": 2000},
    {"s_accelerator_name": "B200", "s_framework_name": "SGLang", "s_precision": "FP8",
     "s_model_name": "deepseek-r1", "l_concurrency": 4,
     "d_tput_genphase_tps_per_user": 80.0, "d_tput_output_tps_per_acc": 50.0,
     "ts_timestamp": "2026-03-13 00:00:00", "s_experiment_id": "EXP-003",
     "l_max_input_length": 1000, "l_max_output_length": 2000},
    {"s_accelerator_name": "B200", "s_framework_name": "SGLang", "s_precision": "FP8",
     "s_model_name": "deepseek-r1", "l_concurrency": 8,
     "d_tput_genphase_tps_per_user": 160.0, "d_tput_output_tps_per_acc": 35.0,
     "ts_timestamp": "2026-03-13 00:00:00", "s_experiment_id": "EXP-004",
     "l_max_input_length": 1000, "l_max_output_length": 2000},
]


def test_parse_excel_finds_two_curves():
    content = _make_excel_bytes(EXCEL_ROWS)
    result = parse_ibdb_export.__module__  # ensure module importable
    from app.devzone_parser import parse_ibdb_excel
    result = parse_ibdb_excel(content)
    assert len(result) == 2


def test_parse_excel_hardware_labels():
    from app.devzone_parser import parse_ibdb_excel
    result = parse_ibdb_excel(_make_excel_bytes(EXCEL_ROWS))
    labels = {c["hardware"] for c in result}
    assert labels == {"H200", "B200"}


def test_parse_excel_xy_points():
    from app.devzone_parser import parse_ibdb_excel
    result = parse_ibdb_excel(_make_excel_bytes(EXCEL_ROWS))
    h200 = next(c for c in result if c["hardware"] == "H200")
    assert len(h200["points"]) == 2
    assert h200["points"][0]["x"] == 50.0
    assert h200["points"][0]["y"] == 30.0


def test_parse_excel_isl_osl_in_curve():
    from app.devzone_parser import parse_ibdb_excel
    result = parse_ibdb_excel(_make_excel_bytes(EXCEL_ROWS))
    h200 = next(c for c in result if c["hardware"] == "H200")
    assert h200["isl"] == 1000
    assert h200["osl"] == 2000


def test_parse_excel_multi_seqlen_unique_labels():
    """When same hardware appears at multiple ISL/OSL, labels get suffixed."""
    from app.devzone_parser import parse_ibdb_excel
    rows = EXCEL_ROWS + [
        {"s_accelerator_name": "H200", "s_framework_name": "SGLang", "s_precision": "FP8",
         "s_model_name": "deepseek-r1", "l_concurrency": 4,
         "d_tput_genphase_tps_per_user": 55.0, "d_tput_output_tps_per_acc": 32.0,
         "ts_timestamp": "2026-03-13 00:00:00", "s_experiment_id": "EXP-005",
         "l_max_input_length": 128000, "l_max_output_length": 8000},
    ]
    result = parse_ibdb_excel(_make_excel_bytes(rows))
    h200_curves = [c for c in result if c["hardware"] == "H200"]
    assert len(h200_curves) == 2
    labels = {c["label"] for c in h200_curves}
    # Both should have isl/osl suffix since there are 2 H200 curves
    assert all("1000" in l or "128000" in l for l in labels)


def test_parse_excel_point_metadata():
    from app.devzone_parser import parse_ibdb_excel
    result = parse_ibdb_excel(_make_excel_bytes(EXCEL_ROWS))
    h200 = next(c for c in result if c["hardware"] == "H200")
    assert h200["points"][0]["concurrency"] == "4"
    assert h200["points"][0]["experiment_id"] == "EXP-001"
    assert h200["points"][0]["model"] == "deepseek-r1"


def test_parse_excel_framework_and_precision():
    from app.devzone_parser import parse_ibdb_excel
    result = parse_ibdb_excel(_make_excel_bytes(EXCEL_ROWS))
    h200 = next(c for c in result if c["hardware"] == "H200")
    assert h200["framework"] == "SGLang"
    assert h200["precision"] == "FP8"


def test_parse_excel_sorted_by_concurrency():
    from app.devzone_parser import parse_ibdb_excel
    # Intentionally reverse concurrency order in input
    rows = list(reversed(EXCEL_ROWS))
    result = parse_ibdb_excel(_make_excel_bytes(rows))
    h200 = next(c for c in result if c["hardware"] == "H200")
    concs = [int(p["concurrency"]) for p in h200["points"]]
    assert concs == sorted(concs)


def test_parse_excel_returns_empty_for_invalid():
    from app.devzone_parser import parse_ibdb_excel
    result = parse_ibdb_excel(b"not an excel file")
    assert result == []
