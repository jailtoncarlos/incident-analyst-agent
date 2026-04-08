"""Orquestrador do agente — modo dirigido.

Encadeia as ferramentas de tools.py numa sequência fixa para reconstruir
o contexto completo de um incidente a partir de uma URL, descrição ou traceback.

O resultado é um dict com todo o contexto necessário para o LLM analisar
o incidente sem precisar de grep nem acesso direto ao repositório.

Controles:
    - max_steps: orçamento de passos (padrão 10)
    - max_context_chars: orçamento de contexto (padrão 15000)
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from iac.agent.tools import (
    buscar_simbolo,
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
    """Executa investigação dirigida de um incidente.

    Args:
        structure: Conteúdo de structure.json
        graph: Conteúdo de graph.json
        base_dir: Diretório raiz do projeto
        url: URL onde ocorreu o erro
        description: Descrição do incidente
        traceback: Traceback/stacktrace do erro
        max_steps: Orçamento de passos do agente
        max_context_chars: Limite de caracteres de código no contexto
        max_refs: Máximo de referências a seguir por view

    Returns:
        dict com o contexto estruturado do incidente.
    """
    ctx = _new_context(url=url, description=description, traceback=traceback)
    steps = 0
    context_chars = 0

    # --- Passo 1: Resolver URL → view ---
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

    # --- Passo 1b: Extrair view do traceback se URL não resolveu ---
    if not ctx['view_name'] and traceback:
        steps += 1
        view_info = _extract_view_from_traceback(traceback, structure)
        if view_info:
            ctx.update(view_info)
            _log_step(steps, 'traceback_parse', f'{view_info["app"]}.views.{view_info["view_name"]}')
        else:
            _log_step(steps, 'traceback_parse', 'não encontrado')

    # --- Passo 1c: Extrair view da descrição se ainda não temos ---
    if not ctx['view_name'] and description:
        steps += 1
        view_info = _extract_view_from_description(description, structure)
        if view_info:
            ctx.update(view_info)
            _log_step(steps, 'description_parse', f'{view_info["app"]}.views.{view_info["view_name"]}')

    # Se não encontrou a view, retorna contexto parcial
    if not ctx['view_name']:
        ctx['status'] = 'view_not_found'
        return ctx

    # --- Passo 2: Ler código da view ---
    if ctx['view_file'] and ctx['view_line'] and steps < max_steps:
        steps += 1
        source = ler_funcao(ctx['view_file'], ctx['view_line'], base_dir)
        if source:
            ctx['view_source'] = source
            context_chars += len(source)
            _log_step(steps, 'ler_funcao', f'{len(source)} chars')

    # --- Passo 3: Extrair chamadas da view ---
    if ctx['view_name'] and steps < max_steps:
        steps += 1
        fqn = f'{ctx["app"]}.views.{ctx["view_name"]}'
        calls = extrair_chamadas(fqn, structure)
        ctx['calls'] = calls
        _log_step(steps, 'extrair_chamadas', f'{len(calls)} calls')

    # --- Passo 4: Seguir referências e ler código ---
    refs_followed = 0
    for call in ctx.get('calls', []):
        if steps >= max_steps or context_chars >= max_context_chars or refs_followed >= max_refs:
            break

        # Ignorar chamadas genéricas
        if _is_generic_call(call):
            continue

        steps += 1
        ref = seguir_referencia(call, ctx['app'], structure, graph)
        if not ref:
            continue

        ref_key = f'{ref["app"]}.{ref["kind"]}.{ref["name"]}'
        if ref.get('method'):
            ref_key += f'.{ref["method"]}'

        # Evitar duplicatas
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

        # Ler código da referência se ainda temos orçamento
        if context_chars < max_context_chars and steps < max_steps:
            steps += 1
            if method_line:
                # Linha do método conhecida — ler diretamente
                src = ler_funcao(ref['file'], method_line, base_dir, max_lines=40)
            else:
                # Fallback: buscar método dentro da classe via AST
                src = ler_funcao(ref['file'], ref['line'], base_dir, max_lines=40, method=ref.get('method'))
            if src:
                ref_entry['source'] = src
                context_chars += len(src)

        ctx['references'].append(ref_entry)
        refs_followed += 1
        _log_step(steps, 'seguir_referencia', f'{call} → {ref_key}')

    # --- Passo 5: Listar imports da view (para contexto adicional) ---
    if ctx['view_file'] and steps < max_steps:
        steps += 1
        imports = listar_imports(ctx['view_file'], base_dir)
        ctx['imports'] = imports
        _log_step(steps, 'listar_imports', f'{len(imports)} imports')

    # --- Passo 6: Extrair traceback relevante ---
    if traceback:
        ctx['traceback_parsed'] = _parse_traceback(traceback, ctx['app'])

    ctx['steps_used'] = steps
    ctx['context_chars'] = context_chars
    ctx['status'] = 'complete'
    return ctx


# ---------------------------------------------------------------------------
# Extração de view a partir de traceback e descrição
# ---------------------------------------------------------------------------


def _extract_view_from_traceback(traceback: str, structure: dict) -> dict | None:
    """Extrai app e view do traceback procurando por views.py ou /app/views/."""
    # Procurar: File "app/views.py", line N, in func_name
    for match in re.finditer(r'File\s+"[^"]*?(\w+)/views(?:/\w+)?\.py",\s*line\s+(\d+),\s*in\s+(\w+)', traceback):
        app_name = match.group(1)
        func_name = match.group(3)
        loc = localizar_arquivo(f'{app_name}.views.{func_name}', structure)
        if loc:
            return {
                'app': loc['app'],
                'view_name': loc['name'],
                'view_file': loc['file'],
                'view_line': loc['line'],
            }

    # Fallback: procurar qualquer referência a views
    for match in re.finditer(r'(\w+)\.views\.(\w+)', traceback):
        app_name, func_name = match.group(1), match.group(2)
        loc = localizar_arquivo(f'{app_name}.views.{func_name}', structure)
        if loc:
            return {
                'app': loc['app'],
                'view_name': loc['name'],
                'view_file': loc['file'],
                'view_line': loc['line'],
            }

    return None


def _extract_view_from_description(description: str, structure: dict) -> dict | None:
    """Extrai app e view de uma descrição tentando encontrar URLs ou nomes de view."""
    # 1. Procurar campo **View**: app.views.func (formato das issues SUAP)
    view_field = re.search(r'\*\*View\*\*\s*:\s*(\w+)\.views\.(\w+)', description)
    if view_field:
        loc = localizar_arquivo(f'{view_field.group(1)}.views.{view_field.group(2)}', structure)
        if loc:
            return {
                'app': loc['app'],
                'view_name': loc['name'],
                'view_file': loc['file'],
                'view_line': loc['line'],
            }

    # 2. Procurar URLs — extrair path completo após o host
    url_match = re.search(r'https?://[^/\s]+((?:/[^\s?#]*)+)', description)
    if url_match:
        rota = resolver_rota(url_match.group(1), structure)
        if rota:
            return {
                'app': rota['app'],
                'view_name': rota['view_name'],
                'view_file': rota['file'],
                'view_line': rota['line'],
            }

    # 3. Procurar menções a app.views.func
    for match in re.finditer(r'(\w+)\.views\.(\w+)', description):
        loc = localizar_arquivo(f'{match.group(1)}.views.{match.group(2)}', structure)
        if loc:
            return {
                'app': loc['app'],
                'view_name': loc['name'],
                'view_file': loc['file'],
                'view_line': loc['line'],
            }

    return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _new_context(**kwargs) -> dict:
    """Cria um contexto de investigação vazio."""
    return {
        'url': kwargs.get('url'),
        'description': kwargs.get('description'),
        'traceback': kwargs.get('traceback'),
        'app': None,
        'view_name': None,
        'view_file': None,
        'view_line': None,
        'url_pattern': None,
        'view_source': None,
        'calls': [],
        'references': [],
        'imports': [],
        'traceback_parsed': None,
        'steps_used': 0,
        'context_chars': 0,
        'status': 'incomplete',
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
    for prefix in generic_prefixes:
        if call.startswith(prefix):
            return True
    return False


def _parse_traceback(traceback: str, app_name: str | None) -> list[dict]:
    """Parseia frames relevantes do traceback."""
    frames = []
    for match in re.finditer(
        r'File\s+"([^"]+)",\s*line\s+(\d+),\s*in\s+(\w+)',
        traceback,
    ):
        file_path = match.group(1)
        line = int(match.group(2))
        func = match.group(3)
        # Filtrar frames de libs e Django internals
        if '/site-packages/' in file_path or '/django/' in file_path:
            continue
        frames.append({'file': file_path, 'line': line, 'function': func})
    return frames


def _log_step(step: int, tool: str, result: str) -> None:
    """Loga um passo do agente."""
    logger.info(f'[Passo {step}] {tool}: {result}')


# ---------------------------------------------------------------------------
# Formatação do contexto para prompt
# ---------------------------------------------------------------------------


def format_context_for_prompt(ctx: dict) -> str:
    """Formata o contexto de investigação como texto para incluir no prompt do LLM.

    Produz uma representação estruturada e compacta do código encontrado,
    pronta para ser inserida no prompt de análise.
    """
    sections = []

    # Header
    if ctx.get('app') and ctx.get('view_name'):
        sections.append(f'## Contexto do incidente\n')
        sections.append(f'**App:** {ctx["app"]}')
        if ctx.get('url'):
            sections.append(f'**URL:** {ctx["url"]}')
        if ctx.get('url_pattern'):
            sections.append(f'**Pattern:** {ctx["url_pattern"]}')
        sections.append(f'**View:** {ctx["app"]}.views.{ctx["view_name"]}')
        sections.append(f'**Arquivo:** {ctx["view_file"]}:{ctx["view_line"]}')

    # Código da view
    if ctx.get('view_source'):
        sections.append(f'\n### Código da view ({ctx["view_file"]}:{ctx["view_line"]})\n')
        sections.append(f'```python\n{ctx["view_source"]}\n```')

    # Referências seguidas
    if ctx.get('references'):
        sections.append(f'\n### Referências ({len(ctx["references"])} componentes)\n')
        for ref in ctx['references']:
            label = ref['key']
            sections.append(f'**{label}** ({ref["file"]}:{ref["line"]})')
            if ref.get('source'):
                sections.append(f'```python\n{ref["source"]}\n```')
            sections.append('')

    # Traceback
    if ctx.get('traceback_parsed'):
        sections.append('\n### Traceback (frames do projeto)\n')
        for frame in ctx['traceback_parsed']:
            sections.append(f'  {frame["file"]}:{frame["line"]} in {frame["function"]}')

    # Metadados
    sections.append(f'\n---\n*Passos: {ctx.get("steps_used", 0)}, '
                    f'Contexto: {ctx.get("context_chars", 0)} chars*')

    return '\n'.join(sections)


# ---------------------------------------------------------------------------
# Análise estrutural — combina classifier + orchestrator + grafo
# ---------------------------------------------------------------------------


def build_structural_analysis(
    classification: dict,
    ctx: dict,
    structure: dict,
    graph: dict,
) -> dict:
    """Constrói análise estrutural completa de um incidente.

    Combina os metadados do classifier com o contexto do orchestrator
    e o grafo de dependências para produzir uma visão estrutural pronta
    para exibição e para o LLM.

    Args:
        classification: Resultado de classifier.classify()
        ctx: Resultado de orchestrator.investigate()
        structure: Conteúdo de structure.json
        graph: Conteúdo de graph.json

    Returns:
        dict com a análise estrutural completa.
    """
    app = ctx.get('app') or classification.get('app')
    view_name = ctx.get('view_name')
    view_fqn = f'{app}.views.{view_name}' if app and view_name else None

    analysis = {
        # Identificação
        'app': app,
        'rota': classification.get('url_erro'),
        'view': view_fqn,
        'file': ctx.get('view_file'),
        'line': ctx.get('view_line'),
        # Metadados do incidente
        'origem': classification.get('origem'),
        'erro_id': classification.get('erro_id'),
        'interessado': classification.get('interessado'),
        'descricao_usuario': classification.get('descricao_usuario'),
        'tipo_sugerido': classification.get('tipo_sugerido'),
        # Componentes envolvidos
        'models': [],
        'forms': [],
        'templates': [],
        'admin': [],
        # Fluxo de interação
        'flow': [],
    }

    if not view_fqn:
        return analysis

    # Extrair componentes do grafo a partir da view
    edges = graph.get('edges', [])
    for edge in edges:
        if edge['from'] != view_fqn:
            continue
        target = edge['to']
        etype = edge['type']

        if etype == 'model_usage':
            if target not in analysis['models']:
                analysis['models'].append(target)
        elif etype == 'method_call':
            # model.method → extrair o model
            parts = target.rsplit('.', 1)
            model_fqn = parts[0] if len(parts) > 1 else target
            if model_fqn not in analysis['models'] and '.models.' in model_fqn:
                analysis['models'].append(model_fqn)
        elif etype == 'form_usage':
            if target not in analysis['forms']:
                analysis['forms'].append(target)
        elif etype == 'renders':
            if target not in analysis['templates']:
                analysis['templates'].append(target)

    # URLs que resolvem para essa view
    urls = [e['from'] for e in edges if e['to'] == view_fqn and e['type'] == 'url_resolves']

    # Admin que registra os models envolvidos
    for model_fqn in analysis['models']:
        for edge in edges:
            if edge['to'] == model_fqn and edge['type'] == 'admin_register':
                if edge['from'] not in analysis['admin']:
                    analysis['admin'].append(edge['from'])

    # Relações FK/M2M dos models envolvidos (segundo nível)
    related_models = []
    for model_fqn in analysis['models']:
        for edge in edges:
            if edge['from'] == model_fqn and edge['type'] == 'model_relation':
                if edge['to'] not in analysis['models'] and edge['to'] not in related_models:
                    related_models.append(edge['to'])

    # Construir fluxo de interação
    flow = analysis['flow']

    # URL → View
    for url in urls:
        flow.append({'from': url, 'to': view_fqn, 'type': 'url_resolves'})

    # View → Models (usage + method_call)
    for edge in edges:
        if edge['from'] == view_fqn and edge['type'] in ('model_usage', 'method_call', 'form_usage', 'renders'):
            flow.append({'from': view_fqn, 'to': edge['to'], 'type': edge['type']})

    # Form → Model
    for form_fqn in analysis['forms']:
        for edge in edges:
            if edge['from'] == form_fqn and edge['type'] == 'form_model':
                flow.append({'from': form_fqn, 'to': edge['to'], 'type': 'form_model'})

    # Model → Model (FK)
    for model_fqn in analysis['models']:
        for edge in edges:
            if edge['from'] == model_fqn and edge['type'] == 'model_relation':
                flow.append({'from': model_fqn, 'to': edge['to'], 'type': 'model_relation'})

    analysis['related_models'] = related_models

    return analysis


def format_structural_analysis(analysis: dict) -> str:
    """Formata a análise estrutural como texto legível.

    Produz um resumo estrutural sem código-fonte — foco em
    componentes e fluxo de interação.
    """
    lines = []

    lines.append('## Análise estrutural\n')

    # Identificação
    lines.append(f'**App:** `{analysis["app"]}`')
    if analysis.get('rota'):
        lines.append(f'**Rota:** {analysis["rota"]}')
    if analysis.get('view'):
        lines.append(f'**View:** `{analysis["view"]}`')
    if analysis.get('file'):
        lines.append(f'**Arquivo:** `{analysis["file"]}:{analysis.get("line", "?")}`')

    # Metadados do incidente
    if analysis.get('origem'):
        lines.append(f'**Origem:** {analysis["origem"]}')
    if analysis.get('erro_id'):
        lines.append(f'**Erro ID:** {analysis["erro_id"]}')
    if analysis.get('interessado'):
        lines.append(f'**Interessado:** {analysis["interessado"]}')
    if analysis.get('descricao_usuario'):
        lines.append(f'**Descrição:** "{analysis["descricao_usuario"]}"')

    # Models
    if analysis.get('models'):
        lines.append(f'\n### Models envolvidos\n')
        for m in analysis['models']:
            lines.append(f'- `{m}`')

    # Models relacionados (FK)
    if analysis.get('related_models'):
        lines.append(f'\n### Models relacionados (FK/M2M)\n')
        for m in analysis['related_models']:
            lines.append(f'- `{m}`')

    # Forms
    if analysis.get('forms'):
        lines.append(f'\n### Forms envolvidos\n')
        for f in analysis['forms']:
            lines.append(f'- `{f}`')

    # Templates
    if analysis.get('templates'):
        lines.append(f'\n### Templates\n')
        for t in analysis['templates']:
            lines.append(f'- `{t}`')

    # Admin
    if analysis.get('admin'):
        lines.append(f'\n### Admin\n')
        for a in analysis['admin']:
            lines.append(f'- `{a}`')

    # Fluxo de interação
    if analysis.get('flow'):
        lines.append(f'\n### Fluxo de interação\n')
        lines.append('```')
        for step in analysis['flow']:
            short_from = _short_name(step['from'])
            short_to = _short_name(step['to'])
            lines.append(f'{short_from} ──[{step["type"]}]──> {short_to}')
        lines.append('```')

    return '\n'.join(lines)


def _short_name(fqn: str) -> str:
    """Encurta um FQN para exibição no fluxo."""
    if '/urls:' in fqn:
        return fqn.split('/urls:')[1]
    if '/templates/' in fqn:
        return fqn.split('/templates/')[-1]
    parts = fqn.split('.')
    if len(parts) >= 3:
        return f'{parts[-2]}.{parts[-1]}'
    return fqn
