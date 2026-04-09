# Arquitetura — Incident Analyst Agent (IAC)

## Visão geral

```mermaid
graph TD
    A[Issue GitLab/GitHub] --> B[iac analyze]
    B --> C1[Camada 1: Classifier]
    B --> C2[Camada 2: Orchestrator]
    B --> C3[Camada 3: Structural]
    B --> C4[Camada 4: Deep]
    C1 --> D[Prompt Builder]
    C2 --> D
    C3 --> D
    C4 --> D
    D --> E[LLM - Ollama/Gemini]
    E --> F[Classificação + Análise]
    F --> G[Resposta ao Usuário]
```

## Pipeline de análise

```mermaid
sequenceDiagram
    participant CLI as iac analyze
    participant CL as Classifier
    participant OR as Orchestrator
    participant ST as Structural
    participant DP as Deep
    participant PR as Prompts
    participant LLM as LLM

    CLI->>CL: title + description
    CL-->>CLI: Classification (origem, app, interessado, labels)

    CLI->>OR: url + description + .iac/
    OR-->>CLI: InvestigationContext (view, calls, refs, source)

    CLI->>ST: classification + context + graph
    ST-->>CLI: StructuralAnalysis (models, forms, templates, flow)

    CLI->>DP: context + graph + FKs
    DP-->>CLI: DeepModel[] (fields, constants, methods)

    CLI->>PR: AnalysisResult
    PR-->>CLI: prompt (investigation)

    CLI->>LLM: prompt 1
    LLM-->>CLI: pedidos de investigação

    CLI->>PR: evidence + view code
    PR-->>CLI: prompt (análise)

    CLI->>LLM: prompt 2
    LLM-->>CLI: classificação + análise

    CLI->>LLM: prompt 3 (resposta)
    LLM-->>CLI: rascunho "Prezado(a)..."
```

## Estrutura do projeto

```
src/iac/
├── __init__.py
├── models.py                  # Contratos de dados (Pydantic)
├── cli.py                     # Entry point CLI
├── config/
│   ├── settings.py            # Load/save .iac/ files
│   ├── app_settings.py        # AppSettings (Pydantic Settings)
│   └── tracer.py              # (deprecado)
├── inspector/
│   ├── detector.py            # Detecta framework (Django/Flask)
│   ├── django.py              # Parser AST Django
│   ├── structure.py           # Gera structure.json
│   └── graph.py               # Gera graph.json
├── agent/
│   ├── tools.py               # 7 ferramentas de navegação
│   ├── orchestrator.py        # analyze_issue + investigate + deep
│   └── prompts.py             # Prompts para LLM
├── analyzer/
│   ├── classifier.py          # Classificação sem LLM
│   └── simulator.py           # (stub)
├── responder/
│   └── generator.py           # (stub)
├── integrations/
│   ├── gitlab.py              # Client GitLab
│   ├── ollama.py              # Backend Ollama
│   └── gemini.py              # Backend Gemini
└── diagram/
    ├── generator.py            # Dados para D3.js
    └── templates/
        ├── overview.html
        └── app_detail.html
```

## Artefatos gerados (.iac/)

```
.iac/
├── project.json       # Framework, versão, settings
├── structure.json     # Mapa de apps/views/models/forms/admin/urls
├── graph.json         # Grafo de dependências (arestas tipadas)
├── config.yaml        # Configurações do projeto (LLM, GitLab)
├── logs/
│   └── iac.log        # Log DEBUG completo
└── diagrams/
    ├── overview.html   # Apps como nós
    └── *.html          # Detalhe por app
```

## Tipos de aresta no grafo

| Tipo | De | Para | Exemplo |
|------|-----|------|---------|
| `url_resolves` | URL pattern | View | `/chamado/<id>/` → `visualizar_chamado` |
| `model_usage` | View | Model | `view` → `Chamado` |
| `method_call` | View | Model.method | `view` → `Chamado.get_permissoes` |
| `form_usage` | View | Form | `view` → `ComunicacaoFormFactory` |
| `form_model` | Form | Model | `ItemForm` → `Item` (Meta.model) |
| `renders` | View | Template | `view` → `chamado.html` |
| `field_definition` | Model | Field | `Chamado` → `Chamado.status` |
| `model_relation` | Model | Model | `Chamado` → `Servico` (FK) |
| `admin_register` | Admin | Model | `ChamadoAdmin` → `Chamado` |
| `admin_form` | Admin | Form | `ProdutoAdmin` → `ProdutoForm` |
| `admin_inline` | Admin | Admin | `Admin` → `InlineAdmin` |

## Perfis de contexto

| Perfil | Modelos | Prompt | Profundidade | Métodos |
|--------|---------|--------|-------------|---------|
| small | 7B | ~10K chars | 2 níveis | Nomes |
| medium | 14-32B | ~20K chars | 2 níveis | Código |
| large | 70B+/APIs | ~28K chars | 3 níveis | Código |
