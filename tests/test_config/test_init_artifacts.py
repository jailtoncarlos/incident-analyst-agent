"""Testes para artefatos gerados pelo iac init.

Garante que ao executar pela primeira vez num repositório novo:
- .iac/.env é gerado com template comentado
- .iac/profile.yaml é gerado vazio (só orientações e nome do projeto)
- .iac/logs/ é criado
- profile.yaml NÃO contém taxonomy preenchida (usa defaults do IAC)
- profile.yaml NÃO contém url_skip_segments preenchidos
- profile.yaml contém nome do projeto
"""

from pathlib import Path

import yaml


def _create_project(tmp_path: Path) -> Path:
    """Cria estrutura mínima de projeto Django para o init."""
    project = tmp_path / 'meu-projeto'
    project.mkdir()
    (project / 'manage.py').write_text('#!/usr/bin/env python\nimport os\nos.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"\n')
    settings_dir = project / 'config'
    settings_dir.mkdir()
    (settings_dir / '__init__.py').write_text('')
    (settings_dir / 'settings.py').write_text('INSTALLED_APPS = ["django.contrib.admin"]\n')
    return project


def _run_init(project: Path) -> Path:
    """Executa _generate_default_artifacts e retorna iac_dir."""
    from iac.cli import _generate_default_artifacts

    iac_dir = project / '.iac'
    iac_dir.mkdir(exist_ok=True)
    result = {'framework': 'Django', 'summary': 'test'}
    _generate_default_artifacts(iac_dir, result)
    return iac_dir


# ---------------------------------------------------------------------------
# .env
# ---------------------------------------------------------------------------


def test_env_gerado(tmp_path):
    project = _create_project(tmp_path)
    iac_dir = _run_init(project)
    env_file = iac_dir / '.env'
    assert env_file.exists()
    content = env_file.read_text()
    assert 'GITLAB_TOKEN' in content
    assert 'IAC_LLM_BACKEND' in content


def test_env_nao_sobrescreve(tmp_path):
    project = _create_project(tmp_path)
    iac_dir = project / '.iac'
    iac_dir.mkdir()
    env_file = iac_dir / '.env'
    env_file.write_text('MINHA_VAR=123\n')
    _run_init(project)
    assert 'MINHA_VAR=123' in env_file.read_text()


# ---------------------------------------------------------------------------
# profile.yaml
# ---------------------------------------------------------------------------


def test_profile_gerado(tmp_path):
    project = _create_project(tmp_path)
    iac_dir = _run_init(project)
    profile_file = iac_dir / 'profile.yaml'
    assert profile_file.exists()


def test_profile_tem_nome_do_projeto(tmp_path):
    project = _create_project(tmp_path)
    iac_dir = _run_init(project)
    content = (iac_dir / 'profile.yaml').read_text()
    assert 'meu-projeto' in content


def test_profile_tem_framework(tmp_path):
    project = _create_project(tmp_path)
    iac_dir = _run_init(project)
    content = (iac_dir / 'profile.yaml').read_text()
    assert 'Django' in content


def test_profile_taxonomy_vazia(tmp_path):
    """O profile gerado NÃO deve ter taxonomy preenchida — usa defaults do IAC."""
    project = _create_project(tmp_path)
    iac_dir = _run_init(project)
    profile = yaml.safe_load((iac_dir / 'profile.yaml').read_text())
    taxonomy = profile.get('taxonomy', {})
    assert taxonomy == {} or taxonomy is None


def test_profile_url_skip_segments_vazio(tmp_path):
    """O profile gerado NÃO deve ter url_skip_segments preenchidos."""
    project = _create_project(tmp_path)
    iac_dir = _run_init(project)
    profile = yaml.safe_load((iac_dir / 'profile.yaml').read_text())
    segments = profile.get('url_skip_segments', [])
    assert segments == [] or segments is None


def test_profile_rules_vazio(tmp_path):
    """O profile gerado NÃO deve ter rules preenchidas."""
    project = _create_project(tmp_path)
    iac_dir = _run_init(project)
    profile = yaml.safe_load((iac_dir / 'profile.yaml').read_text())
    rules = profile.get('rules', [])
    assert rules == [] or rules is None


