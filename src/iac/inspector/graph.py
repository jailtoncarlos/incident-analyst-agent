"""Construção do grafo de dependências entre componentes."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def build_graph(structure: dict) -> dict:
    """Constrói grafo de dependências a partir do mapa estrutural.

    Returns:
        dict com 'edges': lista de arestas tipadas.
    """
    edges: list[dict] = []
    apps = structure.get('apps', {})

    for app_name, app_data in apps.items():
        views = app_data.get('views', {})
        models = app_data.get('models', {})
        forms = app_data.get('forms', {})
        urls = app_data.get('urls', [])

        # URL → View
        for url_entry in urls:
            view_ref = url_entry.get('view', '')
            # Normalizar: 'views.visualizar_chamado' → 'visualizar_chamado'
            view_name = view_ref.split('.')[-1] if '.' in view_ref else view_ref
            if view_name in views:
                edges.append(
                    {
                        'from': f'{app_name}/urls:{url_entry["pattern"]}',
                        'to': f'{app_name}.views.{view_name}',
                        'type': 'url_resolves',
                    }
                )

        # View → Model/Form/Template
        for view_name, view_data in views.items():
            view_fqn = f'{app_name}.views.{view_name}'

            for call in view_data.get('calls', []):
                # View → Model (ex: Chamado.objects.filter)
                model_name = call.split('.')[0] if '.' in call else call
                if model_name in models:
                    edges.append(
                        {
                            'from': view_fqn,
                            'to': f'{app_name}.models.{model_name}',
                            'type': 'model_usage',
                        }
                    )

                # View → Model.method (ex: chamado.resolver_chamado)
                if '.' in call:
                    parts = call.split('.')
                    if len(parts) >= 2:
                        _obj, method = parts[0], parts[-1]
                        for m_name, m_data in models.items():
                            if method in m_data.get('methods', []):
                                edges.append(
                                    {
                                        'from': view_fqn,
                                        'to': f'{app_name}.models.{m_name}.{method}',
                                        'type': 'method_call',
                                    }
                                )

                # View → Form
                if model_name in forms or call in forms:
                    form_name = call if call in forms else model_name
                    edges.append(
                        {
                            'from': view_fqn,
                            'to': f'{app_name}.forms.{form_name}',
                            'type': 'form_usage',
                        }
                    )

            # View → Template
            for template in view_data.get('renders', []):
                edges.append(
                    {
                        'from': view_fqn,
                        'to': f'{app_name}/templates/{template}',
                        'type': 'renders',
                    }
                )

        # Form → Model (via Meta.model)
        for form_name, form_data in forms.items():
            meta_model = form_data.get('meta_model')
            if meta_model and meta_model in models:
                edges.append(
                    {
                        'from': f'{app_name}.forms.{form_name}',
                        'to': f'{app_name}.models.{meta_model}',
                        'type': 'form_model',
                    }
                )

        # Model → Fields
        for model_name, model_data in models.items():
            for field in model_data.get('fields', []):
                edges.append(
                    {
                        'from': f'{app_name}.models.{model_name}',
                        'to': f'{app_name}.models.{model_name}.{field}',
                        'type': 'field_definition',
                    }
                )

    # Deduplicar
    seen = set()
    unique_edges = []
    for edge in edges:
        key = (edge['from'], edge['to'], edge['type'])
        if key not in seen:
            seen.add(key)
            unique_edges.append(edge)

    logger.info(f'Grafo: {len(unique_edges)} arestas únicas.')
    return {'edges': unique_edges}
