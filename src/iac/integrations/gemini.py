"""Backend LLM: Google Gemini."""

from __future__ import annotations

import logging

import requests

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 240
DEFAULT_MAX_TOKENS = 4000
DEFAULT_TEMPERATURE = 0.2


def chat(
    prompt: str,
    url: str,
    api_key: str,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
    timeout: int = DEFAULT_TIMEOUT,
) -> str | None:
    """Envia prompt ao Gemini e retorna a resposta.

    Args:
        prompt: Texto do prompt
        url: Endpoint base (ex: https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent)
        api_key: Chave da API Google
        max_tokens: Máximo de tokens na resposta
        temperature: Temperatura do modelo
        timeout: Timeout em segundos

    Returns:
        Texto da resposta ou None em caso de erro.
    """
    headers = {'Content-Type': 'application/json'}
    data = {
        'contents': [{'parts': [{'text': prompt}]}],
        'generationConfig': {
            'temperature': temperature,
            'maxOutputTokens': max_tokens,
        },
    }

    try:
        response = requests.post(f'{url}?key={api_key}', headers=headers, json=data, timeout=timeout)
    except requests.RequestException as e:
        logger.error(f'Requisição ao Gemini falhou: {e}')
        return None

    if response.status_code != 200:
        logger.error(f'Gemini API erro: {response.status_code} - {response.text}')
        return None

    try:
        return response.json()['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        logger.error(f'Erro ao parsear resposta Gemini: {e}')
        return None
