"""Testes para merge de profiles (defaults + projeto).

Garante que _merge_profiles faz:
- system_description: projeto sobrescreve
- rules: projeto sobrescreve
- issue_patterns: merge (default + projeto)
- app_aliases: merge (default + projeto)
- url_skip_segments: UNIÃO (default + projeto)
- taxonomy.known_tipos: UNIÃO
- taxonomy.aliases: merge (projeto tem prioridade)
"""

from iac.config.settings import _merge_profiles


# ---------------------------------------------------------------------------
# Campos simples — projeto sobrescreve default
# ---------------------------------------------------------------------------


def test_system_description_projeto_sobrescreve():
    defaults = {'system_description': 'Django'}
    project = {'system_description': 'SUAP (ERP Django)'}
    result = _merge_profiles(defaults, project)
    assert result['system_description'] == 'SUAP (ERP Django)'


def test_system_description_usa_default_se_projeto_vazio():
    defaults = {'system_description': 'Django'}
    project = {}
    result = _merge_profiles(defaults, project)
    assert result['system_description'] == 'Django'


def test_rules_projeto_sobrescreve():
    defaults = {'rules': ['regra default']}
    project = {'rules': ['regra do projeto']}
    result = _merge_profiles(defaults, project)
    assert result['rules'] == ['regra do projeto']


def test_rules_usa_default_se_projeto_nao_define():
    defaults = {'rules': ['regra default']}
    project = {}
    result = _merge_profiles(defaults, project)
    assert result['rules'] == ['regra default']


# ---------------------------------------------------------------------------
# issue_patterns — merge (default + projeto)
# ---------------------------------------------------------------------------


def test_issue_patterns_merge():
    defaults = {'issue_patterns': {'title_regex': r'^Erro\s+(\d+)', 'origin_name': 'erro-sistema'}}
    project = {'issue_patterns': {'origin_name': 'erro-suap', 'origin_marker': '**Erro no Suap**:'}}
    result = _merge_profiles(defaults, project)
    assert result['issue_patterns']['title_regex'] == r'^Erro\s+(\d+)'  # do default
    assert result['issue_patterns']['origin_name'] == 'erro-suap'  # projeto sobrescreve
    assert result['issue_patterns']['origin_marker'] == '**Erro no Suap**:'  # do projeto


def test_issue_patterns_usa_default_se_projeto_vazio():
    defaults = {'issue_patterns': {'title_regex': r'^Erro'}}
    project = {}
    result = _merge_profiles(defaults, project)
    assert result['issue_patterns']['title_regex'] == r'^Erro'


# ---------------------------------------------------------------------------
# app_aliases — merge (default + projeto)
# ---------------------------------------------------------------------------


def test_app_aliases_merge():
    defaults = {'app_aliases': {'Ensino': 'edu'}}
    project = {'app_aliases': {'Eventos': 'eventos', 'Ensino': 'educacao'}}
    result = _merge_profiles(defaults, project)
    assert result['app_aliases']['Eventos'] == 'eventos'  # do projeto
    assert result['app_aliases']['Ensino'] == 'educacao'  # projeto sobrescreve


def test_app_aliases_usa_default_se_projeto_vazio():
    defaults = {'app_aliases': {'Ensino': 'edu'}}
    project = {}
    result = _merge_profiles(defaults, project)
    assert result['app_aliases'] == {'Ensino': 'edu'}


# ---------------------------------------------------------------------------
# url_skip_segments — UNIÃO (default + projeto)
# ---------------------------------------------------------------------------


def test_url_skip_segments_uniao():
    defaults = {'url_skip_segments': ['admin', 'api', 'static']}
    project = {'url_skip_segments': ['djtools']}
    result = _merge_profiles(defaults, project)
    segments = set(result['url_skip_segments'])
    assert 'admin' in segments  # do default
    assert 'api' in segments  # do default
    assert 'djtools' in segments  # do projeto


def test_url_skip_segments_sem_duplicatas():
    defaults = {'url_skip_segments': ['admin', 'api']}
    project = {'url_skip_segments': ['admin', 'djtools']}
    result = _merge_profiles(defaults, project)
    assert len(result['url_skip_segments']) == len(set(result['url_skip_segments']))


