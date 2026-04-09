"""Gerador de dados para visualização D3.js."""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path

from iac.config.settings import load_graph, load_structure

logger = logging.getLogger(__name__)


def generate_overview_data(iac_dir: Path) -> dict:
    """Gera dados agregados por app para o overview.

    Args:
        iac_dir: Caminho para o diretório .iac do projeto.

    Returns:
        Dict com 'nodes' (apps) e 'links' (conexões entre apps).
    """
    structure = load_structure(iac_dir)
    graph = load_graph(iac_dir)
    apps = structure.get('apps', {})

    nodes = []
    for app_name, app_data in apps.items():
        views_count = len(app_data.get('views', {}))
        models_count = len(app_data.get('models', {}))
        forms_count = len(app_data.get('forms', {}))
        urls_count = len(app_data.get('urls', []))
        templates_count = len(app_data.get('templates', []))
        total = views_count + models_count + forms_count
        if total == 0:
            continue
        nodes.append(
            {
                'id': app_name,
                'views': views_count,
                'models': models_count,
                'forms': forms_count,
                'urls': urls_count,
                'templates': templates_count,
                'total': total,
            }
        )

    # Agregar arestas entre apps
    inter_app_links: dict[tuple[str, str, str], int] = defaultdict(int)
    for edge in graph.get('edges', []):
        source_app = _extract_app(edge['from'])
        target_app = _extract_app(edge['to'])
        if source_app and target_app and source_app != target_app:
            key = (source_app, target_app, edge['type'])
            inter_app_links[key] += 1

    # Consolidar por par de apps
    consolidated: dict[tuple[str, str], dict] = defaultdict(lambda: {'count': 0, 'types': defaultdict(int)})
    for (src, tgt, etype), count in inter_app_links.items():
        key = (src, tgt)
        consolidated[key]['count'] += count
        consolidated[key]['types'][etype] += count

    app_names = {n['id'] for n in nodes}
    links = []
    for (src, tgt), data in consolidated.items():
        if src in app_names and tgt in app_names:
            links.append(
                {
                    'source': src,
                    'target': tgt,
                    'count': data['count'],
                    'types': dict(data['types']),
                }
            )

    logger.info(f'Overview: {len(nodes)} apps, {len(links)} conexões inter-app.')
    return {'nodes': nodes, 'links': links}


def generate_app_detail_data(iac_dir: Path, app_name: str) -> dict:
    """Gera dados detalhados de um app para o diagrama D3.js.

    Args:
        iac_dir: Caminho para o diretório .iac do projeto.
        app_name: Nome do app Django a detalhar.

    Returns:
        Dict com 'nodes' (componentes), 'links' (arestas internas) e 'app_name'.
    """
    structure = load_structure(iac_dir)
    graph = load_graph(iac_dir)
    app_data = structure.get('apps', {}).get(app_name, {})

    if not app_data:
        logger.warning(f'App "{app_name}" não encontrado.')
        return {'nodes': [], 'links': [], 'app_name': app_name}

    nodes = []
    node_ids = set()

    # Views
    for name, data in app_data.get('views', {}).items():
        node_id = f'{app_name}.views.{name}'
        nodes.append(
            {
                'id': node_id,
                'label': name,
                'type': 'view',
                'file': data.get('file', ''),
                'line': data.get('line', 0),
            }
        )
        node_ids.add(node_id)

    # Models
    for name, data in app_data.get('models', {}).items():
        node_id = f'{app_name}.models.{name}'
        nodes.append(
            {
                'id': node_id,
                'label': name,
                'type': 'model',
                'file': data.get('file', ''),
                'line': data.get('line', 0),
                'fields': data.get('fields', []),
                'methods': list(data.get('methods', {})),
            }
        )
        node_ids.add(node_id)

    # Forms
    for name, data in app_data.get('forms', {}).items():
        node_id = f'{app_name}.forms.{name}'
        nodes.append(
            {
                'id': node_id,
                'label': name,
                'type': 'form',
                'file': data.get('file', ''),
                'line': data.get('line', 0),
            }
        )
        node_ids.add(node_id)

    # Admin
    for name, data in app_data.get('admin', {}).items():
        node_id = f'{app_name}.admin.{name}'
        nodes.append(
            {
                'id': node_id,
                'label': name,
                'type': 'admin',
                'file': data.get('file', ''),
                'line': data.get('line', 0),
            }
        )
        node_ids.add(node_id)

    # Templates (só os que têm arestas)
    templates_with_edges = set()
    for edge in graph.get('edges', []):
        if edge['type'] == 'renders' and _extract_app(edge['from']) == app_name:
            templates_with_edges.add(edge['to'])

    for template_ref in templates_with_edges:
        label = template_ref.split('/')[-1] if '/' in template_ref else template_ref
        nodes.append(
            {
                'id': template_ref,
                'label': label,
                'type': 'template',
                'file': template_ref,
                'line': 0,
            }
        )
        node_ids.add(template_ref)

    # URLs
    for url_entry in app_data.get('urls', [])[:30]:  # limitar URLs no diagrama
        url_id = f'{app_name}/urls:{url_entry["pattern"]}'
        nodes.append(
            {
                'id': url_id,
                'label': url_entry['pattern'],
                'type': 'url',
                'file': f'{app_name}/urls.py',
                'line': 0,
            }
        )
        node_ids.add(url_id)

    # Arestas (filtrar apenas as do app)
    links = []
    for edge in graph.get('edges', []):
        src_app = _extract_app(edge['from'])
        tgt_app = _extract_app(edge['to'])
        if (src_app == app_name or tgt_app == app_name) and edge['from'] in node_ids and edge['to'] in node_ids:
            links.append(
                {
                    'source': edge['from'],
                    'target': edge['to'],
                    'type': edge['type'],
                }
            )

    # Deduplicar links
    seen = set()
    unique_links = []
    for link in links:
        key = (link['source'], link['target'], link['type'])
        if key not in seen:
            seen.add(key)
            unique_links.append(link)

    logger.info(f'App {app_name}: {len(nodes)} nós, {len(unique_links)} arestas.')
    return {'nodes': nodes, 'links': unique_links, 'app_name': app_name}


def _extract_app(fqn: str) -> str | None:
    """Extrai o nome do app de um nome qualificado."""
    if '/urls:' in fqn:
        return fqn.split('/urls:')[0]
    if '/templates/' in fqn:
        return fqn.split('/templates/')[0]
    parts = fqn.split('.')
    return parts[0] if parts else None


def write_html(output_path: Path, template_name: str, data: dict) -> None:
    """Renderiza template HTML com dados JSON embutidos.

    Args:
        output_path: Caminho do arquivo HTML a gerar.
        template_name: Nome do template em iac/diagram/templates/.
        data: Dict com os dados a embutir no placeholder /*__DATA__*/.
    """
    templates_dir = Path(__file__).parent / 'templates'
    template_path = templates_dir / template_name

    html = template_path.read_text(encoding='utf-8')
    html = html.replace('/*__DATA__*/', json.dumps(data, ensure_ascii=False))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding='utf-8')
    logger.info(f'Diagrama gerado: {output_path}')
