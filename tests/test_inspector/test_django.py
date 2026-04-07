"""Testes para o parser Django."""

from pathlib import Path

from iac.inspector.django import build_django_structure


def _create_django_app(tmp_path: Path, app_name: str) -> Path:
    """Cria estrutura mínima de um app Django para testes."""
    app_dir = tmp_path / app_name
    app_dir.mkdir()

    # views.py
    (app_dir / 'views.py').write_text(
        'from django.shortcuts import render\n'
        '\n'
        'def listar_items(request):\n'
        '    items = Item.objects.all()\n'
        "    return render(request, 'items/lista.html', {'items': items})\n"
        '\n'
        'def detalhe_item(request, item_id):\n'
        '    item = Item.objects.get(pk=item_id)\n'
        '    form = ItemForm(instance=item)\n'
        "    return render(request, 'items/detalhe.html', {'item': item, 'form': form})\n"
    )

    # models.py
    (app_dir / 'models.py').write_text(
        'from django.db import models\n'
        '\n'
        'class Item(models.Model):\n'
        '    nome = models.CharField(max_length=200)\n'
        '    descricao = models.TextField()\n'
        '    ativo = models.BooleanField(default=True)\n'
        '\n'
        '    def desativar(self):\n'
        '        self.ativo = False\n'
        '        self.save()\n'
    )

    # forms.py
    (app_dir / 'forms.py').write_text(
        'from django import forms\n'
        'from .models import Item\n'
        '\n'
        'class ItemForm(forms.ModelForm):\n'
        '    class Meta:\n'
        '        model = Item\n'
        "        fields = ['nome', 'descricao']\n"
    )

    # urls.py
    (app_dir / 'urls.py').write_text(
        'from django.urls import path\n'
        'from . import views\n'
        '\n'
        'urlpatterns = [\n'
        "    path('items/', views.listar_items, name='listar'),\n"
        "    path('items/<int:item_id>/', views.detalhe_item, name='detalhe'),\n"
        ']\n'
    )

    # templates
    templates_dir = app_dir / 'templates' / 'items'
    templates_dir.mkdir(parents=True)
    (templates_dir / 'lista.html').write_text('<h1>Items</h1>')
    (templates_dir / 'detalhe.html').write_text('<h1>{{ item.nome }}</h1>')

    return app_dir


def test_build_structure_views(tmp_path: Path):
    """Deve extrair views com calls e renders."""
    _create_django_app(tmp_path, 'myapp')
    config = {'framework': 'django'}
    structure = build_django_structure(tmp_path, config)

    apps = structure['apps']
    assert 'myapp' in apps
    views = apps['myapp']['views']
    assert 'listar_items' in views
    assert 'detalhe_item' in views
    assert views['listar_items']['type'] == 'function'
    assert 'items/lista.html' in views['listar_items'].get('renders', [])


def test_build_structure_models(tmp_path: Path):
    """Deve extrair models com campos e métodos."""
    _create_django_app(tmp_path, 'myapp')
    config = {'framework': 'django'}
    structure = build_django_structure(tmp_path, config)

    models = structure['apps']['myapp']['models']
    assert 'Item' in models
    assert 'nome' in models['Item']['fields']
    assert 'descricao' in models['Item']['fields']
    assert 'desativar' in models['Item']['methods']


def test_build_structure_forms(tmp_path: Path):
    """Deve extrair forms com Meta.model."""
    _create_django_app(tmp_path, 'myapp')
    config = {'framework': 'django'}
    structure = build_django_structure(tmp_path, config)

    forms = structure['apps']['myapp']['forms']
    assert 'ItemForm' in forms
    assert forms['ItemForm']['meta_model'] == 'Item'


def test_build_structure_urls(tmp_path: Path):
    """Deve extrair padrões de URL."""
    _create_django_app(tmp_path, 'myapp')
    config = {'framework': 'django'}
    structure = build_django_structure(tmp_path, config)

    urls = structure['apps']['myapp']['urls']
    assert len(urls) == 2
    assert any(u['view'] == 'views.listar_items' for u in urls)


def test_build_structure_templates(tmp_path: Path):
    """Deve listar templates."""
    _create_django_app(tmp_path, 'myapp')
    config = {'framework': 'django'}
    structure = build_django_structure(tmp_path, config)

    templates = structure['apps']['myapp']['templates']
    assert 'items/lista.html' in templates
    assert 'items/detalhe.html' in templates
