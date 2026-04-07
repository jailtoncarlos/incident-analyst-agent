# Estratégia de Inspeção de Repositório

Este documento descreve como o `iac init` inspeciona um repositório de código e constrói os artefatos que o agente usa para analisar incidentes.

## Visão geral

```mermaid
flowchart LR
    subgraph "iac init"
        A[Repositório] --> B[Etapa 1\nDetecção do framework]
        B --> C[Etapa 2\nMapa estrutural]
        C --> D[Etapa 3\nGrafo de dependências]
    end

    B --> P[".iac/project.json"]
    C --> S[".iac/structure.json"]
    D --> G[".iac/graph.json"]

    subgraph "iac analyze"
        S --> AG[Agente]
        G --> AG
        AG --> R[Análise do incidente]
    end
```

A inspeção gera três artefatos em `.iac/`, cada um com responsabilidade distinta:

| Artefato | Pergunta que responde | Tamanho típico |
|----------|----------------------|----------------|
| `project.json` | *Que tipo de projeto é?* | ~200 bytes |
| `structure.json` | *O que existe?* (inventário) | ~2-5 MB |
| `graph.json` | *Como se conecta?* (relações) | ~3-8 MB |

---

## Etapa 1 — Detecção do framework

```mermaid
flowchart TD
    A[Inspecionar diretório] --> B{manage.py existe?}
    B -->|Sim| C[Django]
    B -->|Não| D{app.py com Flask?}
    D -->|Sim| E[Flask]
    D -->|Não| F{main.py com FastAPI?}
    F -->|Sim| G[FastAPI]
    F -->|Não| H{pyproject.toml?}
    H -->|Sim| I[Python genérico]
    H -->|Não| J[Desconhecido]

    C --> K[Extrair settings_module\nde manage.py]
    K --> L[Extrair python_version\nde pyproject.toml]
    L --> M["Salvar project.json"]
```

**Saída:** `project.json`

```json
{
  "framework": "django",
  "settings_module": "suap.settings",
  "python_version": ">=3.14.3",
  "base_dir": "/opt/suap",
  "inspected_at": "2026-04-07T16:01:49Z"
}
```

---

## Etapa 2 — Mapa estrutural (structure.json)

O mapa estrutural é o **inventário** de todos os componentes do projeto. Para Django, a construção segue este fluxo:

```mermaid
flowchart TD
    A["Ler INSTALLED_APPS\n(settings.py)"] --> B[Listar apps]
    B --> C{Fallback: scan\ndiretórios com\nviews.py ou models.py}

    B --> D["Para cada app:"]
    C --> D

    D --> E["Parse views.py\n(AST)"]
    D --> F["Parse models.py\n(AST)"]
    D --> G["Parse forms.py\n(AST)"]
    D --> H["Parse urls.py\n(regex)"]
    D --> I["Glob templates/\n(*.html)"]

    E --> J[Funções: nome, arquivo, linha,\ncalls, renders]
    E --> K[Classes: nome, arquivo, linha,\ntemplate_name, métodos]
    F --> L[Classes: nome, arquivo, linha,\nfields, methods]
    G --> M[Classes: nome, arquivo, linha,\nMeta.model]
    H --> N[URL patterns: pattern, view]
    I --> O[Lista de templates .html]

    J --> P[structure.json]
    K --> P
    L --> P
    M --> P
    N --> P
    O --> P
```

### Extração por componente

| Componente | Método | O que extrai |
|-----------|--------|-------------|
| **Views** | `ast.parse` → `FunctionDef`, `ClassDef` | nome, arquivo:linha, chamadas internas, templates renderizados |
| **Models** | `ast.parse` → `ClassDef` com campos `*Field` | nome, arquivo:linha, campos (CharField, FK, etc.), métodos públicos |
| **Forms** | `ast.parse` → `ClassDef` com `class Meta` | nome, arquivo:linha, Meta.model referenciado |
| **URLs** | Regex em `urls.py` | padrão de URL, view associada |
| **Templates** | `glob('templates/**/*.html')` | lista de arquivos .html |

### Resolução de renders (view → template)

A resolução de qual template uma view usa é feita em 3 níveis complementares:

```mermaid
flowchart TD
    A[View] --> B{Nível 1:\nString literal no código?}
    B -->|"render(request, 'chamado.html')"| C["✅ Mapeado"]
    B -->|Não| D{Nível 1b:\ntemplate_name em classe?}
    D -->|"template_name = 'chamado.html'"| C
    D -->|Não| E{Nível 2:\nConvenção Django?}
    E -->|"view 'visualizar_chamado'\n→ 'visualizar_chamado.html' existe?"| C
    E -->|Não| F{Nível 3:\nReferência inversa?}
    F -->|"template tem\n{% url 'visualizar_chamado' %}"| C
    F -->|Não| G["❌ Sem mapeamento\n(agente usa grep em runtime)"]
```

