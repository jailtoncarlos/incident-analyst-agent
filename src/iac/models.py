"""Contratos de dados — Pydantic models para todas as camadas.

Define os tipos de entrada e saída de cada camada do pipeline:
    Classification → InvestigationContext → StructuralAnalysis → DeepModel → AnalysisResult

Princípio 3 — Contract-First: substituir dicts soltos por models tipados.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Camada 1: Classifier
# ---------------------------------------------------------------------------


class Classification(BaseModel):
    """Metadados extraídos da issue pelo classifier (sem LLM)."""

    origem: str | None = Field(None, description='erro-sistema | sentry | reporte-manual')
    app: str | None = Field(None, description='App do framework (ex: loja)')
    view: str | None = Field(None, description='FQN da view (ex: loja.views.detalhe_produto)')
    url_erro: str | None = Field(None, description='URL com erro reportada')
    interessado: str | None = Field(None, description='Nome + matrícula do interessado')
    erro_id: str | None = Field(None, description='ID do erro no sistema (ex: 9645)')
    descricao_usuario: str | None = Field(None, description='Texto livre do usuário')
    sentry_url: str | None = Field(None, description='URL do Sentry se presente')
    traceback: str | None = Field(None, description='Traceback/stacktrace extraído')
    tipo_sugerido: str | None = Field(None, description='tipo::* sugerido (sentry=bug)')
    labels_sugeridos: list[str] = Field(default_factory=list, description='Labels a aplicar na issue')


# ---------------------------------------------------------------------------
# Camada 2: Orchestrator
# ---------------------------------------------------------------------------


class Reference(BaseModel):
    """Referência a um método/model/form seguido pelo orchestrator."""

    key: str = Field(description='FQN da referência (ex: app.models.Model.method)')
    call: str = Field(description='Call original na view (ex: chamado.get_permissoes)')
    app: str = Field(description='App da referência')
    kind: str = Field(description='Tipo: models, forms, views, admin')
    name: str = Field(description='Nome do componente')
    method: str | None = Field(None, description='Nome do método (se method_call)')
    file: str = Field(description='Arquivo relativo')
    line: int = Field(0, description='Linha no arquivo')
    method_line: int | None = Field(None, description='Linha do método (se disponível)')
    source: str | None = Field(None, description='Código-fonte extraído')


class InvestigationContext(BaseModel):
    """Contexto de código navegado pelo orchestrator."""

    url: str | None = None
    description: str | None = None
    traceback: str | None = None
    app: str | None = None
    view_name: str | None = None
    view_file: str | None = None
    view_line: int | None = None
    url_pattern: str | None = None
    view_source: str | None = None
    calls: list[str] = Field(default_factory=list)
    references: list[Reference] = Field(default_factory=list)
    imports: list[dict] = Field(default_factory=list)
    traceback_parsed: list[dict] | None = None
    steps_used: int = 0
    context_chars: int = 0
    status: str = 'incomplete'


# ---------------------------------------------------------------------------
# Camada 3: Análise estrutural
# ---------------------------------------------------------------------------


class FlowStep(BaseModel):
    """Passo no fluxo de interação (aresta do grafo)."""

    from_: str = Field(alias='from', description='Origem')
    to: str = Field(description='Destino')
    type: str = Field(description='Tipo de aresta (url_resolves, model_usage, etc.)')

    model_config = {'populate_by_name': True}


class StructuralAnalysis(BaseModel):
    """Análise estrutural — componentes e fluxo da view."""

    app: str | None = None
    rota: str | None = None
    view: str | None = None
    file: str | None = None
    line: int | None = None
    origem: str | None = None
    erro_id: str | None = None
    interessado: str | None = None
    descricao_usuario: str | None = None
    tipo_sugerido: str | None = None
    models: list[str] = Field(default_factory=list)
    forms: list[str] = Field(default_factory=list)
    templates: list[str] = Field(default_factory=list)
    admin: list[str] = Field(default_factory=list)
    related_models: list[str] = Field(default_factory=list)
    flow: list[FlowStep] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Camada 4: Análise profunda
# ---------------------------------------------------------------------------


class DeepModel(BaseModel):
    """Model navegado em profundidade via FKs."""

    fqn: str = Field(description='FQN do model (ex: app.models.Model)')
    depth: int = Field(0, description='Nível de profundidade (0=raiz)')
    file: str = Field('', description='Arquivo relativo')
    line: int = Field(0, description='Linha no arquivo')
    fields: list[str] = Field(default_factory=list)
    methods: dict[str, dict] = Field(default_factory=dict, description='Métodos com código')
    method_names: list[str] | None = Field(None, description='Nomes dos métodos (modo compacto)')
    constants: dict[str, str] = Field(default_factory=dict, description='Constantes UPPER_CASE')
    fk_targets: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Resultado final
# ---------------------------------------------------------------------------


class ModelProfile(BaseModel):
    """Perfil de contexto por tamanho de modelo LLM."""

    max_steps: int = 10
    max_context_chars: int = 15000
    max_refs: int = 6
    deep_max_context_chars: int = 10000
    deep_max_depth: int = 2
    deep_include_methods: bool = True


class AnalysisResult(BaseModel):
    """Resultado completo de analyze_issue()."""

    classification: Classification
    context: InvestigationContext
    structural: StructuralAnalysis
    deep: list[DeepModel] = Field(default_factory=list)
    profile: ModelProfile = Field(default_factory=ModelProfile)
