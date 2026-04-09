"""Investigação de código — navega o repositório via .iac/.

Extraído de orchestrator.py (Princípio 2 — Módulos < 200 linhas).
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from iac.agent.tools import (
    extrair_chamadas,
    ler_funcao,
    listar_imports,
    localizar_arquivo,
    resolver_rota,
    seguir_referencia,
)

logger = logging.getLogger(__name__)

DEFAULT_MAX_STEPS = 10
DEFAULT_MAX_CONTEXT_CHARS = 15000
DEFAULT_MAX_REFS = 6


def investigate(
    structure: dict,
    graph: dict,
    base_dir: Path,
    url: str | None = None,
    description: str | None = None,
    traceback: str | None = None,
    max_steps: int = DEFAULT_MAX_STEPS,
    max_context_chars: int = DEFAULT_MAX_CONTEXT_CHARS,
    max_refs: int = DEFAULT_MAX_REFS,
) -> dict:
    """Executa investigação dirigida de um incidente."""
    ctx = _new_context(url=url, description=description, traceback=traceback)
    steps = 0
    context_chars = 0

    # Passo 1: Resolver URL → view
    if url:
        steps += 1
        rota = resolver_rota(url, structure)
        if rota:
            ctx['app'] = rota['app']
            ctx['view_name'] = rota['view_name']
            ctx['view_file'] = rota['file']
            ctx['view_line'] = rota['line']
            ctx['url_pattern'] = rota.get('url_pattern', '')
            _log_step(steps, 'resolver_rota', f'{rota["app"]}.views.{rota["view_name"]}')
        else:
            _log_step(steps, 'resolver_rota', 'não encontrado')

    # Passo 1b: Extrair view do traceback
    if not ctx['view_name'] and traceback:
        steps += 1
        view_info = _extract_view_from_traceback(traceback, structure)
        if view_info:
            ctx.update(view_info)
            _log_step(steps, 'traceback_parse', f'{view_info["app"]}.views.{view_info["view_name"]}')
        else:
            _log_step(steps, 'traceback_parse', 'não encontrado')

    # Passo 1c: Extrair view da descrição
    if not ctx['view_name'] and description:
        steps += 1
        view_info = _extract_view_from_description(description, structure)
        if view_info:
            ctx.update(view_info)
            _log_step(steps, 'description_parse', f'{view_info["app"]}.views.{view_info["view_name"]}')

    if not ctx['view_name']:
        ctx['status'] = 'view_not_found'
        return ctx

    # Passo 2: Ler código da view
    if ctx['view_file'] and ctx['view_line'] and steps < max_steps:
        steps += 1
        source = ler_funcao(ctx['view_file'], ctx['view_line'], base_dir)
        if source:
            ctx['view_source'] = source
            context_chars += len(source)
            _log_step(steps, 'ler_funcao', f'{len(source)} chars')

    # Passo 3: Extrair chamadas
    if ctx['view_name'] and steps < max_steps:
        steps += 1
        fqn = f'{ctx["app"]}.views.{ctx["view_name"]}'
        calls = extrair_chamadas(fqn, structure)
        ctx['calls'] = calls
        _log_step(steps, 'extrair_chamadas', f'{len(calls)} calls')

    # Passo 4: Seguir referências
    refs_followed = 0
    for call in ctx.get('calls', []):
        if steps >= max_steps or context_chars >= max_context_chars or refs_followed >= max_refs:
            break
        if _is_generic_call(call):
            continue

        steps += 1
        ref = seguir_referencia(call, ctx['app'], structure, graph)
        if not ref:
            continue

        ref_key = f'{ref["app"]}.{ref["kind"]}.{ref["name"]}'
        if ref.get('method'):
            ref_key += f'.{ref["method"]}'

        if any(r['key'] == ref_key for r in ctx['references']):
            continue

        method_line = ref.get('method_line')
        ref_entry = {
            'key': ref_key,
            'call': call,
            'app': ref['app'],
            'kind': ref['kind'],
            'name': ref['name'],
            'method': ref.get('method'),
            'file': ref['file'],
            'line': method_line or ref['line'],
            'source': None,
        }

        if context_chars < max_context_chars and steps < max_steps:
            steps += 1
            if method_line:
                src = ler_funcao(ref['file'], method_line, base_dir, max_lines=40)
            else:
                src = ler_funcao(ref['file'], ref['line'], base_dir, max_lines=40, method=ref.get('method'))
            if src:
                ref_entry['source'] = src
                context_chars += len(src)

        ctx['references'].append(ref_entry)
        refs_followed += 1
        _log_step(steps, 'seguir_referencia', f'{call} → {ref_key}')

    # Passo 5: Listar imports
    if ctx['view_file'] and steps < max_steps:
        steps += 1
        imports = listar_imports(ctx['view_file'], base_dir)
        ctx['imports'] = imports
        _log_step(steps, 'listar_imports', f'{len(imports)} imports')

    # Passo 6: Traceback
    if traceback:
        ctx['traceback_parsed'] = _parse_traceback(traceback, ctx['app'])

    ctx['steps_used'] = steps
    ctx['context_chars'] = context_chars
    ctx['status'] = 'complete'
    return ctx


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_view_from_traceback(traceback: str, structure: dict) -> dict | None:
    """Extrai app e view do traceback procurando por views.py ou /app/views/."""
    for match in re.finditer(r'File\s+"[^"]*?(\w+)/views(?:/\w+)?\.py",\s*line\s+(\d+),\s*in\s+(\w+)', traceback):
        app_name, func_name = match.group(1), match.group(3)
        loc = localizar_arquivo(f'{app_name}.views.{func_name}', structure)
        if loc:
            return {'app': loc['app'], 'view_name': loc['name'], 'view_file': loc['file'], 'view_line': loc['line']}
    for match in re.finditer(r'(\w+)\.views\.(\w+)', traceback):
        loc = localizar_arquivo(f'{match.group(1)}.views.{match.group(2)}', structure)
        if loc:
            return {'app': loc['app'], 'view_name': loc['name'], 'view_file': loc['file'], 'view_line': loc['line']}
    return None


def _extract_view_from_description(description: str, structure: dict) -> dict | None:
    """Extrai app e view de uma descrição tentando campo View, URL ou menções."""
    view_field = re.search(r'\*\*View\*\*\s*:\s*(\w+)\.views\.(\w+)', description)
    if view_field:
        loc = localizar_arquivo(f'{view_field.group(1)}.views.{view_field.group(2)}', structure)
        if loc:
            return {'app': loc['app'], 'view_name': loc['name'], 'view_file': loc['file'], 'view_line': loc['line']}
    url_match = re.search(r'https?://[^/\s]+((?:/[^\s?#]*)+)', description)
    if url_match:
        rota = resolver_rota(url_match.group(1), structure)
        if rota:
            return {'app': rota['app'], 'view_name': rota['view_name'], 'view_file': rota['file'], 'view_line': rota['line']}
    for match in re.finditer(r'(\w+)\.views\.(\w+)', description):
        loc = localizar_arquivo(f'{match.group(1)}.views.{match.group(2)}', structure)
        if loc:
            return {'app': loc['app'], 'view_name': loc['name'], 'view_file': loc['file'], 'view_line': loc['line']}
    return None


def _new_context(**kwargs) -> dict:
    """Cria um contexto de investigação vazio."""
    return {
        'url': kwargs.get('url'), 'description': kwargs.get('description'), 'traceback': kwargs.get('traceback'),
        'app': None, 'view_name': None, 'view_file': None, 'view_line': None, 'url_pattern': None,
        'view_source': None, 'calls': [], 'references': [], 'imports': [],
        'traceback_parsed': None, 'steps_used': 0, 'context_chars': 0, 'status': 'incomplete',
    }


def _is_generic_call(call: str) -> bool:
    """Filtra chamadas genéricas que não valem a pena investigar."""
    generic_prefixes = (
        'request.', 'self.', 'super.', 'datetime.', 'str.', 'int.', 'list.',
        'dict.', 'set.', 'len', 'range', 'print', 'isinstance', 'getattr',
        'setattr', 'hasattr', 'type', 'zip', 'enumerate', 'sorted', 'filter',
        'map', 'any', 'all', 'max', 'min', 'sum', 'abs', 'round',
    )
    generic_exact = {
        'render', 'redirect', 'reverse', 'get_object_or_404',
        'HttpResponse', 'JsonResponse', 'Http404',
        'messages.success', 'messages.error', 'messages.warning', 'messages.info',
        'permission_required', 'login_required', 'rtr', 'first',
        'transaction.atomic',
    }
    if call in generic_exact:
        return True
    return any(call.startswith(p) for p in generic_prefixes)


def _parse_traceback(traceback: str, app_name: str | None) -> list[dict]:
    """Parseia frames relevantes do traceback, filtrando libs."""
    frames = []
    for match in re.finditer(r'File\s+"([^"]+)",\s*line\s+(\d+),\s*in\s+(\w+)', traceback):
        file_path, line, func = match.group(1), int(match.group(2)), match.group(3)
        if '/site-packages/' in file_path or '/django/' in file_path:
            continue
        frames.append({'file': file_path, 'line': line, 'function': func})
    return frames


def _log_step(step: int, tool: str, result: str) -> None:
    """Loga um passo do agente."""
    logger.info(f'[Passo {step}] {tool}: {result}')
