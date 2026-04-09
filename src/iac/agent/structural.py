"""Análise estrutural — componentes e fluxo da view.

Extraído de orchestrator.py (Princípio 2 — Módulos < 200 linhas).
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def build_structural_analysis(
    classification: dict,
    ctx: dict,
    structure: dict,
    graph: dict,
) -> dict:
    """Constrói análise estrutural combinando classifier + orchestrator + grafo.

    Args:
        classification: Dict retornado por classify() com metadados da issue.
        ctx: Contexto de investigação retornado por investigate().
        structure: Mapa estrutural do projeto (.iac/structure.json).
        graph: Grafo de dependências (.iac/graph.json).

    Returns:
        Dict com app, view, models, forms, templates, admin, flow e related_models.
    """
    app = ctx.get('app') or classification.get('app')
    view_name = ctx.get('view_name')
    view_fqn = f'{app}.views.{view_name}' if app and view_name else None

    analysis = {
        'app': app,
        'rota': classification.get('url_erro'),
        'view': view_fqn,
        'file': ctx.get('view_file'),
        'line': ctx.get('view_line'),
        'origem': classification.get('origem'),
        'erro_id': classification.get('erro_id'),
        'interessado': classification.get('interessado'),
        'descricao_usuario': classification.get('descricao_usuario'),
        'tipo_sugerido': classification.get('tipo_sugerido'),
        'models': [],
        'forms': [],
        'templates': [],
        'admin': [],
        'flow': [],
    }

    if not view_fqn:
        return analysis

    edges = graph.get('edges', [])
    apps = structure.get('apps', {})
    view_data = apps.get(app, {}).get('views', {}).get(view_name, {})
    view_calls = view_data.get('calls', [])
    view_renders = view_data.get('renders', [])

    # Template principal
    if view_renders:
        main_template = None
        for t in view_renders:
            base = t.rsplit('/', 1)[-1].replace('.html', '')
            if base == view_name:
                main_template = t
                break
        if not main_template:
            main_template = view_renders[0]
        analysis['templates'].append(f'{app}/templates/{main_template}')

    # Models e Forms dos calls
    for call in view_calls:
        call_head = call.split('.')[0] if '.' in call else call
        if call_head and call_head[0].isupper():
            for a_name, a_data in apps.items():
                if call_head in a_data.get('models', {}):
                    fqn = f'{a_name}.models.{call_head}'
                    if fqn not in analysis['models']:
                        analysis['models'].append(fqn)
                    break
                if call_head in a_data.get('forms', {}):
                    fqn = f'{a_name}.forms.{call_head}'
                    if fqn not in analysis['forms']:
                        analysis['forms'].append(fqn)
                    break
        if '.' in call:
            method = call.split('.')[-1]
            for edge in edges:
                if edge['from'] == view_fqn and edge['type'] == 'method_call' and edge['to'].endswith(f'.{method}'):
                    model_fqn = edge['to'].rsplit('.', 1)[0]
                    if '.models.' in model_fqn and model_fqn not in analysis['models']:
                        analysis['models'].append(model_fqn)
                    break

    # URLs
    urls = [e['from'] for e in edges if e['to'] == view_fqn and e['type'] == 'url_resolves']

    # Admin dos models
    for model_fqn in analysis['models']:
        for edge in edges:
            if edge['to'] == model_fqn and edge['type'] == 'admin_register':
                if edge['from'] not in analysis['admin']:
                    analysis['admin'].append(edge['from'])

    # FK de segundo nível
    related_models = []
    for model_fqn in analysis['models']:
        for edge in edges:
            if edge['from'] == model_fqn and edge['type'] == 'model_relation':
                if edge['to'] not in analysis['models'] and edge['to'] not in related_models:
                    related_models.append(edge['to'])

    # Fluxo
    flow = analysis['flow']
    for url in urls:
        flow.append({'from': url, 'to': view_fqn, 'type': 'url_resolves'})
    for model_fqn in analysis['models']:
        flow.append({'from': view_fqn, 'to': model_fqn, 'type': 'model_usage'})
    for form_fqn in analysis['forms']:
        flow.append({'from': view_fqn, 'to': form_fqn, 'type': 'form_usage'})
        for edge in edges:
            if edge['from'] == form_fqn and edge['type'] == 'form_model':
                flow.append({'from': form_fqn, 'to': edge['to'], 'type': 'form_model'})
    for tmpl in analysis['templates']:
        flow.append({'from': view_fqn, 'to': tmpl, 'type': 'renders'})
    for model_fqn in analysis['models']:
        for edge in edges:
            if edge['from'] == model_fqn and edge['type'] == 'model_relation':
                flow.append({'from': model_fqn, 'to': edge['to'], 'type': 'model_relation'})

    analysis['related_models'] = related_models
    return analysis


def format_structural_analysis(analysis: dict) -> str:
    """Formata a análise estrutural como texto legível.

    Args:
        analysis: Dict retornado por build_structural_analysis().

    Returns:
        Texto em Markdown com dados da issue e componentes estruturais.
    """
    lines = []

    lines.append('## Dados da issue\n')
    lines.append('*Extraídos da descrição da issue pelo classifier (sem LLM).*\n')

    if analysis.get('origem'):
        lines.append(f'**Origem:** {analysis["origem"]}')
    if analysis.get('erro_id'):
        lines.append(f'**Erro ID:** {analysis["erro_id"]}')
    if analysis.get('rota'):
        lines.append(f'**URL com erro:** {analysis["rota"]}')
    if analysis.get('interessado'):
        lines.append(f'**Interessado:** {analysis["interessado"]}')
    if analysis.get('descricao_usuario'):
        lines.append(f'**Descrição do usuário:** "{analysis["descricao_usuario"]}"')
    if analysis.get('tipo_sugerido'):
        lines.append(f'**Tipo sugerido:** `{analysis["tipo_sugerido"]}`')

    lines.append(f'\n## Análise estrutural\n')
    lines.append('*Obtida via inspeção do código (`.iac/structure.json` + `.iac/graph.json`).*\n')

    if analysis.get('app'):
        lines.append(f'**App:** `{analysis["app"]}`')
    if analysis.get('view'):
        lines.append(f'**View:** `{analysis["view"]}`')
    if analysis.get('file'):
        lines.append(f'**Arquivo:** `{analysis["file"]}:{analysis.get("line", "?")}`')

    if analysis.get('models'):
        lines.append(f'\n### Models envolvidos\n')
        for m in analysis['models']:
            lines.append(f'- `{m}`')
    if analysis.get('related_models'):
        lines.append(f'\n### Models relacionados (FK/M2M)\n')
        for m in analysis['related_models']:
            lines.append(f'- `{m}`')
    if analysis.get('forms'):
        lines.append(f'\n### Forms envolvidos\n')
        for f in analysis['forms']:
            lines.append(f'- `{f}`')
    if analysis.get('templates'):
        lines.append(f'\n### Templates\n')
        for t in analysis['templates']:
            lines.append(f'- `{t}`')
    if analysis.get('admin'):
        lines.append(f'\n### Admin\n')
        for a in analysis['admin']:
            lines.append(f'- `{a}`')
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
    """Encurta um FQN para exibição no fluxo (ex: app.views.func → views.func)."""
    if '/urls:' in fqn:
        return fqn.split('/urls:')[1]
    if '/templates/' in fqn:
        return fqn.split('/templates/')[-1]
    parts = fqn.split('.')
    if len(parts) >= 3:
        return f'{parts[-2]}.{parts[-1]}'
    return fqn
