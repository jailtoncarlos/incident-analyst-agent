"""Testes para o classificador de incidentes (analyzer/classifier.py).

Testes de core (genéricos) + testes com profile SUAP.
"""

from iac.analyzer.classifier import classify

# Profile SUAP para testes que dependem de padrões específicos
SUAP_PROFILE = {
    'issue_patterns': {
        'title_regex': r'^Erro\s+(\d+)\s*[-\u2013\u2014]\s*(.+)$',
        'origin_name': 'erro-suap',
        'origin_marker': '**Erro no Suap**:',
        'error_link_regex': r'/erro/(\d+)/',
    },
    'app_aliases': {
        'Central de Serviços': 'centralservicos',
        'Ensino': 'edu',
        'Eventos': 'eventos',
        'Progressão Docente': 'progressao_docente',
        'Comum': 'comum',
        'Enquetes': 'enquete',
    },
    'url_skip_segments': ['admin', 'djtools', 'accounts', 'api', 'static', 'media'],
}


# ---------------------------------------------------------------------------
# Core (genérico — sem profile)
# ---------------------------------------------------------------------------


def test_origem_sentry_label():
    result = classify('ValueError: invalid', '', labels=['sentry', 'ponto'])
    assert result['origem'] == 'sentry'
    assert result['tipo_sugerido'] == 'tipo::bug'


def test_origem_sentry_title():
    result = classify('AttributeError: object has no attribute', '')
    assert result['origem'] == 'sentry'


def test_origem_reporte_manual():
    result = classify('Problema no sistema', 'O botão não funciona')
    assert result['origem'] == 'reporte-manual'


def test_app_da_view():
    desc = '**View**: progressao_docente.views.ver_avaliacoes_discente'
    result = classify('Erro 9645', desc)
    assert result['app'] == 'progressao_docente'


def test_app_da_view_admin():
    desc = '**View**: admin.comum.comum_registronotificacao_changelist'
    result = classify('Erro 9693 - Comum', desc, profile=SUAP_PROFILE)
    assert result['app'] == 'comum'


def test_traceback_bloco_codigo():
    desc = (
        'Sentry Issue: link\n\n'
        '```\n'
        'ValueError: invalid\n'
        '  File "ponto/views.py", line 3041, in solicitar_abono\n'
        '```\n'
    )
    result = classify('ValueError: invalid', desc, labels=['sentry'])
    assert result['traceback'] is not None
    assert 'ponto/views.py' in result['traceback']


def test_traceback_inline():
    desc = 'File "enquete/views.py", line 173, in responder_enquete'
    result = classify('AttributeError: ...', desc, labels=['sentry'])
    assert result['traceback'] is not None
    assert 'enquete/views.py' in result['traceback']


def test_labels_sentry():
    result = classify('ValueError: x', '', labels=['sentry', 'ponto'])
    assert 'origem::sentry' in result['labels_sugeridos']
    assert 'tipo::bug' in result['labels_sugeridos']


# ---------------------------------------------------------------------------
# Com profile SUAP
# ---------------------------------------------------------------------------


def test_origem_erro_suap():
    result = classify('Erro 9645 - Progressão Docente', '', profile=SUAP_PROFILE)
    assert result['origem'] == 'erro-suap'
    assert result['erro_id'] == '9645'


def test_origem_campos_estruturados():
    result = classify('Título genérico', '**Erro no Suap**: https://suap/erros/1/', profile=SUAP_PROFILE)
    assert result['origem'] == 'erro-suap'


DESCRICAO_COMPLETA = (
    '**Erro no Suap**: https://suap.ifrn.edu.br/erros/erro/9645/\n\n'
    '**URL com erro**: https://suap.ifrn.edu.br/progressao_docente/ver_avaliacoes_discente/\n\n'
    '**Sentry**: None\n\n'
    '**View**: progressao_docente.views.ver_avaliacoes_discente\n\n'
    '**Descrição**: não conseguiu visualizar a avaliação em tempo hábil.\n\n'
    '**Interessado principal**: José Rosinaldo de Luna (20231124120023) (Aluno)\n'
)


def test_extrair_view():
    result = classify('Erro 9645 - Progressão Docente', DESCRICAO_COMPLETA, profile=SUAP_PROFILE)
    assert result['view'] == 'progressao_docente.views.ver_avaliacoes_discente'


def test_extrair_url_erro():
    result = classify('Erro 9645 - Progressão Docente', DESCRICAO_COMPLETA, profile=SUAP_PROFILE)
    assert result['url_erro'] == 'https://suap.ifrn.edu.br/progressao_docente/ver_avaliacoes_discente/'


def test_extrair_interessado():
    result = classify('Erro 9645 - Progressão Docente', DESCRICAO_COMPLETA, profile=SUAP_PROFILE)
    assert 'José Rosinaldo de Luna' in result['interessado']


def test_extrair_descricao_usuario():
    result = classify('Erro 9645 - Progressão Docente', DESCRICAO_COMPLETA, profile=SUAP_PROFILE)
    assert 'não conseguiu visualizar' in result['descricao_usuario']


def test_extrair_erro_id_do_titulo():
    result = classify('Erro 9645 - Progressão Docente', DESCRICAO_COMPLETA, profile=SUAP_PROFILE)
    assert result['erro_id'] == '9645'


def test_extrair_erro_id_do_link():
    desc = '**Erro no Suap**: https://suap.ifrn.edu.br/erros/erro/9999/'
    result = classify('Título genérico', desc, profile=SUAP_PROFILE)
    assert result['erro_id'] == '9999'


def test_sentry_url_none():
    result = classify('Erro 9645 - Progressão Docente', DESCRICAO_COMPLETA, profile=SUAP_PROFILE)
    assert result['sentry_url'] is None


def test_sentry_url_presente():
    desc = '**Sentry**: http://sentry.ifrn.edu.br/issues/5762/'
    result = classify('Erro 9679 - Enquetes', desc, profile=SUAP_PROFILE)
    assert result['sentry_url'] == 'http://sentry.ifrn.edu.br/issues/5762/'


def test_app_do_titulo():
    result = classify('Erro 9660 - Eventos', '', profile=SUAP_PROFILE)
    assert result['app'] == 'eventos'


def test_app_do_titulo_alias():
    result = classify('Erro 9678 - Ensino', '', profile=SUAP_PROFILE)
    assert result['app'] == 'edu'


def test_app_da_url():
    desc = '**URL com erro**: https://suap.ifrn.edu.br/enquete/responder/1/'
    result = classify('Título sem app', desc, profile=SUAP_PROFILE)
    assert result['app'] == 'enquete'


def test_labels_erro_suap():
    result = classify('Erro 9645 - Progressão Docente', DESCRICAO_COMPLETA, profile=SUAP_PROFILE)
    assert 'origem::erro-suap' in result['labels_sugeridos']
    assert 'progressao_docente' in result['labels_sugeridos']
