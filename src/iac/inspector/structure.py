"""Construção do mapa estrutural do projeto."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def build_structure(base_dir: Path, config: dict) -> dict:
    """Constrói o mapa estrutural com base no framework detectado.

    Args:
        base_dir: Diretório raiz do projeto a inspecionar.
        config: Dict de configuração retornado por detect_framework().

    Returns:
        Dict com chave 'apps' contendo o mapa por app/módulo.
    """
    framework = config.get('framework', 'unknown')

    if framework == 'django':
        from iac.inspector.django import build_django_structure

        return build_django_structure(base_dir, config)

    # Frameworks futuros
    logger.warning(f'Framework "{framework}" ainda não suportado para mapeamento estrutural.')
    return {'apps': {}}