def test_url_skip_segments_usa_default_se_projeto_vazio():
    defaults = {'url_skip_segments': ['admin', 'api']}
    project = {}
    result = _merge_profiles(defaults, project)
    assert set(result['url_skip_segments']) == {'admin', 'api'}


# ---------------------------------------------------------------------------
# taxonomy.known_tipos — UNIÃO
# ---------------------------------------------------------------------------


def test_taxonomy_known_tipos_uniao():
    defaults = {'taxonomy': {'known_tipos': ['tipo::bug', 'tipo::configuracao']}}
    project = {'taxonomy': {'known_tipos': ['tipo::custom']}}
    result = _merge_profiles(defaults, project)
    known = result['taxonomy']['known_tipos']
    assert 'tipo::bug' in known
    assert 'tipo::configuracao' in known
    assert 'tipo::custom' in known


def test_taxonomy_known_tipos_usa_default_se_projeto_vazio():
    defaults = {'taxonomy': {'known_tipos': ['tipo::bug']}}
    project = {}
    result = _merge_profiles(defaults, project)
    assert 'tipo::bug' in result['taxonomy']['known_tipos']


# ---------------------------------------------------------------------------
# taxonomy.aliases — merge (projeto tem prioridade)
# ---------------------------------------------------------------------------


def test_taxonomy_aliases_merge():
    defaults = {'taxonomy': {'aliases': {'tipo::logica-incorreta': 'tipo::bug'}}}
    project = {'taxonomy': {'aliases': {'tipo::avaliacao-nao-disponivel': 'tipo::prazo-expirado'}}}
    result = _merge_profiles(defaults, project)
    aliases = result['taxonomy']['aliases']
    assert aliases['tipo::logica-incorreta'] == 'tipo::bug'  # do default
    assert aliases['tipo::avaliacao-nao-disponivel'] == 'tipo::prazo-expirado'  # do projeto


def test_taxonomy_aliases_projeto_sobrescreve():
    defaults = {'taxonomy': {'aliases': {'tipo::custom': 'tipo::bug'}}}
    project = {'taxonomy': {'aliases': {'tipo::custom': 'tipo::configuracao'}}}
    result = _merge_profiles(defaults, project)
    assert result['taxonomy']['aliases']['tipo::custom'] == 'tipo::configuracao'


# ---------------------------------------------------------------------------
# Merge completo — cenário realista
# ---------------------------------------------------------------------------


def test_merge_completo():
    """Simula merge de defaults + profile SUAP."""
    defaults = {
        'name': '',
        'system_description': 'Django',
        'rules': [],
        'issue_patterns': {},
        'app_aliases': {},
        'url_skip_segments': ['admin', 'api', 'static', 'media', 'accounts'],
        'taxonomy': {
            'known_tipos': ['tipo::bug', 'tipo::nao-e-erro', 'tipo::prazo-expirado'],
            'aliases': {'tipo::logica-incorreta': 'tipo::bug'},
        },
    }
    project = {
        'name': 'SUAP',
        'system_description': 'SUAP (ERP Django)',
        'rules': ['Regra SUAP 1'],
        'issue_patterns': {'origin_name': 'erro-suap'},
        'app_aliases': {'Ensino': 'edu'},
        'url_skip_segments': ['djtools'],
        'taxonomy': {
            'aliases': {'tipo::avaliacao-nao-disponivel': 'tipo::prazo-expirado'},
        },
    }
    result = _merge_profiles(defaults, project)

    assert result['name'] == 'SUAP'
    assert result['system_description'] == 'SUAP (ERP Django)'
    assert result['rules'] == ['Regra SUAP 1']
    assert result['issue_patterns'] == {'origin_name': 'erro-suap'}
    assert result['app_aliases'] == {'Ensino': 'edu'}
    assert 'admin' in result['url_skip_segments']
    assert 'djtools' in result['url_skip_segments']
    assert 'tipo::bug' in result['taxonomy']['known_tipos']
    assert result['taxonomy']['aliases']['tipo::logica-incorreta'] == 'tipo::bug'
    assert result['taxonomy']['aliases']['tipo::avaliacao-nao-disponivel'] == 'tipo::prazo-expirado'
