"""Runner LLM — executa o fluxo de prompts (single ou multi).

Extraído de cli.py (Princípio 2 — Módulos < 200 linhas).
Encapsula a lógica de envio de prompts e processamento de respostas.
"""

from __future__ import annotations

import logging
import os
import time

from iac.agent.format import format_context_for_prompt
from iac.agent.orchestrator import get_model_profile
from iac.agent.prompts import (
    _strip_context_header,
    build_analysis_prompt,
    build_evidence_prompt,
    build_investigation_prompt,
    build_response_prompt,
    extract_tipo_from_analysis,
    parse_investigation_requests,
    resolve_investigation_requests,
)

logger = logging.getLogger(__name__)


_LLM_RATE_DELAY = int(os.environ.get('IAC_LLM_RATE_DELAY', '0'))
_LLM_MAX_RETRIES = int(os.environ.get('IAC_LLM_MAX_RETRIES', '3'))


def send_to_llm(prompt: str, llm: str, llm_model: str, llm_url: str | None, llm_key: str | None) -> str | None:
    """Envia prompt ao backend LLM configurado.

    Rate delay e retries são controlados por variáveis de ambiente:
        IAC_LLM_RATE_DELAY — delay em segundos entre chamadas (default: 0)
        IAC_LLM_MAX_RETRIES — máximo de retries (default: 3)
    """
    if _LLM_RATE_DELAY > 0 and llm != 'ollama':
        logger.debug(f'[LLM] Rate delay: {_LLM_RATE_DELAY}s')
        time.sleep(_LLM_RATE_DELAY)

    t0 = time.time()
    result = None
    if llm == 'ollama':
        from iac.integrations import ollama
        url = llm_url or 'http://localhost:11434/v1/chat/completions'
        result = ollama.chat(prompt, url=url, model=llm_model, api_key=llm_key)
    elif llm == 'groq':
        from iac.integrations import groq
        url = llm_url or groq.DEFAULT_URL
        result = groq.chat(prompt, url=url, model=llm_model, api_key=llm_key)
    elif llm == 'deepseek':
        from iac.integrations import deepseek
        url = llm_url or deepseek.DEFAULT_URL
        result = deepseek.chat(prompt, url=url, model=llm_model, api_key=llm_key)
    elif llm == 'gemini':
        from iac.integrations import gemini
        if not llm_url or not llm_key:
            logger.warning('Gemini requer llm_url e llm_key.')
            return None
        result = gemini.chat(prompt, url=llm_url, api_key=llm_key)
    elapsed = time.time() - t0
    if result == 'PROMPT_TOO_LARGE':
        logger.warning(f'[LLM] send_to_llm: prompt muito grande em {elapsed:.1f}s')
        return 'PROMPT_TOO_LARGE'
    if result:
        logger.info(f'[LLM] send_to_llm: {len(result)} chars em {elapsed:.1f}s')
    else:
        logger.warning(f'[LLM] send_to_llm: sem resposta em {elapsed:.1f}s (possível timeout ou erro de conexão)')
    return result


def run_single(result: dict, llm: str, llm_model: str, llm_url: str | None, llm_key: str | None, profile: dict | None = None) -> str | None:
    """Executa análise em modo single-prompt com ajuste progressivo.

    Se o prompt for grande demais (413), reduz progressivamente:
    1. Com deep → 2. Sem deep → 3. Desiste.
    """
    model_profile = get_model_profile(llm_model)
    include_deep = model_profile.get('deep_include_methods', True)
    prompt = build_analysis_prompt(result, include_deep=include_deep, profile=profile)
    logger.info(f'[LLM] Modo single-prompt: {len(prompt)} chars (deep={include_deep}) → enviando ao {llm} ({llm_model})')

    analysis = send_to_llm(prompt, llm, llm_model, llm_url, llm_key)

    if analysis == 'PROMPT_TOO_LARGE' and include_deep:
        logger.info('[LLM] Prompt muito grande — retentando sem deep')
        prompt = build_analysis_prompt(result, include_deep=False, profile=profile)
        logger.info(f'[LLM] Modo single-prompt (sem deep): {len(prompt)} chars → enviando ao {llm} ({llm_model})')
        analysis = send_to_llm(prompt, llm, llm_model, llm_url, llm_key)

    if analysis == 'PROMPT_TOO_LARGE':
        logger.error('[LLM] Prompt ainda muito grande mesmo sem deep — modelo não suporta este tamanho')
        return None

    logger.info(f'[LLM] Resposta (single): {len(analysis or "")} chars')
    return analysis