**Nível 1 — Extração direta (AST):**
Busca strings literais em chamadas `render()`, `render_to_string()`, `TemplateResponse()`, `get_template()` e atribuições `template_name = '...'` (class-based views).

**Nível 2 — Convenção Django (heurística):**
Cruza nome da view com templates existentes:
- `visualizar_chamado` → `visualizar_chamado.html`
- `visualizar_chamado` → `centralservicos/visualizar_chamado.html`
- `visualizar_chamado` → `chamado.html` (sem prefixo `visualizar_`)

**Nível 3 — Referência inversa (templates):**
Percorre os templates buscando `{% url 'view_name' %}` e mapeia na direção inversa: o template referencia a view, logo a view provavelmente renderiza (ou está relacionada a) esse template.

**Cobertura observada (SUAP, 2121 templates):**

| Nível | renders detectados | Cobertura |
|-------|-------------------|-----------|
| Apenas Nível 1 | 44 | 2% |
| + Nível 1b (class attrs) | ~90 | 4% |
| + Nível 2 (convenção) | ~600 | 28% |
| + Nível 3 (inverso) | **1.280** | **60%** |

---

## Etapa 3 — Grafo de dependências (graph.json)

O grafo é construído percorrendo o `structure.json` e criando arestas tipadas entre componentes.

```mermaid
graph TD
    URL["URL pattern\n/chamado/&lt;id&gt;/"]
    VIEW["View\nvisualizar_chamado"]
    MODEL["Model\nChamado"]
    METHOD["Method\nget_tempo_ultrapassado"]
    FIELD["Field\ndata_limite_atendimento"]
    FORM["Form\nComunicacaoFormFactory"]
    TEMPLATE["Template\nchamado.html"]

    URL -->|url_resolves| VIEW
    VIEW -->|model_usage| MODEL
    VIEW -->|method_call| METHOD
    VIEW -->|form_usage| FORM
    VIEW -->|renders| TEMPLATE
    MODEL -->|field_definition| FIELD
    MODEL -->|method_definition| METHOD
    FORM -->|form_model| MODEL
```

### Tipos de aresta

| Tipo | De | Para | Como é detectado |
|------|-----|------|-----------------|
| `url_resolves` | URL pattern | View | Parse de `urls.py` |
| `model_usage` | View | Model | Chamadas `Model.objects.*` no corpo da view |
| `method_call` | View | Model.method | Chamadas `obj.method()` onde method existe no model |
| `form_usage` | View | Form | Instanciação de Form no corpo da view |
| `form_model` | Form | Model | `class Meta: model = Model` no form |
| `renders` | View | Template | 3 níveis de resolução (ver acima) |
| `field_definition` | Model | Model.field | Campos `*Field` no corpo da classe |

### Como o agente navega o grafo

Quando o agente recebe um incidente com URL `/centralservicos/chamado/516785/`:

```mermaid
sequenceDiagram
    participant Issue as Incidente
    participant Graph as graph.json
    participant Structure as structure.json
    participant Code as Código fonte

    Issue->>Graph: URL /centralservicos/chamado/<id>/
    Graph->>Graph: url_resolves → visualizar_chamado
    Graph->>Structure: Onde está visualizar_chamado?
    Structure->>Code: centralservicos/views.py:488
    Note over Code: Agente lê a view

    Graph->>Graph: method_call → Chamado.get_tempo_ultrapassado
    Graph->>Structure: Onde está get_tempo_ultrapassado?
    Structure->>Code: centralservicos/models.py:1645
    Note over Code: Agente lê o método

    Graph->>Graph: renders → chamado.html
    Graph->>Structure: Onde está chamado.html?
    Structure->>Code: centralservicos/templates/chamado.html
    Note over Code: Agente lê o template
```

O grafo permite que o agente **navegue sem grep** — ele sabe exatamente quais componentes visitar e em qual ordem.

---

## Números de referência (SUAP)

| Métrica | Valor | Tempo |
|---------|-------|-------|
| Apps mapeados | 94 | — |
| Views | 3.573 | — |
| Models | 1.852 | — |
| Forms | 2.102 | — |
| URLs | 2.223 | — |
| Templates | 2.121 | — |
| Arestas no grafo | 34.480 | — |
| URL → View resolvidas | 1.816 (82%) | — |
| View → Template resolvidas | 1.280 (60%) | — |
| **Tempo total de inspeção** | — | **4 segundos** |
| **Tamanho do .iac/** | 8.5 MB | — |

---

## Extensibilidade

O inspector é plugável por framework. Cada framework tem seu parser em `iac/inspector/`:

```
iac/inspector/
├── detector.py      # Detecta o framework (compartilhado)
├── structure.py      # Despacha para o parser correto
├── graph.py          # Constrói grafo (compartilhado)
├── django.py         # Parser Django (implementado)
├── flask.py          # Parser Flask (futuro)
└── fastapi.py        # Parser FastAPI (futuro)
```

Todos os parsers produzem o mesmo formato de `structure.json` — o grafo e o agente trabalham sobre a estrutura padronizada, independente do framework.
