"""Backend LLM: Groq — inferência rápida via API (compatível OpenAI).

Modelos disponíveis (gratuito com rate limit):
    llama-3.1-8b-instant, llama-3.3-70b-versatile,
    qwen/qwen3-32b, meta-llama/llama-4-scout-17b-16e-instruct.

Rate limit (tier gratuito): ~6.000-12.000 tokens/min.
Retry automático com backoff quando 429 é retornado.

Variáveis de ambiente:
    GROQ_API_KEY       — API key (obrigatória)
    GROQ_RATE_DELAY    — Delay em segundos entre chamadas (default: 0)
    GROQ_MAX_RETRIES   — Máximo de retries em rate limit (default: 3)
"""

from __future__ import annotations

import logging
import os
import re
import time

import requests

logger = logging.getLogger(__name__)

DEFAULT_URL = 'https://api.groq.com/openai/v1/chat/completions'
DEFAULT_TIMEOUT = 60
DEFAULT_MAX_TOKENS = 4000
DEFAULT_TEMPERATURE = 0.2
DEFAULT_RATE_DELAY = int(os.environ.get('GROQ_RATE_DELAY', '0'))
DEFAULT_MAX_RETRIES = int(os.environ.get('GROQ_MAX_RETRIES', '3'))


def chat(
    prompt: str,
    url: str = DEFAULT_URL,
    model: str = 'llama-3.3-70b-versatile',
    api_key: str | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
    timeout: int = DEFAULT_TIMEOUT,
) -> str | None:
    """Envia prompt ao Groq com retry automático em rate limit.

    Args:
        prompt: Texto do prompt.
        url: Endpoint da API.
        model: Nome do modelo Groq.
        api_key: Chave da API (obrigatória).
        max_tokens: Máximo de tokens na resposta.
        temperature: Temperatura do modelo.
        timeout: Timeout em segundos.

    Returns:
        Texto da resposta ou None em caso de erro.
    """
    if not api_key:
        logger.error('Groq requer api_key. Defina GROQ_API_KEY ou use --llm-key.')
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

    if DEFAULT_RATE_DELAY > 0:
        logger.debug(f'[Groq] Rate delay: {DEFAULT_RATE_DELAY}s')
        time.sleep(DEFAULT_RATE_DELAY)

    for attempt in range(1, DEFAULT_MAX_RETRIES + 1):
        try:
            response = requests.post(url, headers=headers, json=data, timeout=timeout)
        except requests.RequestException as e:
            logger.error(f'Requisição ao Groq falhou: {e}')
            return None

        if response.status_code == 429:
            wait = _parse_retry_after(response.text)
            logger.warning(f'[Groq] Rate limit (429) — aguardando {wait}s (tentativa {attempt}/{DEFAULT_MAX_RETRIES})')
            time.sleep(wait)
            continue

        if response.status_code != 200:
            logger.error(f'Groq API erro: {response.status_code} - {response.text}')
            return None

        try:
            result = response.json()
            return result['choices'][0]['message']['content']
        except Exception as e:
            logger.error(f'Erro ao parsear resposta Groq: {e}')
            return None

    logger.error(f'[Groq] Rate limit excedido após {DEFAULT_MAX_RETRIES} tentativas')
    return None


def _parse_retry_after(error_text: str) -> float:
    """Extrai tempo de espera da mensagem de erro 429 do Groq."""
    match = re.search(r'try again in (\d+\.?\d*)s', error_text, re.IGNORECASE)
    if match:
        return float(match.group(1)) + 1.0
    return 30.0
