"""Backend LLM: Groq — inferência rápida via API (compatível OpenAI).

Modelos disponíveis (gratuito com rate limit):
    llama-3.1-8b-instant, llama-3.1-70b-versatile,
    llama-3.3-70b-versatile, mixtral-8x7b-32768, gemma2-9b-it.
"""

from __future__ import annotations

import logging

import requests

logger = logging.getLogger(__name__)

DEFAULT_URL = 'https://api.groq.com/openai/v1/chat/completions'
DEFAULT_TIMEOUT = 60  # Groq é rápido (~1-3s)
DEFAULT_MAX_TOKENS = 4000
DEFAULT_TEMPERATURE = 0.2


def chat(
    prompt: str,
    url: str = DEFAULT_URL,
    model: str = 'llama-3.1-70b-versatile',
    api_key: str | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
    timeout: int = DEFAULT_TIMEOUT,
) -> str | None:
    """Envia prompt ao Groq e retorna a resposta.

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
        logger.error('Groq requer api_key. Obtenha em https://console.groq.com/keys')
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

    try:
        response = requests.post(url, headers=headers, json=data, timeout=timeout)
    except requests.RequestException as e:
        logger.error(f'Requisição ao Groq falhou: {e}')
        return None

    if response.status_code != 200:
        logger.error(f'Groq API erro: {response.status_code} - {response.text}')
        return None

    try:
        result = response.json()
        return result['choices'][0]['message']['content']
    except Exception as e:
        logger.error(f'Erro ao parsear resposta Groq: {e}')
        return None
