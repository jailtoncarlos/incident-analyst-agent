"""Backend LLM: DeepSeek — modelos especializados em código (API compatível OpenAI).

Modelos disponíveis:
    deepseek-coder — especialista em código, melhor custo
    deepseek-chat (V3) — generalista forte, raciocínio próximo ao GPT-4
    deepseek-reasoner (R1) — chain-of-thought, raciocínio profundo

$5 de crédito grátis ao criar conta (sem cartão).
API key: https://platform.deepseek.com/api_keys

Variáveis de ambiente:
    DEEPSEEK_API_KEY — API key (obrigatória)
"""

from __future__ import annotations

import logging
import os
import re
import time

import requests

logger = logging.getLogger(__name__)

DEFAULT_URL = 'https://api.deepseek.com/v1/chat/completions'
DEFAULT_TIMEOUT = 120
DEFAULT_MAX_TOKENS = 4000
DEFAULT_TEMPERATURE = 0.2
DEFAULT_MAX_RETRIES = int(os.environ.get('IAC_LLM_MAX_RETRIES', '3'))


def chat(
    prompt: str,
    url: str = DEFAULT_URL,
    model: str = 'deepseek-coder',
    api_key: str | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
    timeout: int = DEFAULT_TIMEOUT,
) -> str | None:
    """Envia prompt ao DeepSeek com retry automático em rate limit.

    Args:
        prompt: Texto do prompt.
        url: Endpoint da API.
        model: Nome do modelo (deepseek-coder, deepseek-chat, deepseek-reasoner).
        api_key: Chave da API (obrigatória).
        max_tokens: Máximo de tokens na resposta.
        temperature: Temperatura do modelo.
        timeout: Timeout em segundos.

    Returns:
        Texto da resposta ou None em caso de erro.
    """
    if not api_key:
        logger.error('DeepSeek requer api_key. Defina DEEPSEEK_API_KEY ou use --llm-key.')
        return None

    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}',
    }

    data = {
        'model': model,
        'messages': [{'role': 'user', 'content': prompt}],
        'max_tokens': max_tokens,
        'temperature': temperature,
    }

    for attempt in range(1, DEFAULT_MAX_RETRIES + 1):
        try:
            response = requests.post(url, headers=headers, json=data, timeout=timeout)
        except requests.RequestException as e:
            logger.error(f'Requisição ao DeepSeek falhou: {e}')
            return None

        if response.status_code in (429, 413):
            wait = _parse_retry_after(response.text)
            logger.warning(f'[DeepSeek] Rate limit ({response.status_code}) — aguardando {wait}s (tentativa {attempt}/{DEFAULT_MAX_RETRIES})')
            time.sleep(wait)
            continue

        if response.status_code != 200:
            logger.error(f'DeepSeek API erro: {response.status_code} - {response.text}')
            return None

        try:
            result = response.json()
            return result['choices'][0]['message']['content']
        except Exception as e:
            logger.error(f'Erro ao parsear resposta DeepSeek: {e}')
            return None

    logger.error(f'[DeepSeek] Rate limit excedido após {DEFAULT_MAX_RETRIES} tentativas')
    return None


def _parse_retry_after(error_text: str) -> float:
    """Extrai tempo de espera da mensagem de erro do DeepSeek."""
    match = re.search(r'try again in (\d+\.?\d*)s', error_text, re.IGNORECASE)
    if match:
        return float(match.group(1)) + 1.0
    return 30.0
