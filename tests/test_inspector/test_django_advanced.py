"""Testes para features avançados do parser Django.

Cobre: tuplas no settings, pacotes views/models, sintaxe Python 2,
admin.py, FK/M2M, methods com linha.
"""

from pathlib import Path

from iac.inspector.django import (
    _collect_settings_content,
    _extract_installed_apps,
    _fix_legacy_syntax,
    _has_django_module,
    _parse_admin,
    _parse_module,
    build_django_structure,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _create_settings_with_tuples(tmp_path: Path) -> Path:
    """Cria settings usando tuplas () e indireção APPS_SUAP."""
    settings_dir = tmp_path / 'myproject'
    settings_dir.mkdir()

    (settings_dir / 'settings_base.py').write_text(
        "APPS_SUAP = (\n"
        "    'app_a',\n"
        "    'app_b',\n"
        "    'app_c',\n"
        ")\n"
        "\n"
        "PRE_INSTALLED_APPS = (\n"
        "    'django.contrib.admin',\n"
        "    'myutil',\n"
        ")\n"
    )

    (settings_dir / 'settings.py').write_text(
        "from .settings_base import *\n"
        "\n"
        "DEBUG = True\n"
    )

    return settings_dir / 'settings.py'


def _create_app_with_packages(tmp_path: Path, app_name: str) -> Path:
    """Cria app com views/ e models/ como pacotes (diretórios)."""
    app_dir = tmp_path / app_name
    app_dir.mkdir()

    views_dir = app_dir / 'views'
    views_dir.mkdir()
    (views_dir / '__init__.py').write_text('')
    (views_dir / 'alunos.py').write_text(
        'def listar_alunos(request):\n'
        '    return render(request, "alunos.html")\n'
    )

    models_dir = app_dir / 'models'
    models_dir.mkdir()
    (models_dir / '__init__.py').write_text('')
    (models_dir / 'aluno.py').write_text(
        'from django.db import models\n'
        '\n'
        'class Aluno(models.Model):\n'
        '    nome = models.CharField(max_length=200)\n'
        '    matricula = models.CharField(max_length=20)\n'
        '\n'
        '    def get_nome_completo(self):\n'
        '        return self.nome\n'
    )

    return app_dir


def _create_app_with_admin(tmp_path: Path, app_name: str) -> Path:
    """Cria app com admin.py contendo registros."""
    app_dir = tmp_path / app_name
    app_dir.mkdir()

    (app_dir / 'models.py').write_text(
        'from django.db import models\n'
        '\n'
        'class Produto(models.Model):\n'
        '    nome = models.CharField(max_length=200)\n'
        '    categoria = models.ForeignKey("Categoria", on_delete=models.CASCADE)\n'
        '\n'
        'class Categoria(models.Model):\n'
        '    nome = models.CharField(max_length=100)\n'
    )

    (app_dir / 'forms.py').write_text(
        'from django import forms\n'
        'class ProdutoForm(forms.ModelForm):\n'
        '    class Meta:\n'
        '        model = Produto\n'
        "        fields = ['nome']\n"
    )

    (app_dir / 'views.py').write_text(
        'def listar(request): pass\n'
    )

    (app_dir / 'admin.py').write_text(
        'from django.contrib import admin\n'
        'from .models import Produto, Categoria\n'
        'from .forms import ProdutoForm\n'
        '\n'
        '@admin.register(Produto)\n'
        'class ProdutoAdmin(admin.ModelAdmin):\n'
        '    form = ProdutoForm\n'
        '    list_display = ["nome"]\n'
        '\n'
        'admin.site.register(Categoria)\n'
    )

    (app_dir / 'urls.py').write_text('')

    return app_dir


# ---------------------------------------------------------------------------
# Testes: tuplas no settings
# ---------------------------------------------------------------------------


def test_extract_installed_apps_tuples(tmp_path: Path):
    """Deve extrair apps de tuplas () no settings."""
    settings_path = _create_settings_with_tuples(tmp_path)
    apps = _extract_installed_apps(settings_path)
    assert 'app_a' in apps
    assert 'app_b' in apps
    assert 'app_c' in apps
    assert 'myutil' in apps


def test_extract_installed_apps_follows_imports(tmp_path: Path):
    """Deve seguir from .settings_base import * para encontrar apps."""
    settings_path = _create_settings_with_tuples(tmp_path)
    content = _collect_settings_content(settings_path)
    assert 'APPS_SUAP' in content
    assert 'app_a' in content


# ---------------------------------------------------------------------------
# Testes: pacotes views/ e models/
# ---------------------------------------------------------------------------


def test_has_django_module_file(tmp_path: Path):
    """Deve detectar views.py como arquivo."""
    app_dir = tmp_path / 'myapp'
    app_dir.mkdir()
    (app_dir / 'views.py').write_text('')
    assert _has_django_module(app_dir) is True


def test_has_django_module_package(tmp_path: Path):
    """Deve detectar views/ como pacote (diretório)."""
    app_dir = tmp_path / 'myapp'
    app_dir.mkdir()
    (app_dir / 'views').mkdir()
    assert _has_django_module(app_dir) is True


def test_has_django_module_none(tmp_path: Path):
    """Deve retornar False sem views nem models."""
    app_dir = tmp_path / 'myapp'
    app_dir.mkdir()
    assert _has_django_module(app_dir) is False


def test_parse_module_from_package(tmp_path: Path):
    """Deve parsear views de um pacote views/."""
    app_dir = _create_app_with_packages(tmp_path, 'edu')
    result = _parse_module(app_dir, 'views')
    assert 'listar_alunos' in result


def test_parse_module_models_from_package(tmp_path: Path):
    """Deve parsear models de um pacote models/."""
    app_dir = _create_app_with_packages(tmp_path, 'edu')
    result = _parse_module(app_dir, 'models')
    assert 'Aluno' in result
    assert 'nome' in result['Aluno']['fields']
    assert 'get_nome_completo' in result['Aluno']['methods']


# ---------------------------------------------------------------------------
# Testes: fix sintaxe Python 2
# ---------------------------------------------------------------------------


def test_fix_legacy_syntax_two_types():
    """Deve corrigir except Type, Type: para except (Type, Type):."""
    source = 'try:\n    pass\nexcept TypeError, ValueError:\n    pass'
    fixed = _fix_legacy_syntax(source)
    assert 'except (TypeError, ValueError):' in fixed


def test_fix_legacy_syntax_three_types():
    """Deve corrigir except com 3 tipos."""
    source = 'except ValueError, TypeError, KeyError:'
    fixed = _fix_legacy_syntax(source)
    assert 'except (ValueError, TypeError, KeyError):' in fixed


def test_fix_legacy_syntax_dotted_names():
    """Deve corrigir except com nomes qualificados (A.DoesNotExist)."""
    source = 'except Model.DoesNotExist, KeyError:'
    fixed = _fix_legacy_syntax(source)
    assert 'except (Model.DoesNotExist, KeyError):' in fixed


def test_fix_legacy_syntax_preserves_valid():
    """Não deve alterar sintaxe Python 3 válida."""
    source = 'except (TypeError, ValueError):'
    fixed = _fix_legacy_syntax(source)
    assert fixed == source


# ---------------------------------------------------------------------------
# Testes: admin.py
# ---------------------------------------------------------------------------


def test_parse_admin_register_decorator(tmp_path: Path):
    """Deve capturar @admin.register(Model)."""
    app_dir = _create_app_with_admin(tmp_path, 'loja')
    admin = _parse_admin(app_dir)
    assert 'ProdutoAdmin' in admin
    assert 'Produto' in admin['ProdutoAdmin']['models']


def test_parse_admin_form(tmp_path: Path):
    """Deve capturar atributo form do ModelAdmin."""
    app_dir = _create_app_with_admin(tmp_path, 'loja')
    admin = _parse_admin(app_dir)
    assert admin['ProdutoAdmin']['form'] == 'ProdutoForm'


def test_parse_admin_site_register(tmp_path: Path):
    """Deve capturar admin.site.register(Model) sem classe admin."""
    app_dir = _create_app_with_admin(tmp_path, 'loja')
    admin = _parse_admin(app_dir)
    auto_key = 'CategoriaAdmin_auto'
    assert auto_key in admin
    assert 'Categoria' in admin[auto_key]['models']


# ---------------------------------------------------------------------------
# Testes: FK/M2M references
# ---------------------------------------------------------------------------


def test_fk_references_extracted(tmp_path: Path):
    """Deve extrair referências FK/M2M nos models."""
    app_dir = _create_app_with_admin(tmp_path, 'loja')
    models = _parse_module(app_dir, 'models')
    assert 'Produto' in models
    assert 'Categoria' in models['Produto'].get('fk_references', [])


# ---------------------------------------------------------------------------
# Testes: methods com linha
# ---------------------------------------------------------------------------


def test_methods_have_line_numbers(tmp_path: Path):
    """Methods devem ser dict com linha individual."""
    app_dir = _create_app_with_packages(tmp_path, 'edu')
    models = _parse_module(app_dir, 'models')
    methods = models['Aluno']['methods']
    assert isinstance(methods, dict)
    assert 'get_nome_completo' in methods
    assert isinstance(methods['get_nome_completo']['line'], int)
    assert methods['get_nome_completo']['line'] > 0
