"""Configurações centralizadas — Pydantic Settings.

Princípio 1 — Explícito sobre Implícito:
todas as configurações tipadas, com defaults explícitos e validação.

Hierarquia: defaults → config.yaml → variáveis de ambiente → CLI args.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class LLMSettings(BaseSettings):
    """Configurações do backend LLM."""

    backend: str = Field('ollama', description='Backend: ollama | gemini')
    model: str = Field('qwen2.5:7b', description='Nome do modelo')
    url: str = Field('http://localhost:11434/v1/chat/completions', description='Endpoint da API')
    key: str | None = Field(None, description='API key (opcional para Ollama local)')
    max_tokens: int = Field(4000, description='Máximo de tokens na resposta')
    temperature: float = Field(0.2, description='Temperatura do modelo')
    timeout: int = Field(600, description='Timeout em segundos')

    model_config = {'env_prefix': 'IAC_LLM_'}


class GitLabSettings(BaseSettings):
    """Configurações do GitLab."""

    url: str | None = Field(None, description='URL do GitLab')
    token: str | None = Field(None, description='Access token')
    project_id: str | None = Field(None, description='ID do projeto')

    model_config = {'env_prefix': 'IAC_GITLAB_'}


class AnalyzeSettings(BaseSettings):
    """Configurações do comando analyze."""

    mode: str = Field('auto', description='Modo: auto | single | multi')

    model_config = {'env_prefix': 'IAC_ANALYZE_'}


class AppSettings(BaseSettings):
    """Configuração global da aplicação."""

    llm: LLMSettings = Field(default_factory=LLMSettings)
    gitlab: GitLabSettings = Field(default_factory=GitLabSettings)
    analyze: AnalyzeSettings = Field(default_factory=AnalyzeSettings)

    model_config = {'env_prefix': 'IAC_'}
