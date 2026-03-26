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
