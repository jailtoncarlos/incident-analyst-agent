"""Detecção automática do framework do projeto."""

from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


def detect_framework(base_dir: Path) -> dict:
    """Detecta o framework e configurações básicas do projeto.

    Returns:
        dict com: framework, python_version, settings_module, base_dir
    """
    config = {
        'framework': 'unknown',
        'base_dir': str(base_dir),
    }

    # Django: manage.py + settings
    if _detect_django(base_dir, config):
        return config

    # Flask: app.py com Flask import
    if _detect_flask(base_dir, config):
        return config

    # FastAPI: main.py com FastAPI import
    if _detect_fastapi(base_dir, config):
        return config

    # Python genérico: pyproject.toml ou setup.py
    if (base_dir / 'pyproject.toml').exists() or (base_dir / 'setup.py').exists():
        config['framework'] = 'python'

    return config


def _detect_django(base_dir: Path, config: dict) -> bool:
    """Detecta projeto Django."""
    manage_py = base_dir / 'manage.py'
    if not manage_py.exists():
        return False

    config['framework'] = 'django'

    # Extrair DJANGO_SETTINGS_MODULE do manage.py
    content = manage_py.read_text(encoding='utf-8', errors='replace')
    match = re.search(r"DJANGO_SETTINGS_MODULE['\"],\s*['\"]([^'\"]+)['\"]", content)
    if match:
        config['settings_module'] = match.group(1)

    # Extrair versão Python do pyproject.toml se existir
    _extract_python_version(base_dir, config)

    return True


def _detect_flask(base_dir: Path, config: dict) -> bool:
    """Detecta projeto Flask."""
    for candidate in ['app.py', 'application.py', 'wsgi.py']:
        f = base_dir / candidate
        if f.exists():
            content = f.read_text(encoding='utf-8', errors='replace')
            if 'Flask' in content and 'from flask' in content.lower():
                config['framework'] = 'flask'
                config['app_file'] = candidate
                _extract_python_version(base_dir, config)
                return True
    return False


def _detect_fastapi(base_dir: Path, config: dict) -> bool:
    """Detecta projeto FastAPI."""
    for candidate in ['main.py', 'app.py', 'application.py']:
        f = base_dir / candidate
        if f.exists():
            content = f.read_text(encoding='utf-8', errors='replace')
            if 'FastAPI' in content and 'from fastapi' in content.lower():
                config['framework'] = 'fastapi'
                config['app_file'] = candidate
                _extract_python_version(base_dir, config)
                return True
    return False


def _extract_python_version(base_dir: Path, config: dict) -> None:
    """Extrai a versão Python do pyproject.toml."""
    pyproject = base_dir / 'pyproject.toml'
    if not pyproject.exists():
        return

    content = pyproject.read_text(encoding='utf-8', errors='replace')
    match = re.search(r'requires-python\s*=\s*["\']([^"\']+)["\']', content)
    if match:
        config['python_version'] = match.group(1)
