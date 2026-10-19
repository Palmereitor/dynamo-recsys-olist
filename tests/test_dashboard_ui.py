"""Prueba los controles de Streamlit sin servidor HTTP ni datos crudos."""
from pathlib import Path
from unittest.mock import patch

import pytest

testing = pytest.importorskip("streamlit.testing.v1")
PAGE = Path(__file__).resolve().parents[1] / "app/pages/1_Dashboard.py"


@patch("src.dashboard_data.urlopen", side_effect=OSError("sin red en pruebas"))
def test_model_controls_render_and_keep_intervals_at_k10(_download):
    app = testing.AppTest.from_file(str(PAGE), default_timeout=30).run()
    assert not app.exception
    next(s for s in app.selectbox if s.label == "Top-K evaluado").select(20).run()
    assert not app.exception
    assert any("solo corresponden a HitRate@10" in c.value for c in app.caption)
    next(s for s in app.selectbox if s.label == "Usuarios evaluados").select("warm").run()
    assert not app.exception
    assert any("segmento con historial es pequeño" in i.value for i in app.info)
    next(s for s in app.selectbox if s.label == "Top-K evaluado").select(10).run()
    assert not app.exception
    assert any(s.label == "Diferencia pareada de HitRate@10" for s in app.selectbox)
    next(s for s in app.multiselect if s.label == "Modelos a comparar").set_value([]).run()
    assert not app.exception
    assert any("Selecciona al menos un modelo" in i.value for i in app.info)
