"""Testes para integrações LLM — rate limit, fallback, ajuste progressivo.

Cobre: 413 (prompt too large), 429 (rate limit), PROMPT_TOO_LARGE no runner,
ajuste progressivo no run_single, retry no groq/deepseek.
"""

from unittest.mock import MagicMock, patch

import pytest

from iac.agent.runner import send_to_llm


# ---------------------------------------------------------------------------
# groq.py — 413 retorna PROMPT_TOO_LARGE sem retry
# ---------------------------------------------------------------------------


def test_groq_413_returns_prompt_too_large():
    """Groq 413 deve retornar 'PROMPT_TOO_LARGE' imediatamente, sem retry."""
    mock_response = MagicMock()
    mock_response.status_code = 413
    mock_response.text = 'Request too large for model'

    with patch('iac.integrations.groq.requests.post', return_value=mock_response):
        from iac.integrations.groq import chat
        result = chat('prompt grande', api_key='test-key')
        assert result == 'PROMPT_TOO_LARGE'


def test_groq_429_retries():
    """Groq 429 deve fazer retry com backoff."""
    mock_429 = MagicMock()
    mock_429.status_code = 429
    mock_429.text = 'Please try again in 1.0s'

    mock_200 = MagicMock()
    mock_200.status_code = 200
    mock_200.json.return_value = {'choices': [{'message': {'content': 'resposta ok'}}]}

    with patch('iac.integrations.groq.requests.post', side_effect=[mock_429, mock_200]):
        with patch('iac.integrations.groq.time.sleep'):
            from iac.integrations.groq import chat
            result = chat('prompt', api_key='test-key')
            assert result == 'resposta ok'


def test_groq_429_max_retries_exhausted():
    """Groq 429 × max_retries deve retornar None."""
    mock_429 = MagicMock()
    mock_429.status_code = 429
    mock_429.text = 'Please try again in 1.0s'

    with patch('iac.integrations.groq.requests.post', return_value=mock_429):
        with patch('iac.integrations.groq.time.sleep'):
            with patch('iac.integrations.groq.DEFAULT_MAX_RETRIES', 2):
                from iac.integrations.groq import chat
                result = chat('prompt', api_key='test-key')
                assert result is None


def test_groq_sem_api_key():
    """Groq sem api_key deve retornar None com erro."""
    from iac.integrations.groq import chat
    result = chat('prompt', api_key=None)
    assert result is None


