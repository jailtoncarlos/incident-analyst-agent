"""Orquestrador do agente — ponto de entrada e façade.

Encadeia as camadas: classifier → investigate → structural → deep.
Módulos decompostos em: investigate.py, deep.py, structural.py, format.py.

Princípio 2 — Módulos < 200 linhas.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from iac.analyzer.classifier import classify

# Re-exports para retrocompatibilidade
from iac.agent.investigate import investigate  # noqa: F401
from iac.agent.deep import deep_investigate, format_deep_analysis  # noqa: F401
from iac.agent.structural import build_structural_analysis, format_structural_analysis  # noqa: F401
from iac.agent.format import format_context_for_prompt, fmt_dict  # noqa: F401

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Perfis de contexto por tamanho de modelo
# ---------------------------------------------------------------------------

MODEL_PROFILES = {
    'small': {
        'max_steps': 10, 'max_context_chars': 8000, 'max_refs': 4,
        'deep_max_context_chars': 3000, 'deep_max_depth': 2, 'deep_include_methods': False,
    },
    'medium': {
        'max_steps': 12, 'max_context_chars': 15000, 'max_refs': 6,
        'deep_max_context_chars': 8000, 'deep_max_depth': 2, 'deep_include_methods': True,
    },
    'large': {
        'max_steps': 15, 'max_context_chars': 30000, 'max_refs': 8,
        'deep_max_context_chars': 15000, 'deep_max_depth': 3, 'deep_include_methods': True,
    },
}


def get_model_profile(model_name: str | None) -> dict:
    """Retorna o perfil de contexto baseado no nome do modelo."""
    if not model_name:
        return MODEL_PROFILES['small']

    name = model_name.lower()

    if any(api in name for api in ('gemini', 'gpt', 'claude', 'sonnet', 'opus')):
        return MODEL_PROFILES['large']

    size_match = re.search(r':?(\d+)[bB]', name)
    if size_match:
        size = int(size_match.group(1))
        if size <= 8:
            return MODEL_PROFILES['small']
        if size <= 35:
            return MODEL_PROFILES['medium']
        return MODEL_PROFILES['large']

    return MODEL_PROFILES['small']


# ---------------------------------------------------------------------------
# Ponto de entrada único
# ---------------------------------------------------------------------------


def analyze_issue(
    title: str,
    description: str,
    structure: dict,
    graph: dict,
    base_dir: Path,
    model_name: str | None = None,
    max_steps: int | None = None,
    max_context_chars: int | None = None,
    max_refs: int | None = None,
) -> dict:
    """Ponto de entrada único para análise completa de um incidente.

    Encadeia: classifier → orchestrator → análise estrutural → análise profunda.
    """
    profile = get_model_profile(model_name)
    _max_steps = max_steps or profile['max_steps']
    _max_context_chars = max_context_chars or profile['max_context_chars']
    _max_refs = max_refs or profile['max_refs']

    logger.info(f'[analyze_issue] Entrada: title="{title}", model={model_name}')
    logger.debug(f'[analyze_issue] Perfil: steps={_max_steps}, context={_max_context_chars}, refs={_max_refs}')

    # Camada 1: Classifier
    logger.info('[Camada 1] Classifier — extraindo metadados da descrição')
    classification = classify(title, description)
    logger.info(f'[Camada 1] Resultado: origem={classification["origem"]}, app={classification.get("app")}, erro_id={classification.get("erro_id")}')
    logger.debug('[Camada 1] Classifier retornou:\n' + fmt_dict(classification))

    # Camada 2: Orchestrator
    logger.info('[Camada 2] Orchestrator — navegando código via .iac/')
    url = _extract_path_from_url(classification.get('url_erro'))
    logger.debug(f'[Camada 2] Entrada: url={url}, traceback={bool(classification.get("traceback"))}')
    ctx = investigate(
        structure, graph, base_dir,
        url=url, description=description, traceback=classification.get('traceback'),
        max_steps=_max_steps, max_context_chars=_max_context_chars, max_refs=_max_refs,
    )
    logger.info(f'[Camada 2] Resultado: {ctx.get("app")}.views.{ctx.get("view_name")} — {len(ctx.get("calls", []))} calls, {len(ctx.get("references", []))} refs, {ctx.get("steps_used")} passos')
    logger.debug(f'[Camada 2] view_source: {len(ctx.get("view_source", ""))} chars ({ctx.get("view_file")}:{ctx.get("view_line")})')
    logger.debug('[Camada 2] calls:\n' + '\n'.join(f'  - {c}' for c in ctx.get('calls', [])))
    for r in ctx.get('references', []):
        logger.debug(f'[Camada 2] ref: {r["call"]} → {r["key"]} ({r["file"]}:{r["line"]}, {len(r.get("source", "") or "")} chars)')

    # Camada 3: Análise estrutural
    logger.info('[Camada 3] Structural — combinando classifier + orchestrator + grafo')
    structural = build_structural_analysis(classification, ctx, structure, graph)
    logger.info(f'[Camada 3] Resultado: {len(structural.get("models", []))} models, {len(structural.get("forms", []))} forms, {len(structural.get("templates", []))} templates, {len(structural.get("flow", []))} passos no fluxo')
    logger.debug('[Camada 3] models:\n' + '\n'.join(f'  - {m}' for m in structural.get('models', [])))
    logger.debug('[Camada 3] templates:\n' + '\n'.join(f'  - {t}' for t in structural.get('templates', [])))
    logger.debug('[Camada 3] fluxo:\n' + '\n'.join(f'  {s["from"]} --[{s["type"]}]--> {s["to"]}' for s in structural.get('flow', [])))

    # Camada 4: Análise profunda
    logger.info('[Camada 4] Deep — navegando FKs em profundidade')
    deep = deep_investigate(
        ctx, structure, graph, base_dir,
        max_depth=profile['deep_max_depth'],
        max_context_chars=profile['deep_max_context_chars'],
        include_methods=profile['deep_include_methods'],
    )
    logger.info(f'[Camada 4] Resultado: {len(deep)} models em profundidade')
    logger.debug('[Camada 4] models:\n' + '\n'.join(
        f'  {"  " * m["depth"]}depth={m["depth"]}: {m["fqn"]} — {len(m.get("fields", []))} fields, '
        f'{len(m.get("constants", {}))} constantes, fk={m.get("fk_targets", [])}'
        for m in deep
    ))

    return {
        'classification': classification,
        'context': ctx,
        'structural': structural,
        'deep': deep,
        'profile': profile,
    }


def _extract_path_from_url(url: str | None) -> str | None:
    if not url:
        return None
    match = re.search(r'https?://[^/]+(/.+)', url)
    return match.group(1) if match else None