def run_multi(result: dict, structure: dict, graph: dict, base_dir, llm: str, llm_model: str, llm_url: str | None, llm_key: str | None, profile: dict | None = None) -> str | None:
    """Executa análise em modo multi-prompt (investigação → evidência → análise)."""
    logger.info('[LLM] Modo multi-prompt iniciado')

    # Prompt 1: investigação
    investigation_prompt = build_investigation_prompt(result, profile=profile)
    logger.info(f'[LLM] Prompt 1 (investigação): {len(investigation_prompt)} chars → enviando ao {llm} ({llm_model})')
    logger.debug(f'[LLM] Prompt 1 (investigação) conteúdo:\n{investigation_prompt}')

    investigation_response = send_to_llm(investigation_prompt, llm, llm_model, llm_url, llm_key)
    logger.info(f'[LLM] Resposta 1 (investigação): {len(investigation_response or "")} chars')
    logger.debug(f'[LLM] Resposta 1 (investigação) conteúdo:\n{investigation_response}')

    if not investigation_response:
        logger.warning('[LLM] Prompt 1 sem resposta')
        return None

    # Parsear pedidos
    requests = parse_investigation_requests(investigation_response)
    logger.info(f'[LLM] {len(requests)} pedidos de investigação parseados')
    for req in requests:
        logger.debug(f'[LLM] Pedido: tipo={req["type"]}, {req}')

    if not requests:
        logger.info('[LLM] Sem pedidos — fallback para single-prompt')
        return run_single(result, llm, llm_model, llm_url, llm_key, profile=profile)

    # Resolver evidência
    evidence = resolve_investigation_requests(requests, structure, graph, base_dir)
    logger.info(f'[LLM] Evidência resolvida: {len(evidence)} chars')
    logger.debug(f'[LLM] Evidência resolvida conteúdo:\n{evidence}')

    # Prompt 2: análise com evidência + código da view + constantes do deep
    view_context = _strip_context_header(format_context_for_prompt(result['context']))

    # Incluir constantes dos models de nível 1 do deep (alto valor, baixo custo)
    deep_summary = ''
    for m in result.get('deep', []):
        if m.get('depth', 0) <= 1 and m.get('constants'):
            deep_summary += f'\n### Constantes de `{m["fqn"]}`\n'
            for name, value in m['constants'].items():
                deep_summary += f'- `{name} = {value}`\n'

    if deep_summary:
        evidence += '\n---\n' + deep_summary

    evidence_prompt = build_evidence_prompt(evidence, view_context=view_context, profile=profile)
    logger.info(f'[LLM] Prompt 2 (análise): {len(evidence_prompt)} chars → enviando ao {llm} ({llm_model})')
    logger.debug(f'[LLM] Prompt 2 (análise) conteúdo:\n{evidence_prompt}')

    analysis = send_to_llm(evidence_prompt, llm, llm_model, llm_url, llm_key)
    logger.info(f'[LLM] Resposta 2 (análise): {len(analysis or "")} chars')
    logger.debug(f'[LLM] Resposta 2 (análise) conteúdo:\n{analysis}')
    return analysis