def test_groq_200_ok():
    """Groq 200 deve retornar conteúdo."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {'choices': [{'message': {'content': 'análise completa'}}]}

    with patch('iac.integrations.groq.requests.post', return_value=mock_response):
        from iac.integrations.groq import chat
        result = chat('prompt', api_key='test-key')
        assert result == 'análise completa'


def test_groq_500_returns_none():
    """Groq 500 (erro servidor) deve retornar None."""
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = 'Internal Server Error'

    with patch('iac.integrations.groq.requests.post', return_value=mock_response):
        from iac.integrations.groq import chat
        result = chat('prompt', api_key='test-key')
        assert result is None


def test_groq_connection_error():
    """Groq connection error deve retornar None."""
    import requests

    with patch('iac.integrations.groq.requests.post', side_effect=requests.ConnectionError('offline')):
        from iac.integrations.groq import chat
        result = chat('prompt', api_key='test-key')
        assert result is None


# ---------------------------------------------------------------------------
# deepseek.py — mesmos padrões
# ---------------------------------------------------------------------------


def test_deepseek_413_returns_prompt_too_large():
    """DeepSeek 413 deve retornar 'PROMPT_TOO_LARGE'."""
    mock_response = MagicMock()
    mock_response.status_code = 413
    mock_response.text = 'Request too large'

    with patch('iac.integrations.deepseek.requests.post', return_value=mock_response):
        from iac.integrations.deepseek import chat
        result = chat('prompt', api_key='test-key')
        assert result == 'PROMPT_TOO_LARGE'


def test_deepseek_sem_api_key():
    """DeepSeek sem api_key deve retornar None."""
    from iac.integrations.deepseek import chat
    result = chat('prompt', api_key=None)
    assert result is None


# ---------------------------------------------------------------------------
# send_to_llm — propaga PROMPT_TOO_LARGE
# ---------------------------------------------------------------------------


def test_send_to_llm_propaga_prompt_too_large():
    """send_to_llm deve propagar PROMPT_TOO_LARGE do backend."""
    with patch('iac.integrations.groq.chat', return_value='PROMPT_TOO_LARGE'):
        result = send_to_llm('prompt', 'groq', 'model', None, 'key')
        assert result == 'PROMPT_TOO_LARGE'


def test_send_to_llm_groq_sucesso():
    """send_to_llm com groq deve retornar resposta."""
    with patch('iac.integrations.groq.chat', return_value='análise ok'):
        result = send_to_llm('prompt', 'groq', 'model', None, 'key')
        assert result == 'análise ok'


def test_send_to_llm_ollama_sem_rate_delay():
    """send_to_llm com ollama não deve aplicar rate delay."""
    with patch('iac.integrations.ollama.chat', return_value='resp') as mock_chat:
        with patch('iac.agent.runner.time.sleep') as mock_sleep:
            result = send_to_llm('prompt', 'ollama', 'model', 'http://localhost:11434/v1/chat/completions', None)
            # Ollama não deve ter delay
            mock_sleep.assert_not_called()


# ---------------------------------------------------------------------------
# run_single — ajuste progressivo
# ---------------------------------------------------------------------------


def test_run_single_fallback_sem_deep():
    """run_single deve retentar sem deep quando 413."""
    result = {
        'structural': {'components': [], 'flow': [], 'issue_data': {}},
        'context': {'view': None, 'references': [], 'steps': 0, 'context_chars': 0},
        'deep': [{'fqn': 'app.Model', 'fields': [], 'constants': {}, 'depth': 0, 'file': 'models.py', 'line': 1}],
    }

    call_count = {'n': 0}

    def mock_send(prompt, llm, model, url, key):
        call_count['n'] += 1
        if call_count['n'] == 1:
            return 'PROMPT_TOO_LARGE'
        return 'CLASSIFICAÇÃO: tipo::bug\nAnálise sem deep.'

    with patch('iac.agent.runner.send_to_llm', side_effect=mock_send):
        from iac.agent.runner import run_single
        analysis = run_single(result, 'groq', 'llama-3.3-70b-versatile', None, 'key')
        assert analysis is not None
        assert 'tipo::bug' in analysis
        assert call_count['n'] == 2  # Tentou 2x: com deep, sem deep


def test_run_single_413_duas_vezes_retorna_none():
    """run_single deve retornar None se 413 persiste mesmo sem deep."""
    result = {
        'structural': {'components': [], 'flow': [], 'issue_data': {}},
        'context': {'view': None, 'references': [], 'steps': 0, 'context_chars': 0},
        'deep': [],
    }

    with patch('iac.agent.runner.send_to_llm', return_value='PROMPT_TOO_LARGE'):
        from iac.agent.runner import run_single
        analysis = run_single(result, 'groq', 'llama-3.1-8b-instant', None, 'key')
        assert analysis is None


# ---------------------------------------------------------------------------
# _parse_retry_after
# ---------------------------------------------------------------------------


def test_parse_retry_after_groq():
    """Parse do tempo de espera da mensagem 429 do Groq."""
    from iac.integrations.groq import _parse_retry_after
    assert _parse_retry_after('Please try again in 25.08s') == pytest.approx(26.08, abs=0.1)


def test_parse_retry_after_sem_match():
    """Sem tempo na mensagem, retorna default."""
    from iac.integrations.groq import _parse_retry_after
    assert _parse_retry_after('Rate limit exceeded') == 30.0


def test_parse_retry_after_413():
    """413 sem retry time, retorna 60s."""
    from iac.integrations.groq import _parse_retry_after
    assert _parse_retry_after('Request too large for model') == 60.0
