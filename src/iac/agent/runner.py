"""Runner LLM — executa o fluxo de prompts (single ou multi).

Extraído de cli.py (Princípio 2 — Módulos < 200 linhas).
Encapsula a lógica de envio de prompts e processamento de respostas.
"""

from __future__ import annotations

import logging
import time

from iac.agent.format import format_context_for_prompt
from iac.agent.prompts import (
    _strip_context_header,
    build_analysis_prompt,
    build_evidence_prompt,
    build_investigation_prompt,
    build_response_prompt,
    parse_investigation_requests,
    resolve_investigation_requests,
)

logger = logging.getLogger(__name__)


def send_to_llm(prompt: str, llm: str, llm_model: str, llm_url: str | None, llm_key: str | None) -> str | None:
    """Envia prompt ao backend LLM configurado.

    Args:
        prompt: Texto do prompt.
        llm: Backend ('ollama' ou 'gemini').
        llm_model: Nome do modelo.
        llm_url: Endpoint da API.
        llm_key: API key.

    Returns:
        Texto da resposta ou None.
    """
    t0 = time.time()
    result = None
    if llm == 'ollama':
        from iac.integrations import ollama
        url = llm_url or 'http://localhost:11434/v1/chat/completions'
        result = ollama.chat(prompt, url=url, model=llm_model, api_key=llm_key)
    elif llm == 'gemini':
        from iac.integrations import gemini
        if not llm_url or not llm_key:
            logger.warning('Gemini requer llm_url e llm_key.')
            return None
        result = gemini.chat(prompt, url=llm_url, api_key=llm_key)
    elapsed = time.time() - t0
    logger.info(f'[LLM] send_to_llm: {len(result or "")} chars em {elapsed:.1f}s')
    return result


def run_single(result: dict, llm: str, llm_model: str, llm_url: str | None, llm_key: str | None) -> str | None:
    """Executa análise em modo single-prompt.

    Args:
        result: Dict retornado por analyze_issue().
        llm: Backend LLM.
        llm_model: Nome do modelo.
        llm_url: Endpoint da API.
        llm_key: API key.

    Returns:
        Texto da análise do LLM ou None.
    """
    prompt = build_analysis_prompt(result)
    logger.info(f'[LLM] Modo single-prompt: {len(prompt)} chars → enviando ao {llm} ({llm_model})')
    logger.debug(f'[LLM] Prompt (single) conteúdo:\n{prompt}')

    analysis = send_to_llm(prompt, llm, llm_model, llm_url, llm_key)
    logger.info(f'[LLM] Resposta (single): {len(analysis or "")} chars')
    logger.debug(f'[LLM] Resposta (single) conteúdo:\n{analysis}')
    return analysis


def run_multi(result: dict, structure: dict, graph: dict, base_dir, llm: str, llm_model: str, llm_url: str | None, llm_key: str | None) -> str | None:
    """Executa análise em modo multi-prompt (investigação → evidência → análise).

    Args:
        result: Dict retornado por analyze_issue().
        structure: Mapa estrutural (.iac/structure.json).
        graph: Grafo de dependências (.iac/graph.json).
        base_dir: Diretório raiz do projeto.
        llm: Backend LLM.
        llm_model: Nome do modelo.
        llm_url: Endpoint da API.
        llm_key: API key.

    Returns:
        Texto da análise do LLM ou None.
    """
    logger.info('[LLM] Modo multi-prompt iniciado')

    # Prompt 1: investigação
    investigation_prompt = build_investigation_prompt(result)
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
        return run_single(result, llm, llm_model, llm_url, llm_key)

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

    evidence_prompt = build_evidence_prompt(evidence, view_context=view_context)
    logger.info(f'[LLM] Prompt 2 (análise): {len(evidence_prompt)} chars → enviando ao {llm} ({llm_model})')
    logger.debug(f'[LLM] Prompt 2 (análise) conteúdo:\n{evidence_prompt}')

    analysis = send_to_llm(evidence_prompt, llm, llm_model, llm_url, llm_key)
    logger.info(f'[LLM] Resposta 2 (análise): {len(analysis or "")} chars')
    logger.debug(f'[LLM] Resposta 2 (análise) conteúdo:\n{analysis}')
    return analysis


def run_response(result: dict, llm_analysis: str, llm: str, llm_model: str, llm_url: str | None, llm_key: str | None) -> str | None:
    """Gera rascunho de resposta ao usuário (prompt 3).

    Args:
        result: Dict retornado por analyze_issue().
        llm_analysis: Texto da análise do LLM (prompt 2).
        llm: Backend LLM.
        llm_model: Nome do modelo.
        llm_url: Endpoint da API.
        llm_key: API key.

    Returns:
        Texto do rascunho de resposta ou None.
    """
    response_prompt = build_response_prompt(result, llm_analysis)
    logger.info(f'[LLM] Prompt 3 (resposta ao usuário): {len(response_prompt)} chars → enviando ao {llm} ({llm_model})')
    logger.debug(f'[LLM] Prompt 3 (resposta) conteúdo:\n{response_prompt}')

    response_text = send_to_llm(response_prompt, llm, llm_model, llm_url, llm_key)
    logger.info(f'[LLM] Resposta 3 (resposta ao usuário): {len(response_text or "")} chars')
    logger.debug(f'[LLM] Resposta 3 (resposta) conteúdo:\n{response_text}')
    return response_text
