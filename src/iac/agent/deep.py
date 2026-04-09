"""Análise profunda — navega FKs em profundidade sem LLM.

Extraído de orchestrator.py (Princípio 2 — Módulos < 200 linhas).
"""

from __future__ import annotations

import logging
from pathlib import Path

from iac.agent.tools import ler_funcao

logger = logging.getLogger(__name__)


def deep_investigate(
    ctx: dict,
    structure: dict,
    graph: dict,
    base_dir: Path,
    max_depth: int = 2,
    max_context_chars: int = 10000,
    include_methods: bool = True,
) -> list[dict]:
    """Navega FKs em profundidade a partir dos models da view.

    Args:
        ctx: Contexto de investigação retornado por investigate().
        structure: Mapa estrutural do projeto (.iac/structure.json).
        graph: Grafo de dependências (.iac/graph.json).
        base_dir: Diretório raiz do projeto inspecionado.
        max_depth: Profundidade máxima de navegação via FKs.
        max_context_chars: Limite de caracteres de código a incluir.
        include_methods: Se True, inclui código-fonte dos métodos.

    Returns:
        Lista de dicts com dados dos models visitados, ordenada por profundidade.
    """
    apps = structure.get('apps', {})
    edges = graph.get('edges', [])
    context_chars = 0

    seed_models = set()
    for call in ctx.get('calls', []):
        call_head = call.split('.')[0] if '.' in call else call
        if call_head and call_head[0].isupper():
            for app_name, app_data in apps.items():
                if call_head in app_data.get('models', {}):
                    seed_models.add((app_name, call_head))
                    break

    visited = set()
    result = []

    def _explore(app_name: str, model_name: str, depth: int):
        """Visita recursivamente um model e seus FK targets."""
        nonlocal context_chars
        fqn = f'{app_name}.models.{model_name}'
        if fqn in visited or depth > max_depth:
            return
        visited.add(fqn)

        model_data = apps.get(app_name, {}).get('models', {}).get(model_name, {})
        if not model_data:
            return

        entry = {
            'fqn': fqn, 'depth': depth, 'file': model_data.get('file', ''),
            'line': model_data.get('line', 0), 'fields': model_data.get('fields', []),
            'methods': {}, 'constants': model_data.get('constants', {}), 'fk_targets': [],
        }

        methods_data = model_data.get('methods', {})
        if not include_methods:
            entry['method_names'] = list(methods_data.keys())
        else:
            for method_name, method_info in methods_data.items():
                if context_chars >= max_context_chars:
                    break
                method_line = method_info.get('line')
                if method_line:
                    src = ler_funcao(model_data['file'], method_line, base_dir, max_lines=20)
                    if src:
                        entry['methods'][method_name] = {'line': method_line, 'source': src}
                        context_chars += len(src)

        for edge in edges:
            if edge['from'] == fqn and edge['type'] == 'model_relation':
                target = edge['to']
                target_parts = target.split('.')
                if len(target_parts) >= 3:
                    entry['fk_targets'].append(target)
                    _explore(target_parts[0], target_parts[2], depth + 1)

        result.append(entry)

    for app_name, model_name in seed_models:
        _explore(app_name, model_name, 0)

    result.sort(key=lambda x: x['depth'])
    return result


def format_deep_analysis(deep_models: list[dict]) -> str:
    """Formata a análise profunda como texto para o prompt.

    Args:
        deep_models: Lista de dicts retornada por deep_investigate().

    Returns:
        Texto em Markdown com os models e seus detalhes por nível de profundidade.
    """
    if not deep_models:
        return ''

    lines = ['## Análise profunda dos models\n']
    lines.append('*Navegação em profundidade via FKs (sem LLM).*\n')

    for model in deep_models:
        indent = '  ' * model['depth']
        depth_label = f' (nível {model["depth"]})' if model['depth'] > 0 else ''
        lines.append(f'{indent}### `{model["fqn"]}`{depth_label}\n')
        lines.append(f'{indent}**Arquivo:** `{model["file"]}:{model["line"]}`')

        if model['fields']:
            lines.append(f'{indent}**Fields:** {", ".join(f"`{f}`" for f in model["fields"][:15])}')

        if model['constants']:
            lines.append(f'{indent}**Constantes:**')
            for name, value in model['constants'].items():
                lines.append(f'{indent}- `{name} = {value}`')

        if model.get('fk_targets'):
            fk_names = [f'`{t.split(".")[-1]}`' for t in model['fk_targets']]
            lines.append(f'{indent}**FKs:** {", ".join(fk_names)}')

        if model.get('methods'):
            lines.append(f'\n{indent}**Métodos:**\n')
            for _method_name, method_info in model['methods'].items():
                lines.append(f'{indent}```python')
                lines.append(f'{method_info["source"]}')
                lines.append(f'{indent}```\n')
        elif model.get('method_names'):
            methods_str = ', '.join(f'`{m}`' for m in model['method_names'][:10])
            extra = f' (+{len(model["method_names"]) - 10})' if len(model['method_names']) > 10 else ''
            lines.append(f'{indent}**Métodos:** {methods_str}{extra}')

    return '\n'.join(lines)
