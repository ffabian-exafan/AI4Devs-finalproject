"""La extracción de presupuesto usa la API de Claude cuando hay clave."""

import json
from decimal import Decimal
from unittest.mock import patch

from app.config import get_settings
from app.services.extraccion import extraer_presupuesto
from app.services.ocr import _ocr_llm_vision


def _respuesta_claude(texto: str) -> object:
    cuerpo = {
        "content": [
            {"type": "thinking", "thinking": ""},
            {"type": "text", "text": texto},
        ]
    }
    raw = json.dumps(cuerpo).encode("utf-8")

    class _Resp:
        def read(self):
            return raw

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    return _Resp()


def test_extraer_presupuesto_llama_a_claude(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-ant-prueba")
    monkeypatch.delenv("LLM_API_BASE", raising=False)
    monkeypatch.delenv("LLM_PROVEEDOR", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    get_settings.cache_clear()

    json_modelo = json.dumps(
        {
            "nombre_proyecto": "Nave de prueba",
            "tipo_proyecto": "llave_en_mano",
            "naves": [
                {
                    "codigo": "N1",
                    "descripcion": "Nave",
                    "apartados": [
                        {
                            "codigo": "1",
                            "descripcion": "Cubierta",
                            "importe": 80000,
                            "tiene_anotacion_manual": False,
                        }
                    ],
                }
            ],
            "total_impreso": 80000,
        }
    )

    with patch("app.services.llm.request.urlopen", return_value=_respuesta_claude(json_modelo)) as mock:
        resultado = extraer_presupuesto("| Cubierta | 80000 |\n")

    assert resultado.nombre_proyecto == "Nave de prueba"
    assert resultado.naves[0].apartados[0].importe == 80000
    assert resultado.sumas_cuadran is True
    peticion = mock.call_args.args[0]
    assert peticion.full_url == "https://api.anthropic.com/v1/messages"
    assert peticion.get_header("X-api-key") == "sk-ant-prueba"
    cuerpo = json.loads(peticion.data.decode("utf-8"))
    assert cuerpo["model"] == "claude-haiku-4-5"
    assert "thinking" not in cuerpo
    assert "temperature" not in cuerpo
    get_settings.cache_clear()


def test_ocr_vision_claude_lee_bloque_de_texto(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-ant-prueba")
    monkeypatch.delenv("LLM_API_BASE", raising=False)
    get_settings.cache_clear()

    with patch(
        "app.services.llm.request.urlopen",
        return_value=_respuesta_claude("Apartado 1 Cubierta"),
    ) as mock:
        r = _ocr_llm_vision(
            b"png",
            mime="image/png",
            api_key="sk-ant-prueba",
            api_base=None,
            model="claude-sonnet-5",
            anthropic=True,
        )

    assert r.motor == "claude_vision"
    assert r.texto == "Apartado 1 Cubierta"
    cuerpo = json.loads(mock.call_args.args[0].data.decode("utf-8"))
    bloque = cuerpo["messages"][0]["content"][0]
    assert bloque["type"] == "image"
    assert bloque["source"]["media_type"] == "image/png"
    get_settings.cache_clear()


def test_apartado_sin_importe_no_rompe_la_extraccion(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-ant-prueba")
    monkeypatch.delenv("LLM_API_BASE", raising=False)
    monkeypatch.delenv("LLM_PROVEEDOR", raising=False)
    get_settings.cache_clear()

    json_modelo = json.dumps(
        {
            "nombre_proyecto": "Nave con filas vacías",
            "naves": [
                {
                    "codigo": "N1",
                    "descripcion": "Nave",
                    "apartados": [
                        {"codigo": "1", "descripcion": "Cubierta", "importe": 80000},
                        {
                            "codigo": "2",
                            "descripcion": "Capítulo sin cifra",
                            "importe": None,
                        },
                    ],
                }
            ],
            "total_impreso": 80000,
        }
    )

    with patch("app.services.llm.request.urlopen", return_value=_respuesta_claude(json_modelo)):
        resultado = extraer_presupuesto("texto de presupuesto sin fixture")

    sin_cifra = resultado.naves[0].apartados[1]
    assert sin_cifra.importe is None
    assert sin_cifra.excluido_de_suma is True
    assert resultado.requiere_revision is True
    assert resultado.sumas_cuadran is False
    get_settings.cache_clear()


def test_subapartados_cuelgan_del_apartado_con_importe(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-ant-prueba")
    monkeypatch.delenv("LLM_API_BASE", raising=False)
    monkeypatch.delenv("LLM_PROVEEDOR", raising=False)
    get_settings.cache_clear()

    json_modelo = json.dumps(
        {
            "nombre_proyecto": "Nave con subapartados",
            "naves": [
                {
                    "codigo": "N1",
                    "descripcion": "Nave",
                    "apartados": [
                        {"codigo": "1.1", "descripcion": "Cubierta", "importe": 80000},
                        {"codigo": "1.1.1", "descripcion": "Cubierta de nave", "importe": None},
                        {"codigo": "1.1.2", "descripcion": "Cubierta de almacén", "importe": None},
                        {"codigo": "6.1.1", "descripcion": "Estructura", "importe": 180000},
                    ],
                }
            ],
            "total_impreso": 260000,
        }
    )

    with patch("app.services.llm.request.urlopen", return_value=_respuesta_claude(json_modelo)):
        resultado = extraer_presupuesto("texto de presupuesto sin fixture")

    codigos = [ap.codigo for ap in resultado.naves[0].apartados]
    assert codigos == ["1.1", "6.1.1"]
    cubierta = resultado.naves[0].apartados[0]
    assert [h.codigo for h in cubierta.subapartados] == ["1.1.1", "1.1.2"]
    assert resultado.sumas_cuadran is True
    get_settings.cache_clear()


def test_crea_el_apartado_padre_si_solo_vinieron_los_subapartados(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-ant-prueba")
    monkeypatch.delenv("LLM_API_BASE", raising=False)
    monkeypatch.delenv("LLM_PROVEEDOR", raising=False)
    get_settings.cache_clear()

    json_modelo = json.dumps(
        {
            "nombre_proyecto": "Cubierta partida en subapartados",
            "naves": [
                {
                    "codigo": "N1",
                    "descripcion": "Nave",
                    "apartados": [
                        {
                            "codigo": "1.1.1",
                            "descripcion": "CUBIERTA DE NAVE - placas",
                            "importe": 80000,
                        },
                        {
                            "codigo": "1.1.2",
                            "descripcion": "CUBIERTA DE ALMACEN - placas",
                            "importe": None,
                        },
                        {"codigo": "6.1.1", "descripcion": "Estructura nave", "importe": 100},
                        {"codigo": "6.1.2", "descripcion": "Voladizo", "importe": 200},
                        {"codigo": "6.1.3", "descripcion": "Estructura almacén", "importe": 300},
                    ],
                }
            ],
            "total_impreso": 80600,
        }
    )

    with patch("app.services.llm.request.urlopen", return_value=_respuesta_claude(json_modelo)):
        resultado = extraer_presupuesto("texto de presupuesto sin fixture")

    codigos = [ap.codigo for ap in resultado.naves[0].apartados]
    assert "1.1" in codigos
    assert "6.1" not in codigos
    assert {"6.1.1", "6.1.2", "6.1.3"} <= set(codigos)
    cubierta = next(ap for ap in resultado.naves[0].apartados if ap.codigo == "1.1")
    assert cubierta.importe == Decimal("80000")
    assert [h.codigo for h in cubierta.subapartados] == ["1.1.1", "1.1.2"]
    assert all(h.importe is None for h in cubierta.subapartados)
    assert resultado.sumas_cuadran is True
    get_settings.cache_clear()


def test_los_descuentos_finales_se_restan_del_total(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-ant-prueba")
    monkeypatch.delenv("LLM_API_BASE", raising=False)
    monkeypatch.delenv("LLM_PROVEEDOR", raising=False)
    get_settings.cache_clear()
    json_modelo = json.dumps(
        {
            "nombre_proyecto": "Obra con descuento final",
            "naves": [
                {
                    "codigo": "N1",
                    "descripcion": "Nave",
                    "apartados": [
                        {"codigo": "1.1", "descripcion": "Cubierta", "importe": 1000},
                        {
                            "codigo": "99",
                            "descripcion": "Descuento especial",
                            "importe": 100,
                        },
                    ],
                }
            ],
            "descuentos": [
                {
                    "descripcion": "Descuento adicional manuscrito",
                    "importe": 50,
                    "es_manuscrito": True,
                }
            ],
            "total_impreso": 900,
            "total_manuscrito": 850,
        }
    )
    with patch("app.services.llm.request.urlopen", return_value=_respuesta_claude(json_modelo)):
        resultado = extraer_presupuesto("texto de presupuesto sin fixture")

    assert [ap.codigo for ap in resultado.naves[0].apartados] == ["1.1"]
    assert len(resultado.descuentos) == 2
    assert sum(d.importe for d in resultado.descuentos) == 150
    assert any(d.es_manuscrito for d in resultado.descuentos)
    assert resultado.sumas_cuadran is True
    assert resultado.requiere_revision is True
    get_settings.cache_clear()


def test_no_agrupa_apartados_de_un_solo_nivel(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-ant-prueba")
    monkeypatch.delenv("LLM_API_BASE", raising=False)
    monkeypatch.delenv("LLM_PROVEEDOR", raising=False)
    get_settings.cache_clear()
    json_modelo = json.dumps(
        {
            "nombre_proyecto": "Apartados sueltos",
            "naves": [
                {
                    "codigo": "N1",
                    "descripcion": "Nave",
                    "apartados": [
                        {"codigo": "2.2", "descripcion": "Suelos", "importe": None},
                        {"codigo": "2.3", "descripcion": "Corrales", "importe": None},
                    ],
                }
            ],
        }
    )
    with patch("app.services.llm.request.urlopen", return_value=_respuesta_claude(json_modelo)):
        resultado = extraer_presupuesto("texto de presupuesto sin fixture")
    assert [ap.codigo for ap in resultado.naves[0].apartados] == ["2.2", "2.3"]
    get_settings.cache_clear()


def test_endpoint_compatible_sigue_en_chat_completions(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-otro")
    monkeypatch.setenv("LLM_API_BASE", "https://ejemplo.test/v1")
    monkeypatch.setenv("LLM_PROVEEDOR", "openai")
    get_settings.cache_clear()

    json_modelo = json.dumps(
        {
            "nombre_proyecto": "Obra compatible",
            "naves": [
                {
                    "codigo": "N1",
                    "descripcion": "Nave",
                    "apartados": [
                        {"codigo": "1", "descripcion": "Suelos", "importe": 1000},
                    ],
                }
            ],
            "total_impreso": 1000,
        }
    )
    cuerpo_openai = json.dumps(
        {"choices": [{"message": {"content": json_modelo}}]}
    ).encode("utf-8")

    class _Resp:
        def read(self):
            return cuerpo_openai

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    with patch("app.services.llm.request.urlopen", return_value=_Resp()) as mock:
        resultado = extraer_presupuesto("texto suelto sin tabla")

    assert resultado.nombre_proyecto == "Obra compatible"
    assert mock.call_args.args[0].full_url == "https://ejemplo.test/v1/chat/completions"
    get_settings.cache_clear()


def test_pdf_sonnet_transcribe_y_haiku_extrae(monkeypatch):
    import pymupdf

    from app.services.ingesta import leer_presupuesto

    monkeypatch.setenv("LLM_API_KEY", "sk-ant-prueba")
    monkeypatch.delenv("LLM_API_BASE", raising=False)
    monkeypatch.delenv("LLM_PROVEEDOR", raising=False)
    monkeypatch.delenv("LLM_MODELO_TRANSCRIPCION", raising=False)
    monkeypatch.delenv("LLM_MODELO_EXTRACCION", raising=False)
    get_settings.cache_clear()

    doc = pymupdf.open()
    doc.new_page()
    pdf = doc.tobytes()
    doc.close()

    json_modelo = json.dumps(
        {
            "nombre_proyecto": "Nave transcrita",
            "naves": [
                {
                    "codigo": "N1",
                    "descripcion": "Nave",
                    "apartados": [
                        {"codigo": "1", "descripcion": "Cubierta", "importe": 80000},
                    ],
                }
            ],
            "total_impreso": 80000,
        }
    )
    respuestas = [
        _respuesta_claude("| Cubierta | 80000 |"),
        _respuesta_claude(json_modelo),
    ]

    def _urlopen(req, timeout=180):
        return respuestas.pop(0)

    with patch("app.services.llm.request.urlopen", side_effect=_urlopen) as mock:
        leido = leer_presupuesto(pdf, "presupuesto.pdf")
        resultado = extraer_presupuesto(leido.texto)

    assert "| Cubierta | 80000 |" in leido.texto
    assert resultado.nombre_proyecto == "Nave transcrita"
    assert mock.call_count == 2
    primera = json.loads(mock.call_args_list[0].args[0].data.decode("utf-8"))
    segunda = json.loads(mock.call_args_list[1].args[0].data.decode("utf-8"))
    assert primera["model"] == "claude-sonnet-5"
    assert primera["thinking"] == {"type": "disabled"}
    assert primera["messages"][0]["content"][0]["type"] == "document"
    assert segunda["model"] == "claude-haiku-4-5"
    assert "thinking" not in segunda
    assert isinstance(segunda["messages"][0]["content"], str)
    assert "Cubierta" in segunda["messages"][0]["content"]
    get_settings.cache_clear()
