"""Construção do grafo de dependências entre componentes."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def build_graph(structure: dict) -> dict:
    """Constrói grafo de dependências a partir do mapa estrutural.

    Suporta arestas intra-app e inter-app. Um índice global de models
    e forms é construído para resolver referências cruzadas entre apps.

    Returns:
        dict com 'edges': lista de arestas tipadas.
    """
    edges: list[dict] = []
    apps = structure.get('apps', {})

    # Índice global: nome do model/form → lista de (app_name, component_data)
    # Usado para resolver referências inter-app
    global_models = _build_global_index(apps, 'models')
    global_forms = _build_global_index(apps, 'forms')
    global_methods = _build_global_method_index(apps)

    logger.debug(
        f'Índice global: {len(global_models)} models, {len(global_forms)} forms, {len(global_methods)} methods.'
    )

    for app_name, app_data in apps.items():
        views = app_data.get('views', {})
        models = app_data.get('models', {})
        forms = app_data.get('forms', {})
        urls = app_data.get('urls', [])

        # URL → View
        for url_entry in urls:
            view_ref = url_entry.get('view', '')
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
                call_head = call.split('.')[0] if '.' in call else call

                # View → Model (intra-app primeiro, depois inter-app)
                target_app, target_model = _resolve_model(call_head, app_name, models, global_models)
                if target_model:
                    edges.append(
                        {
                            'from': view_fqn,
                            'to': f'{target_app}.models.{target_model}',
                            'type': 'model_usage',
                        }
                    )

                # View → Model.method (intra + inter-app)
                if '.' in call:
                    method = call.split('.')[-1]
                    target_app_m, target_model_m = _resolve_method(method, app_name, models, global_methods)
                    if target_model_m:
                        edges.append(
                            {
                                'from': view_fqn,
                                'to': f'{target_app_m}.models.{target_model_m}.{method}',
                                'type': 'method_call',
                            }
                        )

                # View → Form (intra + inter-app)
                target_app_f, target_form = _resolve_form(call_head, call, app_name, forms, global_forms)
                if target_form:
                    edges.append(
                        {
                            'from': view_fqn,
                            'to': f'{target_app_f}.forms.{target_form}',
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

        # Form → Model (via Meta.model, intra + inter-app)
        for form_name, form_data in forms.items():
            meta_model = form_data.get('meta_model')
            if meta_model:
                target_app_fm, target_model_fm = _resolve_model(meta_model, app_name, models, global_models)
                if target_model_fm:
                    edges.append(
                        {
                            'from': f'{app_name}.forms.{form_name}',
                            'to': f'{target_app_fm}.models.{target_model_fm}',
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

    # Contar inter-app
    inter_app = sum(1 for e in unique_edges if _extract_app(e['from']) != _extract_app(e['to']))
    logger.info(f'Grafo: {len(unique_edges)} arestas únicas ({inter_app} inter-app).')

    return {'edges': unique_edges}


# ---------------------------------------------------------------------------
# Índices globais para resolução inter-app
# ---------------------------------------------------------------------------


def _build_global_index(apps: dict, component_type: str) -> dict[str, list[tuple[str, str]]]:
    """Constrói índice global: nome do componente → [(app_name, component_name)].

    Ex: 'Chamado' → [('centralservicos', 'Chamado')]
    """
    index: dict[str, list[tuple[str, str]]] = {}
    for app_name, app_data in apps.items():
        for comp_name in app_data.get(component_type, {}):
            if comp_name not in index:
                index[comp_name] = []
            index[comp_name].append((app_name, comp_name))
    return index


def _build_global_method_index(apps: dict) -> dict[str, list[tuple[str, str]]]:
    """Constrói índice global: nome do método → [(app_name, model_name)].

    Ex: 'get_tempo_ultrapassado' → [('centralservicos', 'Chamado')]
    """
    index: dict[str, list[tuple[str, str]]] = {}
    for app_name, app_data in apps.items():
        for model_name, model_data in app_data.get('models', {}).items():
            for method in model_data.get('methods', []):
                if method not in index:
                    index[method] = []
                index[method].append((app_name, model_name))
    return index


# ---------------------------------------------------------------------------
# Resolução de referências (intra-app prioritário, fallback inter-app)
# ---------------------------------------------------------------------------


def _resolve_model(
    name: str, current_app: str, local_models: dict, global_models: dict
) -> tuple[str | None, str | None]:
    """Resolve nome de model: prioriza app atual, depois busca global."""
    # Intra-app
    if name in local_models:
        return current_app, name

    # Inter-app
    candidates = global_models.get(name, [])
    if len(candidates) == 1:
        return candidates[0]
    # Se múltiplos candidatos, sem ambiguidade garantida — não resolve
    return None, None


def _resolve_method(
    method: str, current_app: str, local_models: dict, global_methods: dict
) -> tuple[str | None, str | None]:
    """Resolve nome de método para model.method: prioriza app atual."""
    # Intra-app
    for m_name, m_data in local_models.items():
        if method in m_data.get('methods', []):
            return current_app, m_name

    # Inter-app (só se não ambíguo)
    candidates = global_methods.get(method, [])
    if len(candidates) == 1:
        return candidates[0]
    return None, None


def _resolve_form(
    call_head: str, full_call: str, current_app: str, local_forms: dict, global_forms: dict
) -> tuple[str | None, str | None]:
    """Resolve nome de form: prioriza app atual, depois busca global."""
    # Intra-app
    if call_head in local_forms:
        return current_app, call_head
    if full_call in local_forms:
        return current_app, full_call

    # Inter-app
    candidates = global_forms.get(call_head, [])
    if len(candidates) == 1:
        return candidates[0]
    candidates = global_forms.get(full_call, [])
    if len(candidates) == 1:
        return candidates[0]
    return None, None


def _extract_app(fqn: str) -> str | None:
    """Extrai o nome do app de um nome qualificado."""
    if '/urls:' in fqn:
        return fqn.split('/urls:')[0]
    if '/templates/' in fqn:
        return fqn.split('/templates/')[0]
    parts = fqn.split('.')
    return parts[0] if parts else None
