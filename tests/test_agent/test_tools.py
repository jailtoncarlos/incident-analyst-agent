"""Testes para as ferramentas da Camada 2 (agent/tools.py).

Usa uma fixture Django mínima com structure.json e graph.json
gerados pelo inspector, para testar as 7 ferramentas de navegação.
"""

from pathlib import Path

import pytest

from iac.agent.tools import (
    buscar_simbolo,
    extrair_chamadas,
    ler_funcao,
    listar_imports,
    localizar_arquivo,
    resolver_rota,
    seguir_referencia,
)
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
        '\n'
        '    def esta_em_estoque(self):\n'
        '        return self.preco > 0\n'
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
# resolver_rota
# ---------------------------------------------------------------------------


def test_resolver_rota_exact(django_project):
    structure, graph, base_dir = django_project
    result = resolver_rota('/loja/produtos/', structure)
    assert result is not None
    assert result['app'] == 'loja'
    assert result['view_name'] == 'listar_produtos'


def test_resolver_rota_with_param(django_project):
    structure, graph, base_dir = django_project
    result = resolver_rota('/loja/produtos/42/', structure)
    assert result is not None
    assert result['view_name'] == 'detalhe_produto'


def test_resolver_rota_not_found(django_project):
    structure, graph, base_dir = django_project
    result = resolver_rota('/inexistente/xyz/', structure)
    assert result is None


# ---------------------------------------------------------------------------
# localizar_arquivo
# ---------------------------------------------------------------------------


def test_localizar_arquivo_full_qualified(django_project):
    structure, graph, base_dir = django_project
    result = localizar_arquivo('loja.views.listar_produtos', structure)
    assert result is not None
    assert result['app'] == 'loja'
    assert result['kind'] == 'views'
    assert result['file'] == 'loja/views.py'
    assert result['line'] > 0


def test_localizar_arquivo_model(django_project):
    structure, graph, base_dir = django_project
    result = localizar_arquivo('loja.models.Produto', structure)
    assert result is not None
    assert result['kind'] == 'models'


def test_localizar_arquivo_simple_name(django_project):
    structure, graph, base_dir = django_project
    result = localizar_arquivo('ProdutoForm', structure)
    assert result is not None
    assert result['kind'] == 'forms'


def test_localizar_arquivo_not_found(django_project):
    structure, graph, base_dir = django_project
    result = localizar_arquivo('NaoExiste', structure)
    assert result is None


# ---------------------------------------------------------------------------
# ler_funcao
# ---------------------------------------------------------------------------


def test_ler_funcao_view(django_project):
    structure, graph, base_dir = django_project
    loc = localizar_arquivo('loja.views.detalhe_produto', structure)
    source = ler_funcao(loc['file'], loc['line'], base_dir)
    assert source is not None
    assert 'def detalhe_produto' in source
    assert 'get_object_or_404' in source


def test_ler_funcao_method(django_project):
    structure, graph, base_dir = django_project
    loc = localizar_arquivo('loja.models.Produto', structure)
    methods = structure['apps']['loja']['models']['Produto']['methods']
    method_line = methods['incrementar_visualizacoes']['line']
    source = ler_funcao(loc['file'], method_line, base_dir)
    assert source is not None
    assert 'incrementar_visualizacoes' in source


def test_ler_funcao_with_method_param(django_project):
    structure, graph, base_dir = django_project
    loc = localizar_arquivo('loja.models.Produto', structure)
    source = ler_funcao(loc['file'], loc['line'], base_dir, method='esta_em_estoque')
    assert source is not None
    assert 'esta_em_estoque' in source
    assert 'def incrementar_visualizacoes' not in source


# ---------------------------------------------------------------------------
# extrair_chamadas
# ---------------------------------------------------------------------------


def test_extrair_chamadas(django_project):
    structure, graph, base_dir = django_project
    calls = extrair_chamadas('loja.views.detalhe_produto', structure)
    assert len(calls) > 0
    assert any('ProdutoForm' in c for c in calls)


def test_extrair_chamadas_not_found(django_project):
    structure, graph, base_dir = django_project
    calls = extrair_chamadas('nao.existe.nada', structure)
    assert calls == []


# ---------------------------------------------------------------------------
# seguir_referencia
# ---------------------------------------------------------------------------


def test_seguir_referencia_form(django_project):
    structure, graph, base_dir = django_project
    ref = seguir_referencia('ProdutoForm', 'loja', structure, graph)
    assert ref is not None
    assert ref['kind'] == 'forms'
    assert ref['name'] == 'ProdutoForm'


def test_seguir_referencia_method(django_project):
    structure, graph, base_dir = django_project
    ref = seguir_referencia('produto.incrementar_visualizacoes', 'loja', structure, graph)
    assert ref is not None
    assert ref['kind'] == 'models'
    assert ref['name'] == 'Produto'
    assert ref['method'] == 'incrementar_visualizacoes'
    assert ref.get('method_line') is not None


def test_seguir_referencia_not_found(django_project):
    structure, graph, base_dir = django_project
    ref = seguir_referencia('totalmente.inexistente', 'loja', structure, graph)
    assert ref is None


# ---------------------------------------------------------------------------
# listar_imports
# ---------------------------------------------------------------------------


def test_listar_imports(django_project):
    structure, graph, base_dir = django_project
    imports = listar_imports('loja/views.py', base_dir)
    assert len(imports) > 0
    modules = [i['module'] for i in imports]
    assert any('shortcuts' in m for m in modules)


# ---------------------------------------------------------------------------
# buscar_simbolo
# ---------------------------------------------------------------------------


def test_buscar_simbolo(django_project):
    structure, graph, base_dir = django_project
    results = buscar_simbolo('class Produto', base_dir)
    assert len(results) > 0
    assert any('models.py' in r['file'] for r in results)


# ---------------------------------------------------------------------------
# graph.py — arestas
# ---------------------------------------------------------------------------


def test_graph_url_resolves(django_project):
    structure, graph, base_dir = django_project
    url_edges = [e for e in graph['edges'] if e['type'] == 'url_resolves']
    assert len(url_edges) > 0


def test_graph_model_usage(django_project):
    structure, graph, base_dir = django_project
    model_edges = [e for e in graph['edges'] if e['type'] == 'model_usage']
    assert len(model_edges) > 0


def test_graph_form_model(django_project):
    structure, graph, base_dir = django_project
    form_edges = [e for e in graph['edges'] if e['type'] == 'form_model']
    assert any('ProdutoForm' in e['from'] for e in form_edges)


def test_graph_model_relation(django_project):
    structure, graph, base_dir = django_project
    fk_edges = [e for e in graph['edges'] if e['type'] == 'model_relation']
    assert any('Produto' in e['from'] and 'Categoria' in e['to'] for e in fk_edges)


def test_graph_renders(django_project):
    structure, graph, base_dir = django_project
    render_edges = [e for e in graph['edges'] if e['type'] == 'renders']
    assert len(render_edges) > 0
