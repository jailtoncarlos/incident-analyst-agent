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
# profile.yaml — perfil do cliente (padrões de issue, regras, taxonomia)
# ---------------------------------------------------------------------------

PROFILE_FILE = 'profile.yaml'

DEFAULT_PROFILE = {
    'system_description': 'Django',
    'rules': [],
}


def load_profile(iac_dir: Path) -> dict:
    """Carrega profile.yaml do .iac/. Retorna defaults se não existir.

    Args:
        iac_dir: Caminho para o diretório .iac do projeto.

    Returns:
        Dict com system_description e rules.
    """
    import yaml

    profile_file = iac_dir / PROFILE_FILE
    if not profile_file.exists():
        return dict(DEFAULT_PROFILE)

    with open(profile_file, encoding='utf-8') as f:
        profile = yaml.safe_load(f) or {}

    merged = dict(DEFAULT_PROFILE)
    merged.update(profile)
    return merged


# ---------------------------------------------------------------------------
# .env — configuração via variáveis de ambiente
# ---------------------------------------------------------------------------


def load_dotenv(iac_dir: Path, env_file: str | None = None) -> None:
    """Carrega .env do .iac/ ou de caminho customizado.

    Args:
        iac_dir: Caminho para o diretório .iac do projeto.
        env_file: Caminho customizado para .env (override).
    """
    from dotenv import load_dotenv as _load_dotenv

    if env_file:
        path = Path(env_file)
        if not path.is_absolute():
            path = iac_dir / path
    else:
        path = iac_dir / '.env'

    if path.exists():
        _load_dotenv(path, override=False)
        logger.info(f'Variáveis carregadas de {path}')


def get_effective_config(iac_dir: Path, cli_args: dict) -> dict:
    """Retorna configuração efetiva: defaults + .env + CLI args.

    Hierarquia: DEFAULT_CONFIG → .env (via os.environ) → CLI args.

    Args:
        iac_dir: Caminho para o diretório .iac do projeto.
        cli_args: Dict com args do CLI.

    Returns:
        Dict de configuração com seções llm, gitlab e analyze.
    """
    import os

    load_dotenv(iac_dir)

    config = dict(DEFAULT_CONFIG)

    # .env → os.environ → config (só se não None)
    env_map = {
        ('llm', 'backend'): os.environ.get('IAC_LLM_BACKEND'),
        ('llm', 'model'): os.environ.get('IAC_LLM_MODEL'),
        ('llm', 'url'): os.environ.get('IAC_LLM_URL'),
        ('llm', 'key'): os.environ.get('GROQ_API_KEY') or os.environ.get('DEEPSEEK_API_KEY') or os.environ.get('GEMINI_API_KEY'),
        ('gitlab', 'token'): os.environ.get('GITLAB_TOKEN'),
        ('analyze', 'mode'): os.environ.get('IAC_ANALYZE_MODE'),
    }
    for (section, key), value in env_map.items():
        if value:
            config[section][key] = value

    # CLI args (maior prioridade)
    overrides = {
        ('llm', 'backend'): cli_args.get('llm'),
        ('llm', 'model'): cli_args.get('llm_model'),
        ('llm', 'url'): cli_args.get('llm_url'),
        ('llm', 'key'): cli_args.get('llm_key'),
        ('gitlab', 'token'): cli_args.get('gitlab_token'),
        ('analyze', 'mode'): cli_args.get('mode'),
    }
    for (section, key), value in overrides.items():
        if value is not None:
            config[section][key] = value

    return config
