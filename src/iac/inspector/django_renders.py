"""Enriquecimento de renders de templates em projetos Django.

Implementa quatro níveis de inferência de quais templates cada view
renderiza, indo de convenções Django explícitas até varredura regex
em arquivos Python — sem executar o framework.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


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
