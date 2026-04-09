"""Descoberta de apps e extração de configurações Django.

Responsável por localizar os apps instalados num projeto Django
e extrair INSTALLED_APPS dos arquivos de settings — tudo sem
executar o Django ou importar módulos.
"""

from __future__ import annotations

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
