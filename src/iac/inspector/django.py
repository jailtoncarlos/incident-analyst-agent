"""Parser específico para projetos Django — fachada pública.

Extrai: apps instalados, views, models, forms, URLs e templates.
Tudo via AST — sem executar o Django nem importar módulos.

Os detalhes de implementação estão distribuídos em:
  - django_discovery.py  → descoberta de apps e INSTALLED_APPS
  - django_parser.py     → parsing AST de módulos Python
  - django_urls.py       → parsing de urls.py e admin.py
  - django_renders.py    → enriquecimento de renders de templates
"""

from __future__ import annotations

import logging
from pathlib import Path

from .django_discovery import (
    EXCLUDE_DIRS,
    _collect_apps_from_block,
    _collect_settings_content,
    _discover_apps,
    _extract_block,
    _extract_installed_apps,
    _has_django_module,
)
from .django_parser import (
    _call_name,
    _collect_template_string,
    _extract_calls,
    _extract_class_constants,
    _extract_class_template_name,
    _extract_fk_references,
    _extract_meta_model,
    _extract_methods,
    _extract_model_fields,
    _extract_renders,
    _fix_legacy_syntax,
    _parse_module,
    _parse_python_file,
)
from .django_renders import (
    _enrich_renders_by_convention,
    _enrich_renders_from_includes,
    _enrich_renders_from_py_regex,
    _enrich_renders_from_templates,
    _resolve_template_ref,
)
from .django_urls import (
    _enrich_admin_urls,
    _find_templates,
    _parse_admin,
    _parse_urls,
)

__all__ = [
    'build_django_structure',
    # discovery
    'EXCLUDE_DIRS',
    '_discover_apps',
    '_has_django_module',
    '_collect_settings_content',
    '_extract_block',
    '_collect_apps_from_block',
    '_extract_installed_apps',
    # parser
    '_parse_module',
    '_fix_legacy_syntax',
    '_parse_python_file',
    '_extract_calls',
    '_call_name',
    '_extract_renders',
    '_collect_template_string',
    '_extract_model_fields',
    '_extract_fk_references',
    '_extract_class_constants',
    '_extract_methods',
    '_extract_meta_model',
    '_extract_class_template_name',
    # urls
    '_parse_urls',
    '_parse_admin',
    '_enrich_admin_urls',
    '_find_templates',
    # renders
    '_enrich_renders_by_convention',
    '_enrich_renders_from_templates',
    '_enrich_renders_from_includes',
    '_resolve_template_ref',
    '_enrich_renders_from_py_regex',
]

logger = logging.getLogger(__name__)


def build_django_structure(base_dir: Path, config: dict) -> dict:
    """Constrói o mapa estrutural de um projeto Django.

    Args:
        base_dir: Diretório raiz do projeto Django.
        config: Dict de configuração retornado por detect_framework().

    Returns:
        Dict com chave 'apps' mapeando cada app aos seus views, models,
        forms, admin, urls e templates.
    """
    apps = _discover_apps(base_dir, config)
    structure: dict[str, dict] = {}

    for app_name, app_dir in apps.items():
        logger.debug(f'Inspecionando app: {app_name}')
        app_data: dict = {
            'views': {},
            'models': {},
            'forms': {},
            'urls': [],
            'templates': [],
        }

        app_data['views'] = _parse_module(app_dir, 'views')
        app_data['models'] = _parse_module(app_dir, 'models')
        app_data['forms'] = _parse_module(app_dir, 'forms')
        app_data['admin'] = _parse_admin(app_dir)
        app_data['urls'] = _parse_urls(app_dir)
        _enrich_admin_urls(app_name, app_data)
        app_data['templates'] = _find_templates(app_dir)

        # Nível 2: inferir renders por convenção Django (app/template.html)
        _enrich_renders_by_convention(app_name, app_data)

        # Só incluir apps que têm pelo menos um componente
        if any(app_data[k] for k in app_data):
            structure[app_name] = app_data

    # Wrapper para os enrich functions que esperam {'apps': {...}}
    wrapped = {'apps': structure}

    # Nível 3: buscar referências inversas em templates ({% url 'view_name' %})
    _enrich_renders_from_templates(base_dir, apps, wrapped)

    # Nível 4: propagar renders via {% include %} e {% extends %}
    _enrich_renders_from_includes(base_dir, apps, wrapped)

    # Nível 5: buscar referências .html em .py via regex (f-strings, concatenações)
    _enrich_renders_from_py_regex(base_dir, apps, wrapped)

    return wrapped
