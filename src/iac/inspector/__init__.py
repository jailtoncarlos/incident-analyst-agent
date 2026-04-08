"""
Módulo de inspeção de repositório.

Responsável por detectar o framework, gerar o mapa estrutural
e construir o grafo de dependências do projeto.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import click

from iac.config.settings import IAC_DIR, save_config, save_graph, save_structure
from iac.inspector.detector import detect_framework
from iac.inspector.graph import build_graph
from iac.inspector.structure import build_structure

logger = logging.getLogger(__name__)


def inspect_project(base_dir: Path, force: bool = False) -> dict:
    """Executa inspeção completa do projeto.

    Returns:
        dict com 'summary' (str) e 'config' (dict)
    """
    iac_dir = base_dir / IAC_DIR

    if force and iac_dir.exists():
        import shutil

        shutil.rmtree(iac_dir)
        logger.info(f'Diretório {iac_dir} removido (--force).')

    # Etapa 1: Detecção do framework
    logger.info('Etapa 1/3: Detectando framework...')
    config = detect_framework(base_dir)
    config['inspected_at'] = datetime.now(UTC).isoformat()
    save_config(iac_dir, config)
    logger.info(f'Framework detectado: {config.get("framework", "desconhecido")}')

    # Etapa 2: Mapa estrutural
    logger.info('Etapa 2/3: Construindo mapa estrutural...')
    structure = build_structure(base_dir, config)
    save_structure(iac_dir, structure)
    app_count = len(structure.get('apps', {}))
    logger.info(f'Mapa estrutural: {app_count} apps mapeados.')

    # Etapa 3: Grafo de dependências
    logger.info('Etapa 3/3: Construindo grafo de dependências...')
    graph = build_graph(structure)
    save_graph(iac_dir, graph)
    edge_count = len(graph.get('edges', []))
    logger.info(f'Grafo: {edge_count} arestas.')

    # Resumo
    views = sum(len(app.get('views', {})) for app in structure.get('apps', {}).values())
    models = sum(len(app.get('models', {})) for app in structure.get('apps', {}).values())

    summary = f'{app_count} apps, {views} views, {models} models, {edge_count} arestas no grafo'

    return {'summary': summary, 'config': config}


def show_stats(iac_dir: Path) -> None:
    """Exibe estatísticas da inspeção existente."""
    config_file = iac_dir / 'project.json'
    structure_file = iac_dir / 'structure.json'
    graph_file = iac_dir / 'graph.json'

    if config_file.exists():
        config = json.loads(config_file.read_text(encoding='utf-8'))
        click.echo(f'Framework: {config.get("framework", "?")}')
        click.echo(f'Inspecionado em: {config.get("inspected_at", "?")}')

    if structure_file.exists():
        structure = json.loads(structure_file.read_text(encoding='utf-8'))
        apps = structure.get('apps', {})
        click.echo(f'Apps: {len(apps)}')
        total_views = sum(len(a.get('views', {})) for a in apps.values())
        total_models = sum(len(a.get('models', {})) for a in apps.values())
        total_forms = sum(len(a.get('forms', {})) for a in apps.values())
        total_urls = sum(len(a.get('urls', [])) for a in apps.values())
        total_templates = sum(len(a.get('templates', [])) for a in apps.values())
        total_admin = sum(len(a.get('admin', {})) for a in apps.values())
        click.echo(f'Views: {total_views}')
        click.echo(f'Models: {total_models}')
        click.echo(f'Forms: {total_forms}')
        click.echo(f'Admin: {total_admin}')
        click.echo(f'URLs: {total_urls}')
        click.echo(f'Templates: {total_templates}')

    if graph_file.exists():
        graph = json.loads(graph_file.read_text(encoding='utf-8'))
        edges = graph.get('edges', [])
        click.echo(f'Arestas no grafo: {len(edges)}')
        # Contagem por tipo
        by_type: dict[str, int] = {}
        for edge in edges:
            t = edge.get('type', '?')
            by_type[t] = by_type.get(t, 0) + 1
        for t, count in sorted(by_type.items()):
            click.echo(f'  {t}: {count}')
