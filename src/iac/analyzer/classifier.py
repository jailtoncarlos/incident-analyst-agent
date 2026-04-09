"""Classificador de incidentes — extrai metadados da issue sem LLM.

Analisa título, descrição e labels para extrair:
    origem, app, view, url_erro, interessado, erro_id, tipo_sugerido, labels_sugeridos.

Migrado de bin/reviewer/triage/parser.py para o pacote iac.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regex compilados
# ---------------------------------------------------------------------------

# Título: "Erro XXXX - Nome do App"
_RE_ERRO_SUAP = re.compile(r'^Erro\s+(\d+)\s*[-\u2013\u2014]\s*(.+)$', re.IGNORECASE)

# Campos estruturados da descrição
_RE_VIEW_FIELD = re.compile(r'\*\*View\*\*:\s*(\S+)')
_RE_URL_FIELD = re.compile(r'\*\*URL com erro\*\*:\s*(https?://\S+)')
_RE_SENTRY_FIELD = re.compile(r'\*\*Sentry\*\*:\s*(https?://\S+|None)')
_RE_INTERESSADO = re.compile(r'\*\*Interessado principal\*\*:\s*(.+?)(?:\n|$)')
_RE_DESCRICAO = re.compile(r'\*\*Descrição\*\*:\s*(.+?)(?:\n\*\*|\n\n|$)', re.DOTALL)
_RE_ERRO_SUAP_LINK = re.compile(r'\*\*Erro no Suap\*\*:\s*(https?://\S+)')

# Exceções de traceback no título (padrão Sentry)
_RE_EXCEPTION_TITLE = re.compile(
    r'^(ValueError|TypeError|AttributeError|KeyError|IntegrityError|'
    r'PermissionDenied|ValidationError|ObjectDoesNotExist|'
    r'OperationalError|IndexError|NotImplementedError|RuntimeError)'
    r'[:\s]',
)

# Mapeamento de nomes de app no título para labels
_APP_ALIASES: dict[str, str] = {
    'Central de Serviços': 'centralservicos',
    'Centralservicos': 'centralservicos',
    'Estágios': 'estagios',
    'Estagios': 'estagios',
    'Ensino': 'edu',
    'Eventos': 'eventos',
    'Auditoria': 'auditoria',
    'Programa de Gestão 2': 'pgd2',
    'Programa de Gestão': 'pgd2',
    'PGD': 'pgd2',
    'Progressão Docente': 'progressao_docente',
    'Processos Seletivos': 'processo_seletivo',
    'Processo Seletivo': 'processo_seletivo',
    'Comum': 'comum',
    'Enquetes': 'enquete',
    'Enquete': 'enquete',
    'Avaliação Integrada': 'avaliacao_integrada',
    'Ponto': 'ponto',
    'Documento Eletrônico': 'documento_eletronico',
    'Processo Eletrônico': 'processo_eletronico',
    'RH': 'rh',
    'Pesquisa': 'pesquisa',
    'Extensão': 'extensao',
    'Patrimônio': 'patrimonio',
    'Almoxarifado': 'almoxarifado',
    'Contratos': 'contratos',
    'Saúde': 'saude',
}


def classify(title: str, description: str, labels: list[str] | None = None) -> dict:
    """Classifica um incidente a partir do título, descrição e labels.

    Args:
        title: Título da issue.
        description: Descrição completa da issue.
        labels: Labels já aplicados à issue, se houver.

    Returns:
        Dict com origem, app, view, url_erro, interessado, erro_id,
        descricao_usuario, sentry_url, traceback, tipo_sugerido e labels_sugeridos.
    """
    labels = labels or []
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

    _detectar_origem(title, description, labels, result)
    _extrair_campos_estruturados(description, result)
    _extrair_app(title, description, result)
    _extrair_traceback(description, result)
    _montar_labels(result)

    logger.info(
        f'Classificação: origem={result["origem"]}, app={result["app"]}, '
        f'tipo={result["tipo_sugerido"]}, interessado={bool(result["interessado"])}'
    )
    return result


# ---------------------------------------------------------------------------
# Detecção de origem
# ---------------------------------------------------------------------------


def _detectar_origem(title: str, description: str, labels: list[str], result: dict) -> None:
    """Detecta se a issue veio do sistema de erros SUAP, Sentry ou reporte manual."""
    # Sentry: label 'sentry' ou exceção no título
    if 'sentry' in [label.lower() for label in labels]:
        result['origem'] = 'sentry'
        result['tipo_sugerido'] = 'tipo::bug'
        return

    if _RE_EXCEPTION_TITLE.match(title):
        result['origem'] = 'sentry'
        result['tipo_sugerido'] = 'tipo::bug'
        return

    # Erro SUAP: título no formato "Erro XXXX - App"
    match = _RE_ERRO_SUAP.match(title)
    if match:
        result['origem'] = 'erro-suap'
        result['erro_id'] = match.group(1)
        return

    # Descrição com campos estruturados do sistema de erros
    if '**Erro no Suap**:' in description or '**View**:' in description:
        result['origem'] = 'erro-suap'
        return

    result['origem'] = 'reporte-manual'


# ---------------------------------------------------------------------------
# Extração de campos estruturados
# ---------------------------------------------------------------------------


def _extrair_campos_estruturados(description: str, result: dict) -> None:
    """Extrai campos da descrição estruturada da issue."""
    # View
    match = _RE_VIEW_FIELD.search(description)
    if match:
        result['view'] = match.group(1)

    # URL com erro
    match = _RE_URL_FIELD.search(description)
    if match:
        result['url_erro'] = match.group(1)

    # Interessado principal
    match = _RE_INTERESSADO.search(description)
    if match:
        result['interessado'] = match.group(1).strip()

    # Descrição do usuário
    match = _RE_DESCRICAO.search(description)
    if match:
        result['descricao_usuario'] = match.group(1).strip()

    # Sentry URL
    match = _RE_SENTRY_FIELD.search(description)
    if match and match.group(1) != 'None':
        result['sentry_url'] = match.group(1)

    # Link do erro SUAP
    match = _RE_ERRO_SUAP_LINK.search(description)
    if match:
        # Extrair erro_id do link se não veio do título
        if not result['erro_id']:
            id_match = re.search(r'/erro/(\d+)/', match.group(1))
            if id_match:
                result['erro_id'] = id_match.group(1)


# ---------------------------------------------------------------------------
# Extração de app
# ---------------------------------------------------------------------------


def _extrair_app(title: str, description: str, result: dict) -> None:
    """Extrai o app Django da view, do título ou da URL."""
    # 1. Da view (mais confiável)
    if result['view']:
        # admin.comum.comum_registronotificacao_changelist → comum
        # centralservicos.views.visualizar_chamado → centralservicos
        parts = result['view'].split('.')
        if parts[0] == 'admin' and len(parts) >= 2:
            result['app'] = parts[1]
        else:
            result['app'] = parts[0]
        return

    # 2. Do título "Erro XXXX - Nome do App"
    match = _RE_ERRO_SUAP.match(title)
    if match:
        app_name = match.group(2).strip()
        for alias, app_label in _APP_ALIASES.items():
            if alias.lower() == app_name.lower():
                result['app'] = app_label
                return

    # 3. Da URL com erro
    if result['url_erro']:
        path_match = re.search(r'https?://[^/]+/([^/]+)/', result['url_erro'])
        if path_match:
            segment = path_match.group(1)
            if segment not in ('admin', 'djtools', 'accounts', 'api', 'static', 'media'):
                result['app'] = segment
                return

    # 4. Dos labels
    for label in _APP_ALIASES.values():
        if label in [l.lower() for l in (result.get('_labels_raw') or [])]:
            result['app'] = label
            return


# ---------------------------------------------------------------------------
# Extração de traceback
# ---------------------------------------------------------------------------


def _extrair_traceback(description: str, result: dict) -> None:
    """Extrai traceback/stacktrace da descrição (formato Sentry ou bloco de código)."""
    # Bloco de código com traceback
    match = re.search(r'```\s*\n(.+?)```', description, re.DOTALL)
    if match:
        result['traceback'] = match.group(1).strip()
        return

    # Traceback inline (File "..." no texto)
    frames = re.findall(r'File\s+"[^"]+",\s*line\s+\d+,\s*in\s+\w+', description)
    if frames:
        result['traceback'] = '\n'.join(frames)


# ---------------------------------------------------------------------------
# Montagem de labels
# ---------------------------------------------------------------------------


def _montar_labels(result: dict) -> None:
    """Monta a lista de labels a aplicar com base nos metadados extraídos."""
    labels = []

    origem_labels = {
        'erro-suap': 'origem::erro-suap',
        'sentry': 'origem::sentry',
        'reporte-manual': 'origem::reporte-manual',
    }
    if result['origem'] and result['origem'] in origem_labels:
        labels.append(origem_labels[result['origem']])

    if result['app']:
        labels.append(result['app'])

    if result['tipo_sugerido']:
        labels.append(result['tipo_sugerido'])

    result['labels_sugeridos'] = labels
