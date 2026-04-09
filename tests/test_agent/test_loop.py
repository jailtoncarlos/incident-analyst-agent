"""Testes de regressão para o loop interativo.

Cobre: _detect_action, _normalize_label, extract_tipo com formatos variados,
_request_key, detecção de repetição.
"""

from iac.agent.loop import _detect_action, _request_key
from iac.agent.prompts.utils import _normalize_label, extract_tipo_from_analysis


# ---------------------------------------------------------------------------
# _detect_action
# ---------------------------------------------------------------------------


def test_detect_investigar():
    assert _detect_action('AÇÃO: INVESTIGAR\nINVESTIGAR: app.models.M') == 'INVESTIGAR'


def test_detect_classificar():
    assert _detect_action('AÇÃO: CLASSIFICAR\nCLASSIFICAÇÃO: tipo::bug') == 'CLASSIFICAR'


def test_detect_verificar_banco():
    assert _detect_action('AÇÃO: VERIFICAR_BANCO\nCONSULTA: buscar dados') == 'VERIFICAR_BANCO'


def test_detect_alterar_codigo():
    assert _detect_action('AÇÃO: ALTERAR_CODIGO\nARQUIVO: views.py') == 'ALTERAR_CODIGO'


def test_detect_by_marker_tipo():
    assert _detect_action('blablabla tipo::prazo-expirado') == 'CLASSIFICAR'


def test_detect_by_marker_investigar():
    assert _detect_action('INVESTIGAR: app.models.M — motivo') == 'INVESTIGAR'


def test_detect_unknown():
    assert _detect_action('Não sei o que fazer') == 'DESCONHECIDO'


# ---------------------------------------------------------------------------
# _normalize_label
# ---------------------------------------------------------------------------


def test_normalize_tipo_bug():
    assert _normalize_label('tipo::bug') == 'tipo::bug'


def test_normalize_bug_prefix():
    assert _normalize_label('Bug::tempo_habil') == 'tipo::tempo-habil'


def test_normalize_spaces_accents():
    assert _normalize_label('Bug::Avaliação Não Preenchida') == 'tipo::avaliacao-nao-preenchida'


def test_normalize_markdown():
    assert _normalize_label('**tipo::prazo-expirado**') == 'tipo::prazo-expirado'


def test_normalize_uppercase():
    assert _normalize_label('TIPO::BUG') == 'tipo::bug'


# ---------------------------------------------------------------------------
# extract_tipo — formatos variados
# ---------------------------------------------------------------------------


def test_extract_standard():
    assert extract_tipo_from_analysis('CLASSIFICAÇÃO: tipo::bug') == 'tipo::bug'


def test_extract_markdown_bold():
    assert extract_tipo_from_analysis('**CLASSIFICAÇÃO:** tipo::prazo-expirado') == 'tipo::prazo-expirado'


def test_extract_bug_prefix():
    assert extract_tipo_from_analysis('CLASSIFICAÇÃO: Bug::tempo_habil') == 'tipo::tempo-habil'


def test_extract_spaces_accents():
    assert extract_tipo_from_analysis('**CLASSIFICAÇÃO:** Bug::Avaliação Não Preenchida') == 'tipo::avaliacao-nao-preenchida'


def test_extract_none():
    assert extract_tipo_from_analysis('Nenhuma classificação aqui') is None


def test_extract_new_label():
    assert extract_tipo_from_analysis('tipo::permissao') == 'tipo::permissao'


# ---------------------------------------------------------------------------
# _request_key
# ---------------------------------------------------------------------------


def test_request_key_method():
    key = _request_key({'type': 'method', 'app': 'pd', 'model': 'Avaliacao', 'method': 'TEMPO'})
    assert key == 'pd.Avaliacao.TEMPO'


def test_request_key_model():
    key = _request_key({'type': 'model', 'app': 'pd', 'model': 'Avaliacao'})
    assert key == 'pd.Avaliacao'


def test_request_key_symbol():
    key = _request_key({'type': 'symbol', 'name': 'SomeSymbol'})
    assert key == 'SomeSymbol'
