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


def _discover_apps(base_dir: Path, config: dict) -> dict[str, Path]:
    """Descobre os apps Django do projeto.

    Tenta extrair de INSTALLED_APPS no settings, ou faz scan de diretórios
    que contenham views.py, models.py, ou pacotes views/ e models/.
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

    # Fallback: scan de diretórios com views(.py|/) ou models(.py|/)
    if not apps:
        for child in sorted(base_dir.iterdir()):
            if (
                child.is_dir()
                and child.name not in EXCLUDE_DIRS
                and not child.name.startswith('.')
                and _has_django_module(child)
            ):
                apps[child.name] = child

    logger.info(f'Apps descobertos: {len(apps)}')
    return apps


def _has_django_module(app_dir: Path) -> bool:
    """Verifica se o diretório contém views ou models (arquivo ou pacote)."""
    return (
        (app_dir / 'views.py').exists()
        or (app_dir / 'models.py').exists()
        or (app_dir / 'views').is_dir()
        or (app_dir / 'models').is_dir()
    )


def _collect_settings_content(settings_path: Path) -> str:
    """Lê o settings principal e arquivos importados via 'from .X import *'."""
    content = settings_path.read_text(encoding='utf-8', errors='replace')
    settings_dir = settings_path.parent

    # Seguir imports relativos: from .settings_base import *
    for match in re.finditer(r'from\s+\.(\w+)\s+import\s+\*', content):
        sibling_name = match.group(1) + '.py'
        sibling = settings_dir / sibling_name
        if sibling.exists():
            logger.debug(f'Seguindo import: {sibling}')
            content += '\n' + sibling.read_text(encoding='utf-8', errors='replace')

    return content


def _extract_block(content: str, start: int, open_char: str) -> str | None:
    """Extrai o conteúdo entre delimitadores balanceados a partir de start."""
    close_char = ']' if open_char == '[' else ')'
    depth = 0
    for i in range(start, len(content)):
        if content[i] == open_char:
            depth += 1
        elif content[i] == close_char:
            depth -= 1
            if depth == 0:
                return content[start + 1 : i]
    return None


def _collect_apps_from_block(block: str) -> list[str]:
    """Extrai nomes de apps de um bloco de texto com strings quoted."""
    apps: list[str] = []
    skip_prefixes = ('django.', 'rest_framework', 'corsheaders', 'debug_toolbar')
    for match in re.finditer(r"['\"]([a-zA-Z_][\w.]*)['\"]", block):
        app = match.group(1)
        if not app.startswith(skip_prefixes) and app not in apps:
            apps.append(app)
    return apps


def _extract_installed_apps(settings_path: Path) -> list[str]:
    """Extrai nomes de apps do arquivo de settings (sem executar Python).

    Suporta listas [] e tuplas (), segue imports relativos (from .X import *),
    e resolve indireções simples (VAR = (...); INSTALLED_APPS = VAR + ...).
    """
    content = _collect_settings_content(settings_path)
    apps: list[str] = []

    # Buscar atribuições a variáveis com 'APP' no nome: VAR = (...) ou VAR = [...]
    for match in re.finditer(r'(\w*APP\w*)\s*=\s*([\[\(])', content):
        open_char = match.group(2)
        block = _extract_block(content, match.end() - 1, open_char)
        if block:
            apps.extend(_collect_apps_from_block(block))

    # Buscar += e .extend() com ambos delimitadores
    for match in re.finditer(r'\w*APP\w*\s*(?:\+=|\.extend\()\s*([\[\(])', content):
        open_char = match.group(1)
        block = _extract_block(content, match.end() - 1, open_char)
        if block:
            apps.extend(_collect_apps_from_block(block))

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


def _fix_legacy_syntax(source: str) -> str:
    """Corrige sintaxes Python 2 que impedem o ast.parse no Python 3.

    Transformações:
        except TypeError, ValueError:             →  except (TypeError, ValueError):
        except A, B, C.DoesNotExist:              →  except (A, B, C.DoesNotExist):
        except A.DoesNotExist, KeyError:          →  except (A.DoesNotExist, KeyError):
    """

    def _fix_except(match: re.Match) -> str:
        types_str = match.group(1)
        # Separar por vírgula, preservando nomes qualificados (A.B)
        types = [t.strip() for t in types_str.split(',')]
        return f'except ({", ".join(types)}):'

    return re.sub(
        r'except\s+([\w.]+(?:\s*,\s*[\w.]+)+)\s*:',
        _fix_except,
        source,
    )


def _parse_python_file(file_path: Path, app_dir: Path) -> dict[str, dict]:
    """Parseia um arquivo Python extraindo funções e classes de topo."""
    result: dict[str, dict] = {}
    relative = str(file_path.relative_to(app_dir.parent))

    try:
        source = file_path.read_text(encoding='utf-8', errors='replace')
        try:
            tree = ast.parse(source, filename=str(file_path))
        except SyntaxError:
            source = _fix_legacy_syntax(source)
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
            # Extrair referências FK/M2M (para models)
            fk_refs = _extract_fk_references(node)
            if fk_refs:
                entry['fk_references'] = fk_refs
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


def _extract_fk_references(node: ast.ClassDef) -> list[str]:
    """Extrai models referenciados via ForeignKey, OneToOne e ManyToMany."""
    refs: list[str] = []
    fk_types = ('ForeignKey', 'ForeignKeyPlus', 'OneToOneField', 'OneToOneFieldPlus', 'ManyToManyField', 'ManyToManyFieldPlus')
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.Assign) and isinstance(child.value, ast.Call):
            call_name = _call_name(child.value)
            if call_name and any(fk in call_name for fk in fk_types):
                # Primeiro argumento posicional é o model referenciado
                if child.value.args:
                    arg = child.value.args[0]
                    if isinstance(arg, ast.Name) and arg.id not in refs:
                        refs.append(arg.id)
                    elif isinstance(arg, ast.Constant) and isinstance(arg.value, str) and arg.value not in refs:
                        refs.append(arg.value)
    return refs


def _extract_methods(node: ast.ClassDef) -> dict[str, dict]:
    """Extrai métodos de uma classe com número da linha."""
    methods: dict[str, dict] = {}
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef) and (
            not child.name.startswith('_') or child.name in ('__str__', '__repr__')
        ):
            methods[child.name] = {'line': child.lineno}
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


# ---------------------------------------------------------------------------
# Nível 4: Propagar renders via {% include %} e {% extends %}
# ---------------------------------------------------------------------------


def _enrich_renders_from_includes(base_dir: Path, apps: dict[str, Path], structure: dict) -> None:
    """Se uma view renderiza template A e A faz include de B, associa B à view também.

    Isso captura templates parciais (abas, includes, partials) que são
    usados indiretamente por views via include/extends.
    """
    include_pattern = re.compile(r'{%\s*(?:include|extends)\s+["\']([^"\']+)["\']')

    # Construir mapa: template → lista de templates que ele inclui
    template_includes: dict[str, list[str]] = {}

    for _app_name, app_dir in apps.items():
        templates_dir = app_dir / 'templates'
        if not templates_dir.exists():
            continue

        for html_file in templates_dir.rglob('*.html'):
            try:
                content = html_file.read_text(encoding='utf-8', errors='replace')
            except OSError:
                continue

            template_name = str(html_file.relative_to(templates_dir))
            includes = []
            for match in include_pattern.finditer(content):
                includes.append(match.group(1))
            if includes:
                template_includes[template_name] = includes

    # Construir set global de todos os templates (para matching flexível)
    all_templates_set: set[str] = set()
    for app_data in structure.get('apps', {}).values():
        all_templates_set.update(app_data.get('templates', []))

    # Para cada view que já tem renders, propagar para os includes
    for _app_name, app_data in structure.get('apps', {}).items():
        views = app_data.get('views', {})
        existing_templates = set(app_data.get('templates', []))

        for _view_name, view_data in views.items():
            current_renders = list(view_data.get('renders', []))
            if not current_renders:
                continue

            # BFS: propagar includes dos renders existentes
            to_visit = list(current_renders)
            visited = set(current_renders)
            while to_visit:
                template = to_visit.pop(0)
                for included in template_includes.get(template, []):
                    if included in visited:
                        continue
                    # Matching flexível: o include pode ser path completo ou relativo
                    resolved = _resolve_template_ref(included, existing_templates, all_templates_set)
                    if resolved:
                        current_renders.append(resolved)
                        visited.add(included)
                        visited.add(resolved)
                        to_visit.append(resolved)

            new_count = len(current_renders) - len(view_data.get('renders', []))
            if new_count > 0:
                view_data['renders'] = current_renders
                logger.debug(f'Include propagation: +{new_count} templates for view')


def _resolve_template_ref(ref: str, app_templates: set[str], all_templates: set[str]) -> str | None:
    """Resolve uma referência de template para um template existente.

    Trata variações de path:
      'abas/anexos.html'                          → direto
      'erros/templates/abas/anexos.html'           → strip 'app/templates/'
      'documento_eletronico/cabecalho_include.html' → busca em todos os apps
      'relatorio_pdf.html'                         → busca global
    """
    # Match direto no app
    if ref in app_templates:
        return ref

    # Strip 'app/templates/' prefix
    if '/templates/' in ref:
        stripped = ref.split('/templates/', 1)[1]
        if stripped in app_templates:
            return stripped

    # Match no basename
    basename = ref.rsplit('/', 1)[-1]
    for t in app_templates:
        if t == basename or t.endswith('/' + basename):
            return t

    # Match global (outros apps)
    if ref in all_templates:
        return ref
    for t in all_templates:
        if t == basename or t.endswith('/' + basename):
            return t

    return None


# ---------------------------------------------------------------------------
# Nível 5: Buscar referências .html em .py via regex
# ---------------------------------------------------------------------------


def _enrich_renders_from_py_regex(base_dir: Path, apps: dict[str, Path], structure: dict) -> None:
    """Busca strings .html em arquivos .py que o AST não capturou.

    Captura: f-strings, concatenações, variáveis, chamadas dinâmicas.
    Ex: f'{app}/chamado.html', template = 'chamado.html', etc.
    """
    html_pattern = re.compile(r'["\'](\w[\w/]*\.html)["\']')

    for app_name, app_dir in apps.items():
        app_data = structure.get('apps', {}).get(app_name, {})
        views = app_data.get('views', {})
        existing_templates = set(app_data.get('templates', []))
        if not existing_templates:
            continue

        # Coletar todas as referências .html dos .py do app
        py_templates: dict[str, set[str]] = {}  # arquivo → set de templates referenciados
        for py_file in sorted(app_dir.rglob('*.py')):
            if 'migration' in str(py_file) or '__pycache__' in str(py_file):
                continue
            try:
                content = py_file.read_text(encoding='utf-8', errors='replace')
            except OSError:
                continue
            for match in html_pattern.finditer(content):
                template_ref = match.group(1)
                # Matching flexível: path completo, com /templates/, ou basename
                resolved = _resolve_template_ref(template_ref, existing_templates, existing_templates)
                if resolved:
                    relative = str(py_file.relative_to(app_dir.parent))
                    if relative not in py_templates:
                        py_templates[relative] = set()
                    py_templates[relative].add(resolved)

        # Associar templates encontrados às views do mesmo arquivo
        for _view_name, view_data in views.items():
            view_file = view_data.get('file', '')
            if view_file in py_templates:
                renders = view_data.get('renders', [])
                for t in py_templates[view_file]:
                    if t not in renders:
                        renders.append(t)
                if renders:
                    view_data['renders'] = renders
