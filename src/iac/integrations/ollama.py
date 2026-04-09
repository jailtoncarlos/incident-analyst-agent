"""Backend LLM: Ollama (local/self-hosted).

Suporta API OpenAI-compatible (/v1/chat/completions) e API nativa Ollama (/api/chat).
"""

from __future__ import annotations

import logging

import requests

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 1200  # 20 min — modelos 14B em CPU podem ser muito lentos
DEFAULT_MAX_TOKENS = 4000
DEFAULT_TEMPERATURE = 0.2


def chat(
    prompt: str,
    url: str,
    model: str,
    api_key: str | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
    timeout: int = DEFAULT_TIMEOUT,
) -> str | None:
    """Envia prompt ao Ollama e retorna a resposta.

    Args:
        prompt: Texto do prompt
        url: Endpoint da API (ex: http://localhost:11434/v1/chat/completions)
        model: Nome do modelo (ex: qwen2.5:7b)
        api_key: Chave da API (opcional para Ollama local)
        max_tokens: Máximo de tokens na resposta
        temperature: Temperatura do modelo
        timeout: Timeout em segundos

    Returns:
        Texto da resposta ou None em caso de erro.
    """
    headers = {'Content-Type': 'application/json'}
    if api_key:
        headers['Authorization'] = f'Bearer {api_key}'

    data = {
        'model': model,
        'messages': [{'role': 'user', 'content': prompt}],
        'max_tokens': max_tokens,
        'temperature': temperature,
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=timeout)
    except requests.RequestException as e:
        logger.error(f'Requisição ao Ollama falhou: {e}')
        return None

    if response.status_code != 200:
        logger.error(f'Ollama API erro: {response.status_code} - {response.text}')
        return None

    try:
        result = response.json()
        # Formato OpenAI (/v1/chat/completions)
        if 'choices' in result:
            return result['choices'][0]['message']['content']
        # Formato Ollama nativo (/api/chat)
        return result.get('message', {}).get('content')
    except Exception as e:
        logger.error(f'Erro ao parsear resposta Ollama: {e}')
        return None
