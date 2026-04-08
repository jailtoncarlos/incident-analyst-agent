"""Testes para o orquestrador da Camada 3 (agent/orchestrator.py).

Usa a mesma fixture Django de test_tools.py para testar investigate()
e format_context_for_prompt().
"""

from pathlib import Path

import pytest

from iac.agent.orchestrator import format_context_for_prompt, investigate
from iac.inspector.django import build_django_structure
from iac.inspector.graph import build_graph


@pytest.fixture
def django_project(tmp_path: Path) -> tuple[dict, dict, Path]:
    """Cria projeto Django mínimo e retorna (structure, graph, base_dir)."""
    app_dir = tmp_path / 'loja'
    app_dir.mkdir()

    (app_dir / 'views.py').write_text(
        'from django.shortcuts import render, get_object_or_404\n'
        'from loja.models import Produto\n'
        'from loja.forms import ProdutoForm\n'
        '\n'
        'def listar_produtos(request):\n'
        '    produtos = Produto.objects.all()\n'
        '    return render(request, "loja/lista.html", {"produtos": produtos})\n'
        '\n'
        'def detalhe_produto(request, pk):\n'
        '    produto = get_object_or_404(Produto, pk=pk)\n'
        '    form = ProdutoForm(instance=produto)\n'
        '    produto.incrementar_visualizacoes()\n'
        '    return render(request, "loja/detalhe.html", {"produto": produto, "form": form})\n'
    )

    (app_dir / 'models.py').write_text(
        'from django.db import models\n'
        '\n'
        'class Categoria(models.Model):\n'
        '    nome = models.CharField(max_length=100)\n'
        '\n'
        'class Produto(models.Model):\n'
        '    nome = models.CharField(max_length=200)\n'
        '    preco = models.DecimalField(max_digits=10, decimal_places=2)\n'
        '    categoria = models.ForeignKey(Categoria, on_delete=models.CASCADE)\n'
        '    visualizacoes = models.IntegerField(default=0)\n'
        '\n'
        '    def incrementar_visualizacoes(self):\n'
        '        self.visualizacoes += 1\n'
        '        self.save()\n'
    )

    (app_dir / 'forms.py').write_text(
        'from django import forms\n'
        'from loja.models import Produto\n'
        '\n'
        'class ProdutoForm(forms.ModelForm):\n'
        '    class Meta:\n'
        '        model = Produto\n'
        "        fields = ['nome', 'preco']\n"
    )

    (app_dir / 'urls.py').write_text(
        'from django.urls import path\n'
        'from loja import views\n'
        '\n'
        'urlpatterns = [\n'
        "    path('produtos/', views.listar_produtos, name='listar'),\n"
        "    path('produtos/<int:pk>/', views.detalhe_produto, name='detalhe'),\n"
        ']\n'
    )

    templates_dir = app_dir / 'templates' / 'loja'
    templates_dir.mkdir(parents=True)
    (templates_dir / 'lista.html').write_text('<h1>Produtos</h1>')
    (templates_dir / 'detalhe.html').write_text('<h1>{{ produto.nome }}</h1>')

    config = {'framework': 'django'}
    structure = build_django_structure(tmp_path, config)
    graph = build_graph(structure)

    return structure, graph, tmp_path


# ---------------------------------------------------------------------------
# investigate — por URL
# ---------------------------------------------------------------------------


def test_investigate_by_url(django_project):
    structure, graph, base_dir = django_project
    ctx = investigate(structure, graph, base_dir, url='/loja/produtos/42/')
    assert ctx['status'] == 'complete'
    assert ctx['app'] == 'loja'
    assert ctx['view_name'] == 'detalhe_produto'
    assert ctx['view_source'] is not None
    assert 'def detalhe_produto' in ctx['view_source']


def test_investigate_finds_calls(django_project):
    structure, graph, base_dir = django_project
    ctx = investigate(structure, graph, base_dir, url='/loja/produtos/42/')
    assert len(ctx['calls']) > 0
    assert any('ProdutoForm' in c for c in ctx['calls'])


def test_investigate_follows_references(django_project):
    structure, graph, base_dir = django_project
    ctx = investigate(structure, graph, base_dir, url='/loja/produtos/42/')
    assert len(ctx['references']) > 0
    ref_keys = [r['key'] for r in ctx['references']]
    assert any('ProdutoForm' in k for k in ref_keys)


def test_investigate_reference_has_source(django_project):
    structure, graph, base_dir = django_project
    ctx = investigate(structure, graph, base_dir, url='/loja/produtos/42/')
    refs_with_source = [r for r in ctx['references'] if r['source']]
    assert len(refs_with_source) > 0


# ---------------------------------------------------------------------------
# investigate — URL não encontrada
# ---------------------------------------------------------------------------


def test_investigate_url_not_found(django_project):
    structure, graph, base_dir = django_project
    ctx = investigate(structure, graph, base_dir, url='/nao/existe/')
    assert ctx['status'] == 'view_not_found'
    assert ctx['view_name'] is None


# ---------------------------------------------------------------------------
# investigate — por descrição com URL embutida
# ---------------------------------------------------------------------------


def test_investigate_by_description(django_project):
    structure, graph, base_dir = django_project
    ctx = investigate(
        structure, graph, base_dir,
        description='Erro 500 em https://example.com/loja/produtos/42/',
    )
    assert ctx['status'] == 'complete'
    assert ctx['view_name'] == 'detalhe_produto'


# ---------------------------------------------------------------------------
# investigate — controles de orçamento
# ---------------------------------------------------------------------------


def test_investigate_respects_max_steps(django_project):
    structure, graph, base_dir = django_project
    ctx = investigate(structure, graph, base_dir, url='/loja/produtos/42/', max_steps=3)
    assert ctx['steps_used'] <= 3


def test_investigate_respects_max_refs(django_project):
    structure, graph, base_dir = django_project
    ctx = investigate(structure, graph, base_dir, url='/loja/produtos/42/', max_refs=1, max_steps=20)
    assert len(ctx['references']) <= 1


# ---------------------------------------------------------------------------
# format_context_for_prompt
# ---------------------------------------------------------------------------


def test_format_context_has_view(django_project):
    structure, graph, base_dir = django_project
    ctx = investigate(structure, graph, base_dir, url='/loja/produtos/42/')
    prompt = format_context_for_prompt(ctx)
    assert 'detalhe_produto' in prompt
    assert 'loja/views.py' in prompt
    assert '```python' in prompt


def test_format_context_has_references(django_project):
    structure, graph, base_dir = django_project
    ctx = investigate(structure, graph, base_dir, url='/loja/produtos/42/')
    prompt = format_context_for_prompt(ctx)
    assert 'Referências' in prompt


def test_format_context_has_metadata(django_project):
    structure, graph, base_dir = django_project
    ctx = investigate(structure, graph, base_dir, url='/loja/produtos/42/')
    prompt = format_context_for_prompt(ctx)
    assert 'Passos:' in prompt
    assert 'Contexto:' in prompt
