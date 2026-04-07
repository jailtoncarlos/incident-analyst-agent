"""Parser específico para projetos Django.

Extrai: apps instalados, views, models, forms, URLs e templates.
Tudo via AST — sem executar o Django nem importar módulos.
"""

from __future__ import annotations

import ast
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# Diretórios a ignorar na inspeção
EXCLUDE_DIRS = {
    'migrations',
    'static',
    'templates',
    'locale',
    '.venv',
    'venv',
    'node_modules',
    '__pycache__',
    '.git',
    '.iac',
    '.tox',
    '.mypy_cache',
    '.pytest_cache',
}


def build_django_structure(base_dir: Path, config: dict) -> dict:
    """Constrói o mapa estrutural de um projeto Django."""
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
        app_data['urls'] = _parse_urls(app_dir)
        app_data['templates'] = _find_templates(app_dir)

        # Nível 2: inferir renders por convenção Django (app/template.html)
        _enrich_renders_by_convention(app_name, app_data)

        # Só incluir apps que têm pelo menos um componente
        if any(app_data[k] for k in app_data):
            structure[app_name] = app_data

    # Nível 3: buscar referências inversas em templates ({% url 'view_name' %})
    _enrich_renders_from_templates(base_dir, apps, structure)

    return {'apps': structure}


def _discover_apps(base_dir: Path, config: dict) -> dict[str, Path]:
    """Descobre os apps Django do projeto.

    Tenta extrair de INSTALLED_APPS no settings, ou faz scan de diretórios
    que contenham views.py ou models.py.
    """
    apps: dict[str, Path] = {}

    # Tentar extrair INSTALLED_APPS do settings
    settings_module = config.get('settings_module', '')
    if settings_module:
        settings_path = base_dir / settings_module.replace('.', '/') / '__init__.py'
        if not settings_path.exists():
            settings_path = base_dir / (settings_module.replace('.', '/') + '.py')
        if settings_path.exists():
            installed = _extract_installed_apps(settings_path)
            for app_label in installed:
                app_dir = base_dir / app_label.replace('.', '/')
                if app_dir.is_dir():
                    apps[app_label] = app_dir

    # Fallback: scan de diretórios com views.py ou models.py
    if not apps:
        for child in sorted(base_dir.iterdir()):
            if (
                child.is_dir()
                and child.name not in EXCLUDE_DIRS
                and not child.name.startswith('.')
                and ((child / 'views.py').exists() or (child / 'models.py').exists())
            ):
                apps[child.name] = child

    logger.info(f'Apps descobertos: {len(apps)}')
    return apps


def _extract_installed_apps(settings_path: Path) -> list[str]:
    """Extrai nomes de apps do arquivo de settings via regex (sem executar Python)."""
    content = settings_path.read_text(encoding='utf-8', errors='replace')

    # Buscar INSTALLED_APPS ou variantes (INSTALLED_APPS_SUAP, etc.)
    apps: list[str] = []
    pattern = r'INSTALLED_APPS\w*\s*=\s*\[([^\]]+)\]'
    for match in re.finditer(pattern, content, re.DOTALL):
        block = match.group(1)
        for app_match in re.finditer(r"['\"]([a-zA-Z_][\w.]*)['\"]", block):
            app = app_match.group(1)
            # Ignorar apps do Django e third-party comuns
            if not app.startswith(('django.', 'rest_framework', 'corsheaders', 'debug_toolbar')):
                apps.append(app)

    # Buscar INSTALLED_APPS += [...] ou .extend([...])
    pattern_extend = r'INSTALLED_APPS\w*\s*(?:\+=|\.extend\()\s*\[([^\]]+)\]'
    for match in re.finditer(pattern_extend, content, re.DOTALL):
        block = match.group(1)
        for app_match in re.finditer(r"['\"]([a-zA-Z_][\w.]*)['\"]", block):
            app = app_match.group(1)
            if not app.startswith(('django.', 'rest_framework', 'corsheaders', 'debug_toolbar')):
                apps.append(app)

    return list(dict.fromkeys(apps))  # deduplica mantendo ordem


def _parse_module(app_dir: Path, module_name: str) -> dict[str, dict]:
    """Parseia um módulo (views, models ou forms) extraindo funções e classes."""
    result: dict[str, dict] = {}

    # Arquivo único: app/views.py
    single_file = app_dir / f'{module_name}.py'
    if single_file.exists():
        result.update(_parse_python_file(single_file, app_dir))

    # Pacote: app/views/__init__.py + submodules
    package_dir = app_dir / module_name
    if package_dir.is_dir():
        for py_file in sorted(package_dir.glob('*.py')):
            if py_file.name == '__init__.py':
                continue
            result.update(_parse_python_file(py_file, app_dir))

    return result


