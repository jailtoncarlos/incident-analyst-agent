"""Testes de regressão para o loop interativo.

Cobre: _detect_action, _normalize_label, extract_tipo com formatos variados,
_request_key, detecção de repetição.
"""

from iac.agent.loop import _detect_action, _request_key
from iac.agent.prompts.utils import (
    _normalize_label,
    extract_classificacao,
    extract_tipo_from_analysis,
    normalize_to_known,
)


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


# ---------------------------------------------------------------------------
# _detect_action — variantes de CLASSIFICAR (#52)
# ---------------------------------------------------------------------------


def test_detect_classificar_markdown():
    """CLASSIFICAR com bold markdown — deve reconhecer."""
    assert _detect_action('**AÇÃO: CLASSIFICAR**\n**CLASSIFICAÇÃO:** tipo::bug') == 'CLASSIFICAR'


def test_detect_classificar_solo():
    """CLASSIFICAR sozinho em linha — deve reconhecer."""
    assert _detect_action('Análise completa.\n\nCLASSIFICAR\n\nO problema é...') == 'CLASSIFICAR'


def test_detect_classificar_sections():
    """Seções ### Análise + ### Resolução sem AÇÃO: — deve inferir CLASSIFICAR."""
    response = '### Análise\nCausa raiz...\n### Resolução\nCorrigir...'
    assert _detect_action(response) == 'CLASSIFICAR'


def test_detect_classificacao_without_accents():
    """CLASSIFICACAO sem acento — deve reconhecer."""
    assert _detect_action('CLASSIFICACAO: tipo::prazo-expirado') == 'CLASSIFICAR'


# ---------------------------------------------------------------------------
# normalize_to_known — taxonomia (#52)
# ---------------------------------------------------------------------------


def test_normalize_avaliacao_nao_disponivel():
    assert normalize_to_known('tipo::avaliacao-nao-disponivel') == 'tipo::prazo-expirado'


def test_normalize_logica_incorreta():
    assert normalize_to_known('tipo::logica-incorreta') == 'tipo::bug'


def test_normalize_acesso_negado():
    assert normalize_to_known('tipo::acesso-negado') == 'tipo::permissao'


def test_normalize_unknown_returns_none():
    assert normalize_to_known('tipo::algo-desconhecido') is None


def test_normalize_known_tipo_not_aliased():
    """Labels já conhecidos não precisam de alias."""
    assert normalize_to_known('tipo::bug') is None
    assert normalize_to_known('tipo::prazo-expirado') is None


def test_normalize_tempo_aliases():
    """Labels temporais criativos devem normalizar para prazo-expirado."""
    assert normalize_to_known('tipo::tempo-de-execucao-insuficiente') == 'tipo::prazo-expirado'
    assert normalize_to_known('tipo::tempo-habil-para-avaliacao') == 'tipo::prazo-expirado'
    assert normalize_to_known('tipo::tempo-de-avaliacao-insuficiente') == 'tipo::prazo-expirado'


def test_normalize_comportamento_esperado():
    assert normalize_to_known('tipo::comportamento-esperado') == 'tipo::nao-e-erro'


# ---------------------------------------------------------------------------
# extract_classificacao — labels sem prefixo tipo:: (#57 melhoria 2)
# ---------------------------------------------------------------------------


def test_extract_bare_label_bug():
    """CLASSIFICAÇÃO: bug (sem tipo::) deve resolver para tipo::bug."""
    result = extract_classificacao('CLASSIFICAÇÃO: bug\nSUBCLASSIFICAÇÃO: logica-incorreta')
    assert result['classificacao'] == 'tipo::bug'
    assert result['subclassificacao'] == 'tipo::bug'  # logica-incorreta → bug via alias


def test_extract_bare_label_nao_e_erro():
    """CLASSIFICAÇÃO: nao-e-erro → tipo::nao-e-erro."""
    result = extract_classificacao('CLASSIFICAÇÃO: nao-e-erro')
    assert result['classificacao'] == 'tipo::nao-e-erro'


def test_extract_bare_label_permissao():
    """CLASSIFICAÇÃO: permissao → tipo::permissao."""
    result = extract_classificacao('CLASSIFICAÇÃO: permissao')
    assert result['classificacao'] == 'tipo::permissao'


def test_extract_subclassificacao_normalized():
    """Subclassificação fora do catálogo deve ser normalizada."""
    result = extract_classificacao('CLASSIFICAÇÃO: tipo::nao-e-erro\nSUBCLASSIFICAÇÃO: tipo::comportamento-esperado')
    assert result['classificacao'] == 'tipo::nao-e-erro'
    assert result['subclassificacao'] == 'tipo::nao-e-erro'  # comportamento-esperado → nao-e-erro


def test_extract_subclassificacao_prazo():
    """Subclassificação prazo-expirado ou alias deve normalizar."""
    result = extract_classificacao('CLASSIFICAÇÃO: tipo::nao-e-erro\nSUBCLASSIFICAÇÃO: tipo::prazo-expirado')
    assert result['classificacao'] == 'tipo::nao-e-erro'
    assert result['subclassificacao'] == 'tipo::prazo-expirado'  # já é known, mantém
