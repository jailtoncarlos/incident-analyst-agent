"""Formatação de contexto para prompts.

Extraído de orchestrator.py (Princípio 2 — Módulos < 200 linhas).
"""

from __future__ import annotations


def format_context_for_prompt(ctx: dict) -> str:
    """Formata o contexto de investigação como texto para o prompt do LLM."""
    sections = []

    if ctx.get('app') and ctx.get('view_name'):
        sections.append('## Contexto do incidente\n')
        sections.append(f'**App:** {ctx["app"]}')
        if ctx.get('url'):
            sections.append(f'**URL:** {ctx["url"]}')
        if ctx.get('url_pattern'):
            sections.append(f'**Pattern:** {ctx["url_pattern"]}')
        sections.append(f'**View:** {ctx["app"]}.views.{ctx["view_name"]}')
        sections.append(f'**Arquivo:** {ctx["view_file"]}:{ctx["view_line"]}')

    if ctx.get('view_source'):
        sections.append(f'\n### Código da view ({ctx["view_file"]}:{ctx["view_line"]})\n')
        sections.append(f'```python\n{ctx["view_source"]}\n```')

    if ctx.get('references'):
        sections.append(f'\n### Referências ({len(ctx["references"])} componentes)\n')
        for ref in ctx['references']:
            label = ref['key']
            sections.append(f'**{label}** ({ref["file"]}:{ref["line"]})')
            if ref.get('source'):
                sections.append(f'```python\n{ref["source"]}\n```')
            sections.append('')

    if ctx.get('traceback_parsed'):
        sections.append('\n### Traceback (frames do projeto)\n')
        for frame in ctx['traceback_parsed']:
            sections.append(f'  {frame["file"]}:{frame["line"]} in {frame["function"]}')

    sections.append(f'\n---\n*Passos: {ctx.get("steps_used", 0)}, '
                    f'Contexto: {ctx.get("context_chars", 0)} chars*')

    return '\n'.join(sections)


def fmt_dict(d: dict, indent: int = 2) -> str:
    """Formata um dict para log em múltiplas linhas."""
    lines = []
    prefix = ' ' * indent
    for k, v in d.items():
        if v is None or v == [] or v == '':
            continue
        lines.append(f'{prefix}{k}: {v}')
    return '\n'.join(lines)
