"""Configurações centralizadas — Pydantic Settings.

Princípio 1 — Explícito sobre Implícito:
todas as configurações tipadas, com defaults explícitos e validação.

Hierarquia: defaults → .env → variáveis de ambiente → CLI args.

Variáveis de ambiente aceitas:
    GITLAB_TOKEN        — Access token do GitLab
    IAC_LLM_BACKEND     — Backend LLM (ollama, groq, deepseek, gemini)
    IAC_LLM_MODEL       — Nome do modelo
    IAC_LLM_URL         — Endpoint da API
    IAC_LLM_KEY         — API key genérica (fallback)
    IAC_LLM_RATE_DELAY  — Delay entre chamadas em segundos (0 = sem delay)
    IAC_LLM_MAX_RETRIES — Máximo de retries em rate limit (default: 3)
    IAC_ANALYZE_MODE    — Modo de análise (auto, single, multi, loop)
    GROQ_API_KEY        — API key do Groq
    DEEPSEEK_API_KEY    — API key do DeepSeek
    GEMINI_API_KEY      — API key do Google Gemini
"""

from __future__ import annotations

import os

from pydantic import Field
from pydantic_settings import BaseSettings


def _resolve_llm_key() -> str | None:
    """Resolve API key pelo backend configurado, ou fallback genérico."""
    backend = os.environ.get('IAC_LLM_BACKEND', '')
    backend_keys = {'groq': 'GROQ_API_KEY', 'deepseek': 'DEEPSEEK_API_KEY', 'gemini': 'GEMINI_API_KEY'}
    if backend in backend_keys:
        return os.environ.get(backend_keys[backend]) or os.environ.get('IAC_LLM_KEY')
    return os.environ.get('GROQ_API_KEY') or os.environ.get('DEEPSEEK_API_KEY') or os.environ.get('GEMINI_API_KEY') or os.environ.get('IAC_LLM_KEY')


def _resolve_gitlab_token() -> str | None:
    """Resolve token pela ordem: GITLAB_TOKEN → IAC_GITLAB_TOKEN."""
    return os.environ.get('GITLAB_TOKEN') or os.environ.get('IAC_GITLAB_TOKEN')


class LLMSettings(BaseSettings):
    """Configurações do backend LLM."""

    backend: str = Field('ollama', description='Backend: ollama | groq | deepseek | gemini')
    model: str = Field('qwen2.5:7b', description='Nome do modelo')
    url: str = Field('http://localhost:11434/v1/chat/completions', description='Endpoint da API')
    key: str | None = Field(default_factory=_resolve_llm_key, description='API key (GROQ_API_KEY, DEEPSEEK_API_KEY, GEMINI_API_KEY ou IAC_LLM_KEY)')
    max_tokens: int = Field(4000, description='Máximo de tokens na resposta')
    temperature: float = Field(0.2, description='Temperatura do modelo')
    timeout: int = Field(1200, description='Timeout em segundos')
    rate_delay: int = Field(0, description='Delay entre chamadas em segundos (0 = sem delay)')
    max_retries: int = Field(3, description='Máximo de retries em rate limit')

    model_config = {'env_prefix': 'IAC_LLM_'}


class GitLabSettings(BaseSettings):
    """Configurações do GitLab."""

    url: str | None = Field(None, description='URL do GitLab')
    token: str | None = Field(default_factory=_resolve_gitlab_token, description='Access token (GITLAB_TOKEN ou IAC_GITLAB_TOKEN)')
    project_id: str | None = Field(None, description='ID do projeto')

    model_config = {'env_prefix': 'IAC_GITLAB_'}


class AnalyzeSettings(BaseSettings):
    """Configurações do comando analyze."""

    mode: str = Field('auto', description='Modo: auto | single | multi | loop')

    model_config = {'env_prefix': 'IAC_ANALYZE_'}


class AppSettings(BaseSettings):
    """Configuração global da aplicação."""

    llm: LLMSettings = Field(default_factory=LLMSettings)
    gitlab: GitLabSettings = Field(default_factory=GitLabSettings)
    analyze: AnalyzeSettings = Field(default_factory=AnalyzeSettings)

    model_config = {'env_prefix': 'IAC_'}
