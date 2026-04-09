"""Configuração do projeto inspecionado."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

IAC_DIR = '.iac'
PROJECT_FILE = 'project.json'
STRUCTURE_FILE = 'structure.json'
GRAPH_FILE = 'graph.json'
CONFIG_FILE = 'config.yaml'

DEFAULT_CONFIG = {
    'llm': {
        'backend': 'ollama',
        'model': 'qwen2.5:7b',
        'url': 'http://localhost:11434/v1/chat/completions',
        'key': None,
    },
    'gitlab': {
        'url': None,
        'project_id': None,
        'token': None,
    },
    'analyze': {
        'mode': 'auto',
    },
}


def load_config(iac_dir: Path) -> dict:
    """Carrega a configuração do projeto a partir do diretório .iac.

    Args:
        iac_dir: Caminho para o diretório .iac do projeto.

    Returns:
        Dict com a configuração do projeto ou {} se não existir.
    """
    project_file = iac_dir / PROJECT_FILE
    if not project_file.exists():
        return {}
    return json.loads(project_file.read_text(encoding='utf-8'))


def save_config(iac_dir: Path, config: dict) -> None:
    """Salva a configuração do projeto no diretório .iac.

    Args:
        iac_dir: Caminho para o diretório .iac do projeto.
        config: Dict de configuração a persistir.
    """
    iac_dir.mkdir(parents=True, exist_ok=True)
    project_file = iac_dir / PROJECT_FILE
    project_file.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding='utf-8')
    logger.info(f'Configuração salva em {project_file}')


def load_structure(iac_dir: Path) -> dict:
    """Carrega o mapa estrutural do projeto.

    Args:
        iac_dir: Caminho para o diretório .iac do projeto.

    Returns:
        Dict com o mapa estrutural ou {} se não existir.
    """
    structure_file = iac_dir / STRUCTURE_FILE
    if not structure_file.exists():
        return {}
    return json.loads(structure_file.read_text(encoding='utf-8'))


def save_structure(iac_dir: Path, structure: dict) -> None:
    """Salva o mapa estrutural do projeto.

    Args:
        iac_dir: Caminho para o diretório .iac do projeto.
        structure: Dict com o mapa estrutural a persistir.
    """
    iac_dir.mkdir(parents=True, exist_ok=True)
    structure_file = iac_dir / STRUCTURE_FILE
    structure_file.write_text(json.dumps(structure, indent=2, ensure_ascii=False), encoding='utf-8')
    logger.info(f'Estrutura salva em {structure_file}')


def load_graph(iac_dir: Path) -> dict:
    """Carrega o grafo de dependências.

    Args:
        iac_dir: Caminho para o diretório .iac do projeto.

    Returns:
        Dict com 'edges' ou {'edges': []} se não existir.
    """
    graph_file = iac_dir / GRAPH_FILE
    if not graph_file.exists():
        return {'edges': []}
    return json.loads(graph_file.read_text(encoding='utf-8'))


def save_graph(iac_dir: Path, graph: dict) -> None:
    """Salva o grafo de dependências.

    Args:
        iac_dir: Caminho para o diretório .iac do projeto.
        graph: Dict com 'edges' a persistir.
    """
    iac_dir.mkdir(parents=True, exist_ok=True)
    graph_file = iac_dir / GRAPH_FILE
    graph_file.write_text(json.dumps(graph, indent=2, ensure_ascii=False), encoding='utf-8')
    logger.info(f'Grafo salvo em {graph_file}')


# ---------------------------------------------------------------------------
# config.yaml — configurações persistentes do projeto
# ---------------------------------------------------------------------------


def load_user_config(iac_dir: Path) -> dict:
    """Carrega config.yaml do .iac/. Retorna defaults se não existir.

    Args:
        iac_dir: Caminho para o diretório .iac do projeto.

    Returns:
        Dict com configuração efetiva (defaults + valores do usuário mesclados).
    """
    config_file = iac_dir / CONFIG_FILE
    if not config_file.exists():
        return dict(DEFAULT_CONFIG)

    with open(config_file, encoding='utf-8') as f:
        user_config = yaml.safe_load(f) or {}

    # Merge com defaults (user sobrescreve)
    merged = dict(DEFAULT_CONFIG)
    for section, defaults in DEFAULT_CONFIG.items():
        if section in user_config and isinstance(defaults, dict):
            merged[section] = {**defaults, **user_config[section]}
        elif section in user_config:
            merged[section] = user_config[section]

    return merged


def save_user_config(iac_dir: Path, config: dict) -> None:
    """Salva config.yaml no .iac/.

    Args:
        iac_dir: Caminho para o diretório .iac do projeto.
        config: Dict de configuração a persistir (valores None são omitidos).
    """
    iac_dir.mkdir(parents=True, exist_ok=True)
    config_file = iac_dir / CONFIG_FILE

    # Remover valores None para config limpo
    clean = {}
    for section, values in config.items():
        if isinstance(values, dict):
            filtered = {k: v for k, v in values.items() if v is not None}
            if filtered:
                clean[section] = filtered
        elif values is not None:
            clean[section] = values

    with open(config_file, 'w', encoding='utf-8') as f:
        yaml.dump(clean, f, default_flow_style=False, allow_unicode=True)
    logger.info(f'Configuração salva em {config_file}')


def get_effective_config(iac_dir: Path, cli_args: dict) -> dict:
    """Retorna configuração efetiva: config.yaml + overrides do CLI.

    CLI args sobrescrevem config.yaml que sobrescreve defaults.

    Args:
        iac_dir: Caminho para o diretório .iac do projeto.
        cli_args: Dict com args do CLI (llm, llm_model, llm_url, llm_key, gitlab_token, mode).

    Returns:
        Dict de configuração com seções llm, gitlab e analyze já mescladas.
    """
    config = load_user_config(iac_dir)

    # Mapear CLI args para seções do config
    overrides = {
        'llm': {
            'backend': cli_args.get('llm'),
            'model': cli_args.get('llm_model'),
            'url': cli_args.get('llm_url'),
            'key': cli_args.get('llm_key'),
        },
        'gitlab': {
            'token': cli_args.get('gitlab_token'),
        },
        'analyze': {
            'mode': cli_args.get('mode'),
        },
    }

    for section, values in overrides.items():
        for key, value in values.items():
            if value is not None:
                config[section][key] = value

    return config
