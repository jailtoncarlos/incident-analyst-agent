"""Configuração do projeto inspecionado."""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

IAC_DIR = '.iac'
PROJECT_FILE = 'project.json'
STRUCTURE_FILE = 'structure.json'
GRAPH_FILE = 'graph.json'


def load_config(iac_dir: Path) -> dict:
    """Carrega a configuração do projeto a partir do diretório .iac."""
    project_file = iac_dir / PROJECT_FILE
    if not project_file.exists():
        return {}
    return json.loads(project_file.read_text(encoding='utf-8'))


def save_config(iac_dir: Path, config: dict) -> None:
    """Salva a configuração do projeto no diretório .iac."""
    iac_dir.mkdir(parents=True, exist_ok=True)
    project_file = iac_dir / PROJECT_FILE
    project_file.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding='utf-8')
    logger.info(f'Configuração salva em {project_file}')


def load_structure(iac_dir: Path) -> dict:
    """Carrega o mapa estrutural do projeto."""
    structure_file = iac_dir / STRUCTURE_FILE
    if not structure_file.exists():
        return {}
    return json.loads(structure_file.read_text(encoding='utf-8'))


def save_structure(iac_dir: Path, structure: dict) -> None:
    """Salva o mapa estrutural do projeto."""
    iac_dir.mkdir(parents=True, exist_ok=True)
    structure_file = iac_dir / STRUCTURE_FILE
    structure_file.write_text(json.dumps(structure, indent=2, ensure_ascii=False), encoding='utf-8')
    logger.info(f'Estrutura salva em {structure_file}')


def load_graph(iac_dir: Path) -> dict:
    """Carrega o grafo de dependências."""
    graph_file = iac_dir / GRAPH_FILE
    if not graph_file.exists():
        return {'edges': []}
    return json.loads(graph_file.read_text(encoding='utf-8'))


def save_graph(iac_dir: Path, graph: dict) -> None:
    """Salva o grafo de dependências."""
    iac_dir.mkdir(parents=True, exist_ok=True)
    graph_file = iac_dir / GRAPH_FILE
    graph_file.write_text(json.dumps(graph, indent=2, ensure_ascii=False), encoding='utf-8')
    logger.info(f'Grafo salvo em {graph_file}')