def _parse_python_file(file_path: Path, app_dir: Path) -> dict[str, dict]:
    """Parseia um arquivo Python extraindo funções e classes de topo."""
    result: dict[str, dict] = {}
    relative = str(file_path.relative_to(app_dir.parent))

    try:
        source = file_path.read_text(encoding='utf-8', errors='replace')
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError:
        logger.debug(f'SyntaxError ao parsear {file_path}, pulando.')
        return result

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            entry = {
                'file': relative,
                'line': node.lineno,
                'type': 'function',
            }
            # Extrair chamadas dentro da função
            calls = _extract_calls(node)
            if calls:
                entry['calls'] = calls
            # Extrair renders (template)
            renders = _extract_renders(node)
            if renders:
                entry['renders'] = renders
            result[node.name] = entry

        elif isinstance(node, ast.ClassDef):
            entry = {
                'file': relative,
                'line': node.lineno,
                'type': 'class',
            }
            # Extrair campos (para models)
            fields = _extract_model_fields(node)
            if fields:
                entry['fields'] = fields
            # Extrair métodos
            methods = _extract_methods(node)
            if methods:
                entry['methods'] = methods
            # Extrair Meta.model (para forms)
            meta_model = _extract_meta_model(node)
            if meta_model:
                entry['meta_model'] = meta_model
            # Nível 1: Extrair template_name de class-based views
            class_template = _extract_class_template_name(node)
            if class_template:
                entry['renders'] = [class_template]
            result[node.name] = entry

    return result


def _extract_calls(node: ast.AST) -> list[str]:
    """Extrai nomes de chamadas de função/método dentro de um nó."""
    calls: list[str] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            name = _call_name(child)
            if name and name not in calls:
                calls.append(name)
    return calls[:20]  # limitar a 20 chamadas mais relevantes


def _call_name(node: ast.Call) -> str | None:
    """Extrai o nome de uma chamada."""
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        # ex: chamado.resolver_chamado() → chamado.resolver_chamado
        parts = []
        current = node.func
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
        parts.reverse()
        return '.'.join(parts)
    return None


def _extract_renders(node: ast.AST) -> list[str]:
    """Extrai nomes de templates passados a render, render_to_string, etc."""
    templates: list[str] = []
    render_funcs = ('render', 'render_to_string', 'TemplateResponse', 'get_template', 'select_template')

    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        name = _call_name(child)
        if not name:
            continue

        # Funções de render: render(request, 'template.html', ...)
        if name in render_funcs:
            for arg in child.args:
                _collect_template_string(arg, templates)
            for kw in child.keywords:
                if kw.arg in ('template_name', 'template'):
                    _collect_template_string(kw.value, templates)

        # Variáveis de template: template_name = 'template.html' ou self.template_name = '...'
        if isinstance(child, ast.Call) and name == 'render':
            continue  # já tratado acima

    # Também buscar atribuições do tipo template = '...' ou template_name = '...'
    for child in ast.walk(node):
        if isinstance(child, ast.Assign):
            for target in child.targets:
                target_name = None
                if isinstance(target, ast.Name):
                    target_name = target.id
                elif isinstance(target, ast.Attribute):
                    target_name = target.attr
                if target_name and 'template' in target_name.lower():
                    _collect_template_string(child.value, templates)

    return templates


