"""Classificador de incidentes — extrai metadados da issue sem LLM.

Analisa título, descrição e labels para extrair:
    origem, app, view, url_erro, interessado, erro_id, tipo_sugerido, labels_sugeridos.

Os padrões de issue (regex, field markers, app aliases) são lidos do
profile (.iac/profile.yaml). Se o profile não define padrões, usa
detecção genérica por campos comuns.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regex compilados (genéricos — padrões estruturados comuns)
# ---------------------------------------------------------------------------

_RE_VIEW_FIELD = re.compile(r'\*\*View\*\*:\s*(\S+)')
_RE_URL_FIELD = re.compile(r'\*\*URL com erro\*\*:\s*(https?://\S+)')
_RE_SENTRY_FIELD = re.compile(r'\*\*Sentry\*\*:\s*(https?://\S+|None)')
_RE_INTERESSADO = re.compile(r'\*\*Interessado principal\*\*:\s*(.+?)(?:\n|$)')
_RE_DESCRICAO = re.compile(r'\*\*Descri[çc][aã]o\*\*:\s*(.+?)(?:\n\*\*|\n\n|$)', re.DOTALL)

# Exceções de traceback no título (padrão Sentry)
_RE_EXCEPTION_TITLE = re.compile(
    r'^(ValueError|TypeError|AttributeError|KeyError|IntegrityError|'
    r'PermissionDenied|ValidationError|ObjectDoesNotExist|'
    r'OperationalError|IndexError|NotImplementedError|RuntimeError)'
    r'[:\s]',
)


def classify(title: str, description: str, labels: list[str] | None = None, profile: dict | None = None) -> dict:
    """Classifica um incidente a partir do título, descrição e labels.

    Args:
        title: Título da issue.
        description: Descrição completa da issue.
        labels: Labels já aplicados à issue, se houver.
        profile: Perfil do cliente (.iac/profile.yaml) com padrões de issue.

    Returns:
        Dict com origem, app, view, url_erro, interessado, erro_id,
        descricao_usuario, sentry_url, traceback, tipo_sugerido e labels_sugeridos.
    """
    labels = labels or []
    profile = profile or {}
    patterns = profile.get('issue_patterns', {})

    result = {
        'origem': None,
        'app': None,
        'view': None,
        'url_erro': None,
        'interessado': None,
        'erro_id': None,
        'descricao_usuario': None,
        'sentry_url': None,
        'traceback': None,
        'tipo_sugerido': None,
        'labels_sugeridos': [],
    }

    _detectar_origem(title, description, labels, result, patterns)
    _extrair_campos_estruturados(description, result, patterns)
    _extrair_app(title, description, result, profile)
    _extrair_traceback(description, result)
    _montar_labels(result)

    logger.info(
        f'Classificação: origem={result["origem"]}, app={result["app"]}, '
        f'tipo={result["tipo_sugerido"]}, interessado={bool(result["interessado"])}'
    )
    return result


def _detectar_origem(title: str, description: str, labels: list[str], result: dict, patterns: dict) -> None:
    """Detecta se a issue veio do sistema de erros, Sentry ou reporte manual."""
    if 'sentry' in [label.lower() for label in labels]:
        result['origem'] = 'sentry'
        result['tipo_sugerido'] = 'tipo::bug'
        return

    if _RE_EXCEPTION_TITLE.match(title):
        result['origem'] = 'sentry'
        result['tipo_sugerido'] = 'tipo::bug'
        return

    # Padrão de título configurável (ex: "Erro XXXX - App")
    title_pattern = patterns.get('title_regex', r'^Erro\s+(\d+)\s*[-\u2013\u2014]\s*(.+)$')
    match = re.match(title_pattern, title, re.IGNORECASE)
    if match:
        result['origem'] = patterns.get('origin_name', 'erro-sistema')
        result['erro_id'] = match.group(1)
        return

    # Campo marcador na descrição (ex: "**Erro no Suap**:")
    origin_marker = patterns.get('origin_marker')
    if origin_marker and origin_marker in description:
        result['origem'] = patterns.get('origin_name', 'erro-sistema')
        return

    # Detecção genérica por campos estruturados
    if '**View**:' in description:
        result['origem'] = patterns.get('origin_name', 'erro-sistema')
        return

    result['origem'] = 'reporte-manual'


def _extrair_campos_estruturados(description: str, result: dict, patterns: dict) -> None:
    """Extrai campos da descrição estruturada da issue."""
    match = _RE_VIEW_FIELD.search(description)
    if match:
        result['view'] = match.group(1)

    match = _RE_URL_FIELD.search(description)
    if match:
        result['url_erro'] = match.group(1)

    match = _RE_INTERESSADO.search(description)
    if match:
        result['interessado'] = match.group(1).strip()

    match = _RE_DESCRICAO.search(description)
    if match:
        result['descricao_usuario'] = match.group(1).strip()

    match = _RE_SENTRY_FIELD.search(description)
    if match and match.group(1) != 'None':
        result['sentry_url'] = match.group(1)

    # Link do erro (ex: /erro/XXXX/)
    error_link_pattern = patterns.get('error_link_regex', r'/erro/(\d+)/')
    for url_match in re.finditer(r'https?://\S+', description):
        id_match = re.search(error_link_pattern, url_match.group())
        if id_match and not result['erro_id']:
            result['erro_id'] = id_match.group(1)
            break


def _extrair_app(title: str, description: str, result: dict, profile: dict) -> None:
    """Extrai o app do framework a partir da view, título ou URL."""
    patterns = profile.get('issue_patterns', {})
    app_aliases = profile.get('app_aliases', {})
    skip_segments = set(profile.get('url_skip_segments', ['admin', 'api', 'static', 'media', 'accounts']))

    # 1. Da view (mais confiável)
    if result['view']:
        parts = result['view'].split('.')
        if parts[0] == 'admin' and len(parts) >= 2:
            result['app'] = parts[1]
        else:
            result['app'] = parts[0]
        return

    # 2. Do título via app_aliases do profile
    title_pattern = patterns.get('title_regex', r'^Erro\s+(\d+)\s*[-\u2013\u2014]\s*(.+)$')
    match = re.match(title_pattern, title, re.IGNORECASE)
    if match and len(match.groups()) >= 2:
        app_name = match.group(2).strip()
        for alias, app_label in app_aliases.items():
            if alias.lower() == app_name.lower():
                result['app'] = app_label
                return

    # 3. Da URL
    if result['url_erro']:
        path_match = re.search(r'https?://[^/]+/([^/]+)/', result['url_erro'])
        if path_match:
            segment = path_match.group(1)
            if segment not in skip_segments:
                result['app'] = segment
                return


def _extrair_traceback(description: str, result: dict) -> None:
    """Extrai traceback/stacktrace da descrição."""
    match = re.search(r'```\s*\n(.+?)```', description, re.DOTALL)
    if match:
        result['traceback'] = match.group(1).strip()
        return

    frames = re.findall(r'File\s+"[^"]+",\s*line\s+\d+,\s*in\s+\w+', description)
    if frames:
        result['traceback'] = '\n'.join(frames)


def _montar_labels(result: dict) -> None:
    """Monta a lista de labels com base nos metadados extraídos."""
    labels = []

    if result['origem']:
        labels.append(f'origem::{result["origem"]}')

    if result['app']:
        labels.append(result['app'])

    if result['tipo_sugerido']:
        labels.append(result['tipo_sugerido'])

    result['labels_sugeridos'] = labels
