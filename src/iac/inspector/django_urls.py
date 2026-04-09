"""Extração de URLs e admin Django via parsing de arquivos.

Parseia urls.py e admin.py de cada app Django, extraindo patterns
de URL, classes ModelAdmin registradas e gerando os URLs automáticos
do Django admin — tudo sem executar o Django.
"""

from __future__ import annotations

import ast
import logging
import re
from pathlib import Path

from .django_parser import _call_name, _fix_legacy_syntax

logger = logging.getLogger(__name__)


def _parse_urls(app_dir: Path) -> list[dict]:
    """Extrai padrões de URL do urls.py do app.

    Captura path() e re_path()/url() com regex.
    """
    urls_file = app_dir / 'urls.py'
    if not urls_file.exists():
        return []

    content = urls_file.read_text(encoding='utf-8', errors='replace')
    urls: list[dict] = []

    # path('pattern/', view, ...)
    for match in re.finditer(r"path\(\s*['\"]([^'\"]*)['\"],\s*(\w[\w.]*)", content):
        pattern = match.group(1)
        view = match.group(2)
        urls.append({'pattern': f'/{pattern}', 'view': view})

    # re_path(r'pattern/', view, ...) e url(r'pattern/', view, ...)
    for match in re.finditer(r"(?:re_path|url)\(\s*r?['\"]([^'\"]*)['\"],\s*(\w[\w.]*)", content):
        pattern = match.group(1)
        view = match.group(2)
        # Converter regex para formato legível: (?P<name>...) → <name>
        pattern = re.sub(r'\(\?P<(\w+)>[^)]+\)', r'<\1>', pattern)
        pattern = pattern.lstrip('^').rstrip('$')
        if not pattern.startswith('/'):
            pattern = f'/{pattern}'
        urls.append({'pattern': pattern, 'view': view})

    return urls[:100]  # limitar a 100 URLs


def _parse_admin(app_dir: Path) -> dict[str, dict]:
    """Extrai classes ModelAdmin e models registrados do admin.py.

    Captura:
        - @admin.register(Model) ou admin.site.register(Model, ModelAdmin)
        - Atributos: list_display, list_filter, search_fields, inlines, form
    """
    admin_file = app_dir / 'admin.py'
    if not admin_file.exists():
        return {}

    try:
        source = admin_file.read_text(encoding='utf-8', errors='replace')
        try:
            tree = ast.parse(source, filename=str(admin_file))
        except SyntaxError:
            source = _fix_legacy_syntax(source)
            tree = ast.parse(source, filename=str(admin_file))
    except SyntaxError:
        return {}

    result: dict[str, dict] = {}
    relative = str(admin_file.relative_to(app_dir.parent))

    # 1. Parsear classes (ModelAdmin) com decorador @admin.register(...)
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            entry: dict = {
                'file': relative,
                'line': node.lineno,
                'type': 'class',
                'models': [],
                'form': None,
                'inlines': [],
            }

            # Extrair models do decorador @admin.register(Model1, Model2)
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Call):
                    dec_name = _call_name(decorator)
                    if dec_name and 'register' in dec_name:
                        for arg in decorator.args:
                            if isinstance(arg, ast.Name):
                                entry['models'].append(arg.id)

            # Extrair atributos: form, inlines, list_display, etc.
            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.Assign):
                    for target in child.targets:
                        if not isinstance(target, ast.Name):
                            continue
                        if target.id == 'form' and isinstance(child.value, ast.Name):
                            entry['form'] = child.value.id
                        elif target.id == 'inlines' and isinstance(child.value, ast.List | ast.Tuple):
                            for elt in child.value.elts:
                                if isinstance(elt, ast.Name):
                                    entry['inlines'].append(elt.id)

            if entry['models'] or entry['form']:
                result[node.name] = entry

    # 2. Capturar admin.site.register(Model, Admin) fora de classes
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            call_name = _call_name(node.value)
            if call_name and 'register' in call_name:
                args = node.value.args
                if args and isinstance(args[0], ast.Name):
                    model_name = args[0].id
                    admin_name = args[1].id if len(args) > 1 and isinstance(args[1], ast.Name) else None
                    if admin_name and admin_name in result:
                        if model_name not in result[admin_name]['models']:
                            result[admin_name]['models'].append(model_name)
                    elif admin_name:
                        result[admin_name] = {
                            'file': relative,
                            'line': node.lineno,
                            'type': 'class',
                            'models': [model_name],
                            'form': None,
                            'inlines': [],
                        }
                    else:
                        # register(Model) sem admin class
                        key = f'{model_name}Admin_auto'
                        result[key] = {
                            'file': relative,
                            'line': node.lineno,
                            'type': 'auto',
                            'models': [model_name],
                            'form': None,
                            'inlines': [],
                        }

    return result


def _enrich_admin_urls(app_name: str, app_data: dict) -> None:
    """Gera URL patterns do Django admin para models registrados.

    Django admin cria automaticamente:
        /admin/{app_label}/{model_name}/          (changelist)
        /admin/{app_label}/{model_name}/<int:pk>/  (change)
        /admin/{app_label}/{model_name}/add/       (add)
    """
    admin_classes = app_data.get('admin', {})
    models = app_data.get('models', {})

    registered_models = set()
    for admin_data in admin_classes.values():
        for model_ref in admin_data.get('models', []):
            if model_ref in models:
                registered_models.add(model_ref)

    for model_name in registered_models:
        model_lower = model_name.lower()
        app_data['urls'].append({
            'pattern': f'/admin/{app_name}/{model_lower}/',
            'view': f'admin.{model_name}',
        })


def _find_templates(app_dir: Path) -> list[str]:
    """Lista templates HTML do app."""
    templates_dir = app_dir / 'templates'
    if not templates_dir.exists():
        return []

    templates: list[str] = []
    for html_file in sorted(templates_dir.rglob('*.html')):
        relative = str(html_file.relative_to(templates_dir))
        templates.append(relative)

    return templates[:100]  # limitar a 100 templates