def test_profile_issue_patterns_vazio(tmp_path):
    """O profile gerado NÃO deve ter issue_patterns preenchidos."""
    project = _create_project(tmp_path)
    iac_dir = _run_init(project)
    profile = yaml.safe_load((iac_dir / 'profile.yaml').read_text())
    patterns = profile.get('issue_patterns', {})
    assert patterns == {} or patterns is None


def test_profile_app_aliases_vazio(tmp_path):
    """O profile gerado NÃO deve ter app_aliases preenchidos."""
    project = _create_project(tmp_path)
    iac_dir = _run_init(project)
    profile = yaml.safe_load((iac_dir / 'profile.yaml').read_text())
    aliases = profile.get('app_aliases', {})
    assert aliases == {} or aliases is None


def test_profile_nao_sobrescreve(tmp_path):
    """Se profile já existe, init NÃO sobrescreve."""
    project = _create_project(tmp_path)
    iac_dir = project / '.iac'
    iac_dir.mkdir()
    profile_file = iac_dir / 'profile.yaml'
    profile_file.write_text('name: customizado\n')
    _run_init(project)
    assert 'customizado' in profile_file.read_text()


def test_profile_tem_comentarios_orientativos(tmp_path):
    """O profile gerado deve ter comentários explicando cada seção."""
    project = _create_project(tmp_path)
    iac_dir = _run_init(project)
    content = (iac_dir / 'profile.yaml').read_text()
    assert '# Exemplo:' in content
    assert 'issue_patterns' in content
    assert 'app_aliases' in content
    assert 'taxonomy' in content
    assert 'rules' in content


# ---------------------------------------------------------------------------
# logs/
# ---------------------------------------------------------------------------


def test_logs_dir_criado(tmp_path):
    project = _create_project(tmp_path)
    iac_dir = _run_init(project)
    assert (iac_dir / 'logs').is_dir()


# ---------------------------------------------------------------------------
# End-to-end: iac init completo (inspect_project + artifacts)
# ---------------------------------------------------------------------------


def _create_django_project_with_apps(tmp_path: Path) -> Path:
    """Cria projeto Django com 2 apps para teste end-to-end."""
    project = tmp_path / 'meu-erp'
    project.mkdir()
    (project / 'manage.py').write_text(
        '#!/usr/bin/env python\nimport os\n'
        'os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"\n'
    )
    settings_dir = project / 'config'
    settings_dir.mkdir()
    (settings_dir / '__init__.py').write_text('')
    (settings_dir / 'settings.py').write_text(
        'INSTALLED_APPS = [\n'
        '    "django.contrib.admin",\n'
        '    "loja",\n'
        '    "estoque",\n'
        ']\n'
    )

    # App loja
    loja = project / 'loja'
    loja.mkdir()
    (loja / '__init__.py').write_text('')
    (loja / 'views.py').write_text(
        'from django.http import HttpResponse\n\n'
        'def listar_produtos(request):\n'
        '    return HttpResponse("ok")\n'
    )
    (loja / 'models.py').write_text(
        'from django.db import models\n\n'
        'class Produto(models.Model):\n'
        '    nome = models.CharField(max_length=100)\n'
        '    preco = models.DecimalField(max_digits=10, decimal_places=2)\n'
    )
    (loja / 'urls.py').write_text(
        'from django.urls import path\nfrom . import views\n\n'
        'urlpatterns = [\n'
        '    path("produtos/", views.listar_produtos),\n'
        ']\n'
    )

    # App estoque
    estoque = project / 'estoque'
    estoque.mkdir()
    (estoque / '__init__.py').write_text('')
    (estoque / 'views.py').write_text(
        'from django.http import HttpResponse\n\n'
        'def verificar_estoque(request):\n'
        '    return HttpResponse("ok")\n'
    )
    (estoque / 'models.py').write_text(
        'from django.db import models\n\n'
        'class Item(models.Model):\n'
        '    quantidade = models.IntegerField()\n'
    )

    return project


