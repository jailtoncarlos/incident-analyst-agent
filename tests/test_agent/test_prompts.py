"""Testes para agent/prompts.py."""

from iac.agent.prompts import (
    build_analysis_prompt,
    build_response_prompt,
    compact_code,
    extract_tipo_from_analysis,
)


# ---------------------------------------------------------------------------
# build_analysis_prompt
# ---------------------------------------------------------------------------


def _make_result():
    """Cria um resultado mínimo de analyze_issue para testes."""
    return {
        'classification': {
            'origem': 'erro-suap',
            'app': 'loja',
            'view': 'loja.views.detalhe',
            'url_erro': 'https://suap/loja/produto/1/',
            'interessado': 'João Silva (12345) (Servidor)',
            'erro_id': '9999',
            'descricao_usuario': 'O botão não funciona.',
            'tipo_sugerido': None,
            'labels_sugeridos': ['origem::erro-suap', 'loja'],
        },
        'context': {
            'app': 'loja',
            'view_name': 'detalhe',
            'view_file': 'loja/views.py',
            'view_line': 42,
            'url': '/loja/produto/1/',
            'url_pattern': '/produto/<int:pk>/',
            'view_source': 'def detalhe(request, pk):\n    return render(request, "loja/detalhe.html")',
            'calls': ['Produto.objects.get', 'ProdutoForm'],
            'references': [
                {
                    'key': 'loja.models.Produto',
                    'call': 'Produto.objects.get',
                    'file': 'loja/models.py',
                    'line': 10,
                    'source': 'class Produto(models.Model):\n    nome = models.CharField()',
                    'app': 'loja',
                    'kind': 'models',
                    'name': 'Produto',
                    'method': None,
                },
            ],
            'imports': [],
            'traceback_parsed': None,
            'steps_used': 5,
            'context_chars': 200,
            'status': 'complete',
        },
        'structural': {
            'app': 'loja',
            'rota': 'https://suap/loja/produto/1/',
            'view': 'loja.views.detalhe',
            'file': 'loja/views.py',
            'line': 42,
            'origem': 'erro-suap',
            'erro_id': '9999',
            'interessado': 'João Silva (12345) (Servidor)',
            'descricao_usuario': 'O botão não funciona.',
            'tipo_sugerido': None,
            'models': ['loja.models.Produto'],
            'forms': ['loja.forms.ProdutoForm'],
            'templates': ['loja/templates/detalhe.html'],
            'admin': [],
            'related_models': [],
            'flow': [
                {'from': 'loja/urls:/produto/<int:pk>/', 'to': 'loja.views.detalhe', 'type': 'url_resolves'},
                {'from': 'loja.views.detalhe', 'to': 'loja.models.Produto', 'type': 'model_usage'},
            ],
        },
    }


def test_analysis_prompt_has_system():
    prompt = build_analysis_prompt(_make_result())
    assert 'engenheiro de software sênior' in prompt


def test_analysis_prompt_has_issue_data():
    prompt = build_analysis_prompt(_make_result())
    assert 'Dados da issue' in prompt
    assert 'erro-suap' in prompt
    assert 'João Silva' in prompt
    assert 'O botão não funciona' in prompt


def test_analysis_prompt_has_structural():
    prompt = build_analysis_prompt(_make_result())
    assert 'Análise estrutural' in prompt
    assert 'loja.views.detalhe' in prompt
    assert 'Fluxo de interação' in prompt


def test_analysis_prompt_has_code():
    prompt = build_analysis_prompt(_make_result())
    assert 'def detalhe(request, pk)' in prompt
    assert '```python' in prompt


def test_analysis_prompt_has_instructions():
    prompt = build_analysis_prompt(_make_result())
    assert 'CLASSIFICAÇÃO: tipo::bug' in prompt
    assert 'tipo::configuracao' in prompt
    assert 'tipo::prazo-expirado' in prompt
    assert 'Plano de simulação' in prompt


# ---------------------------------------------------------------------------
# build_response_prompt
# ---------------------------------------------------------------------------


def test_response_prompt_has_orientations():
    result = _make_result()
    analysis = 'CLASSIFICAÇÃO: tipo::configuracao\nOrientação ao responsável.'
    prompt = build_response_prompt(result, analysis)
    assert 'João Silva' in prompt
    assert 'Prezado(a)' in prompt
    assert 'tipo::configuracao' in prompt
    assert 'Orientação ao responsável' in prompt


def test_response_prompt_has_analysis():
    result = _make_result()
    analysis = 'CLASSIFICAÇÃO: tipo::bug\nErro no código.'
    prompt = build_response_prompt(result, analysis)
    assert 'João Silva' in prompt
    assert 'Erro no código' in prompt
    assert 'NUNCA culpe' in prompt


# ---------------------------------------------------------------------------
# extract_tipo_from_analysis
# ---------------------------------------------------------------------------


def test_extract_tipo_bug():
    assert extract_tipo_from_analysis('CLASSIFICAÇÃO: tipo::bug') == 'tipo::bug'


def test_extract_tipo_configuracao():
    assert extract_tipo_from_analysis('**tipo::configuracao**') == 'tipo::configuracao'


def test_extract_tipo_prazo():
    assert extract_tipo_from_analysis('Classificação: tipo::prazo-expirado') == 'tipo::prazo-expirado'


def test_extract_tipo_invalid():
    assert extract_tipo_from_analysis('Nenhuma classificação aqui') is None


def test_extract_tipo_unknown():
    assert extract_tipo_from_analysis('tipo::inventado') is None


# ---------------------------------------------------------------------------
# compact_code
# ---------------------------------------------------------------------------


def test_compact_code_removes_blanks():
    code = 'def f():\n\n    return 1\n'
    assert '\n\n' not in compact_code(code)


def test_compact_code_removes_comments():
    code = '# comentário\ndef f():\n    # outro\n    return 1'
    result = compact_code(code)
    assert '# comentário' not in result
    assert 'def f()' in result


def test_compact_code_removes_docstrings():
    code = 'def f():\n    """Docstring."""\n    return 1'
    result = compact_code(code)
    assert 'Docstring' not in result
    assert 'return 1' in result