def run_auto(result: dict, structure: dict, graph: dict, base_dir, llm: str, llm_model: str, llm_url: str | None, llm_key: str | None, profile: dict | None = None) -> dict:
    """Executa single como fast-path, escala para loop se incerto."""
    from iac.agent.loop import run_loop

    # Passo 1: single como Prompt 0
    logger.info('[auto] Passo 1: single como fast-path')
    single_analysis = run_single(result, llm, llm_model, llm_url, llm_key, profile=profile)

    if not single_analysis:
        logger.warning('[auto] Single sem resposta — fallback para loop')
        loop_result = run_loop(result, structure, graph, base_dir, llm, llm_model, llm_url, llm_key, profile=profile)
        return {**loop_result, 'mode_used': 'loop'}

    # Passo 2: avaliar confiança
    confidence = _confidence_score(single_analysis)
    logger.info(f'[auto] Confiança do single: {confidence}/4')

    if confidence >= 3:
        logger.info('[auto] Resposta confiante — aceitar single')
        tipo = extract_tipo_from_analysis(single_analysis, profile=profile)
        return {
            'analysis': single_analysis,
            'tipo': tipo,
            'alteracoes': [],
            'iterations': 0,
            'mode_used': 'single',
        }

    # Passo 3: escalar para multi (mais estável que loop)
    logger.info(f'[auto] Resposta incerta (confiança={confidence}/4) — escalando para multi')
    multi_analysis = run_multi(result, structure, graph, base_dir, llm, llm_model, llm_url, llm_key, profile=profile)
    if multi_analysis:
        tipo = extract_tipo_from_analysis(multi_analysis, profile=profile)
        return {
            'analysis': multi_analysis,
            'tipo': tipo,
            'alteracoes': [],
            'iterations': 0,
            'mode_used': 'single+multi',
        }

    # Passo 4: se multi também falhou, escalar para loop
    logger.info('[auto] Multi sem resposta — escalando para loop')
    initial_history = (
        f'**Prompt 0 — SINGLE (análise inicial)**\n\n'
        f'{single_analysis}\n\n'
        f'⚠️ A análise acima pode estar incompleta ou imprecisa. '
        f'Revise, investigue mais se necessário, ou confirme com CLASSIFICAR.'
    )
    loop_result = run_loop(
        result, structure, graph, base_dir,
        llm, llm_model, llm_url, llm_key,
        initial_history=initial_history,
        profile=profile,
    )
    return {**loop_result, 'mode_used': 'single+multi+loop'}


def _confidence_score(analysis: str) -> int:
    """Avalia confiança da resposta do single (0-4).

    Critérios:
        1. Tem classificação tipo:: ?
        2. Tem evidência [ENCONTRADO] ?
        3. Mencionou constantes/campos específicos ?
        4. Sugeriu resolução concreta ?

    Args:
        analysis: Texto da análise do LLM.

    Returns:
        Score de 0 a 4.
    """
    score = 0

    # 1. Tem classificação
    if extract_tipo_from_analysis(analysis):
        score += 1

    # 2. Tem evidência encontrada
    if '[ENCONTRADO]' in analysis:
        score += 1

    # 3. Mencionou constantes/campos específicos (não genérico)
    specific_markers = ['TEMPO_', 'data_', 'situacao', 'status', 'prazo', 'periodo']
    if any(m in analysis for m in specific_markers):
        score += 1

    # 4. Sugeriu resolução concreta
    concrete_markers = ['diff', 'ANTES:', 'DEPOIS:', 'Admin >', 'Acessar', 'verificar no banco', 'orientar']
    if any(m.lower() in analysis.lower() for m in concrete_markers):
        score += 1

    return score


def run_response(result: dict, llm_analysis: str, llm: str, llm_model: str, llm_url: str | None, llm_key: str | None, profile: dict | None = None) -> str | None:
    """Gera relatório técnico para o desenvolvedor (prompt 3)."""
    response_prompt = build_response_prompt(result, llm_analysis, profile=profile)
    logger.info(f'[LLM] Prompt 3 (relatório técnico): {len(response_prompt)} chars → enviando ao {llm} ({llm_model})')
    logger.debug(f'[LLM] Prompt 3 (resposta) conteúdo:\n{response_prompt}')

    response_text = send_to_llm(response_prompt, llm, llm_model, llm_url, llm_key)
    logger.info(f'[LLM] Resposta 3 (relatório técnico): {len(response_text or "")} chars')
    logger.debug(f'[LLM] Resposta 3 (resposta) conteúdo:\n{response_text}')
    return response_text