def _run_full_init(project: Path) -> Path:
    """Executa inspect_project + _generate_default_artifacts (init completo)."""
    from iac.cli import _generate_default_artifacts
    from iac.inspector import inspect_project

    result = inspect_project(project, force=True)
    iac_dir = project / '.iac'
    _generate_default_artifacts(iac_dir, result)
    return iac_dir


def test_e2e_project_json(tmp_path):
    project = _create_django_project_with_apps(tmp_path)
    iac_dir = _run_full_init(project)
    assert (iac_dir / 'project.json').exists()


def test_e2e_structure_json(tmp_path):
    project = _create_django_project_with_apps(tmp_path)
    iac_dir = _run_full_init(project)
    assert (iac_dir / 'structure.json').exists()
    import json
    structure = json.loads((iac_dir / 'structure.json').read_text())
    assert 'apps' in structure
    assert 'loja' in structure['apps']
    assert 'estoque' in structure['apps']


def test_e2e_graph_json(tmp_path):
    project = _create_django_project_with_apps(tmp_path)
    iac_dir = _run_full_init(project)
    assert (iac_dir / 'graph.json').exists()
    import json
    graph = json.loads((iac_dir / 'graph.json').read_text())
    assert 'edges' in graph


def test_e2e_env(tmp_path):
    project = _create_django_project_with_apps(tmp_path)
    iac_dir = _run_full_init(project)
    env_file = iac_dir / '.env'
    assert env_file.exists()
    content = env_file.read_text()
    assert 'GITLAB_TOKEN' in content
    assert 'GROQ_API_KEY' in content
    assert 'DEEPSEEK_API_KEY' in content
    assert 'GEMINI_API_KEY' in content
    assert 'IAC_LLM_BACKEND' in content
    assert 'IAC_LLM_RATE_DELAY' in content
    assert 'IAC_ANALYZE_MODE' in content


def test_e2e_profile_yaml(tmp_path):
    project = _create_django_project_with_apps(tmp_path)
    iac_dir = _run_full_init(project)
    profile_file = iac_dir / 'profile.yaml'
    assert profile_file.exists()
    content = profile_file.read_text()
    assert 'meu-erp' in content
    # Framework detectado pode ser Django ou Python (depende do ambiente)
    assert 'system_description' in content
    profile = yaml.safe_load(content)
    assert profile['name'] == 'meu-erp'
    assert profile.get('taxonomy', {}) == {} or profile.get('taxonomy') is None
    assert profile.get('rules', []) == [] or profile.get('rules') is None
    assert profile.get('app_aliases', {}) == {} or profile.get('app_aliases') is None


def test_e2e_logs_dir(tmp_path):
    project = _create_django_project_with_apps(tmp_path)
    iac_dir = _run_full_init(project)
    assert (iac_dir / 'logs').is_dir()


def test_e2e_diagrams_overview(tmp_path):
    project = _create_django_project_with_apps(tmp_path)
    iac_dir = _run_full_init(project)
    assert (iac_dir / 'diagrams' / 'overview.html').exists()


def test_e2e_diagrams_per_app(tmp_path):
    project = _create_django_project_with_apps(tmp_path)
    iac_dir = _run_full_init(project)
    diagrams_dir = iac_dir / 'diagrams'
    assert (diagrams_dir / 'loja.html').exists()
    assert (diagrams_dir / 'estoque.html').exists()


def test_e2e_todos_artefatos_presentes(tmp_path):
    """Validação completa: todos os artefatos do init existem."""
    project = _create_django_project_with_apps(tmp_path)
    iac_dir = _run_full_init(project)

    assert (iac_dir / 'project.json').exists(), 'project.json ausente'
    assert (iac_dir / 'structure.json').exists(), 'structure.json ausente'
    assert (iac_dir / 'graph.json').exists(), 'graph.json ausente'
    assert (iac_dir / '.env').exists(), '.env ausente'
    assert (iac_dir / 'profile.yaml').exists(), 'profile.yaml ausente'
    assert (iac_dir / 'logs').is_dir(), 'logs/ ausente'
    assert (iac_dir / 'diagrams' / 'overview.html').exists(), 'diagrams/overview.html ausente'