def _collect_template_string(node: ast.AST, templates: list[str]) -> None:
    """Coleta string de template de um nó AST."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        value = node.value.strip()
        if ('/' in value or value.endswith('.html')) and value not in templates:
            templates.append(value)


def _extract_model_fields(node: ast.ClassDef) -> list[str]:
    """Extrai nomes de campos de um Model Django."""
    fields: list[str] = []
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.Assign):
            for target in child.targets:
                if isinstance(target, ast.Name) and isinstance(child.value, ast.Call):
                    call_name = _call_name(child.value)
                    if call_name and ('Field' in call_name or 'ForeignKey' in call_name or 'ManyToMany' in call_name):
                        fields.append(target.id)
        elif isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name):
            fields.append(child.target.id)
    return fields


def _extract_methods(node: ast.ClassDef) -> list[str]:
    """Extrai nomes de métodos de uma classe."""
    methods: list[str] = []
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef) and (
            not child.name.startswith('_') or child.name in ('__str__', '__repr__')
        ):
            methods.append(child.name)
    return methods


def _extract_meta_model(node: ast.ClassDef) -> str | None:
    """Extrai o model referenciado em Meta.model de um Form."""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.ClassDef) and child.name == 'Meta':
            for meta_child in ast.iter_child_nodes(child):
                if isinstance(meta_child, ast.Assign):
                    for target in meta_child.targets:
                        if (
                            isinstance(target, ast.Name)
                            and target.id == 'model'
                            and isinstance(meta_child.value, ast.Name)
                        ):
                            return meta_child.value.id
    return None


def _parse_urls(app_dir: Path) -> list[dict]:
    """Extrai padrões de URL do urls.py do app."""
    urls_file = app_dir / 'urls.py'
    if not urls_file.exists():
        return []

    content = urls_file.read_text(encoding='utf-8', errors='replace')
    urls: list[dict] = []

    # Regex para path('pattern/', view, name='name')
    for match in re.finditer(r"path\(\s*['\"]([^'\"]*)['\"],\s*(\w[\w.]*)", content):
        pattern = match.group(1)
        view = match.group(2)
        urls.append({'pattern': f'/{pattern}', 'view': view})

    return urls[:50]  # limitar a 50 URLs


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


# ---------------------------------------------------------------------------
# Nível 1: Extrair template_name de atributo de classe (class-based views)
# ---------------------------------------------------------------------------


def _extract_class_template_name(node: ast.ClassDef) -> str | None:
    """Extrai template_name de atributo de classe (CBV Django)."""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.Assign):
            for target in child.targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id == 'template_name'
                    and isinstance(child.value, ast.Constant)
                    and isinstance(child.value.value, str)
                ):
                    return child.value.value
    return None


# ---------------------------------------------------------------------------
# Nível 2: Inferir renders por convenção Django
# ---------------------------------------------------------------------------


def _enrich_renders_by_convention(app_name: str, app_data: dict) -> None:
    """Infere renders cruzando nomes de views/models com templates existentes.

    Convenções Django:
      - View 'visualizar_chamado' → template 'visualizar_chamado.html'
      - View 'visualizar_chamado' → template 'chamado.html'
      - App 'centralservicos' → templates em 'centralservicos/*.html'
      - Model 'Chamado' → template 'chamado.html' ou 'chamado_list.html'
    """
    existing_templates = set(app_data.get('templates', []))
    if not existing_templates:
        return

    views = app_data.get('views', {})
    for view_name, view_data in views.items():
        if view_data.get('renders'):
            continue  # já tem renders mapeados

        # Candidatos por convenção
        candidates = [
            f'{view_name}.html',
            f'{app_name}/{view_name}.html',
        ]
        # Se o nome da view tem prefixo (listar_, visualizar_, etc.), tentar sem prefixo
        for prefix in ('listar_', 'visualizar_', 'editar_', 'adicionar_', 'cadastrar_', 'detalhe_'):
            if view_name.startswith(prefix):
                base = view_name[len(prefix) :]
                candidates.extend(
                    [
                        f'{base}.html',
                        f'{app_name}/{base}.html',
                    ]
                )

        matched = [t for t in candidates if t in existing_templates]
        if matched:
            view_data['renders'] = matched
            logger.debug(f'Convenção: {app_name}.{view_name} → {matched}')


# ---------------------------------------------------------------------------
# Nível 3: Buscar referências inversas em templates
# ---------------------------------------------------------------------------


def _enrich_renders_from_templates(base_dir: Path, apps: dict[str, Path], structure: dict) -> None:
    """Busca {% url 'view_name' %} nos templates e mapeia template → view.

    Faz o caminho inverso: em vez de "qual template a view usa",
    descobre "quais views o template referencia" via {% url %} tags.
    """
    url_tag_pattern = re.compile(r"\{%\s*url\s+['\"](\w+)['\"]")

    # Construir mapa reverso: url_name → (app_name, view_name)
    url_name_map: dict[str, tuple[str, str]] = {}
    for app_name, app_data in structure.get('apps', {}).items():
        for url_entry in app_data.get('urls', []):
            view_ref = url_entry.get('view', '')
            view_name = view_ref.split('.')[-1] if '.' in view_ref else view_ref
            # Inferir url_name do view_name (convenção Django)
            url_name_map[view_name] = (app_name, view_name)

    # Percorrer templates de cada app
    for app_name, app_dir in apps.items():
        templates_dir = app_dir / 'templates'
        if not templates_dir.exists():
            continue

        app_structure = structure.get('apps', {}).get(app_name, {})
        views = app_structure.get('views', {})

        for html_file in templates_dir.rglob('*.html'):
            try:
                content = html_file.read_text(encoding='utf-8', errors='replace')
            except OSError:
                continue

            template_name = str(html_file.relative_to(templates_dir))

            # Buscar {% url 'view_name' %} no template
            for match in url_tag_pattern.finditer(content):
                url_name = match.group(1)
                if url_name in url_name_map:
                    ref_app, ref_view = url_name_map[url_name]
                    # Se a view referenciada está no mesmo app, associar template
                    if ref_app == app_name and ref_view in views:
                        renders = views[ref_view].get('renders', [])
                        if template_name not in renders:
                            renders.append(template_name)
                            views[ref_view]['renders'] = renders
                            logger.debug(f'Template inverso: {template_name} → {app_name}.{ref_view}')
