# incident-analyst-agent

Agente de análise técnica de incidentes de software, capaz de investigar código, reconstruir fluxos, simular cenários e propor resolução com resposta operacional estruturada.

## Instalação

```bash
pip install incident-analyst-agent
```

Ou para desenvolvimento:

```bash
git clone https://github.com/jailtoncarlos/incident-analyst-agent.git
cd incident-analyst-agent
pip install -e ".[dev]"
pre-commit install
```

## Uso

```bash
# Inspecionar o repositório
cd /path/to/my-django-project
iac init

# Ver estatísticas da inspeção
iac init --stats

# Re-inspecionar após mudanças no código
iac init --force

# Analisar um incidente por URL da issue
iac analyze --issue-url https://gitlab.example.com/project/-/issues/123

# Analisar por descrição
iac analyze --description "Error 500 em /api/users/"

# Com LLM (Ollama local)
iac analyze --llm ollama --model qwen2.5-coder:7b \
    --issue-url https://gitlab.example.com/project/-/issues/123
```

## Inspeção do repositório (`iac init`)

Ao executar `iac init`, o agente inspeciona o repositório e gera três arquivos no diretório `.iac/`:

### `.iac/project.json` — Identificação do projeto

Metadados básicos: framework detectado, versão Python, módulo de settings.

```json
{
  "framework": "django",
  "settings_module": "myproject.settings",
  "python_version": ">=3.11",
  "inspected_at": "2026-04-07T16:01:49Z"
}
```

### `.iac/structure.json` — O que existe (inventário)

Lista todos os componentes do projeto e seus atributos. Responde a perguntas como:
*"Quais views o app centralservicos tem? Quais campos o model Chamado possui? Quais métodos ele expõe?"*

```json
{
  "apps": {
    "centralservicos": {
      "views": {
        "visualizar_chamado": {
          "file": "centralservicos/views.py",
          "line": 488,
          "type": "function",
          "calls": ["Chamado.objects.filter", "chamado.get_permissoes"],
          "renders": ["chamado.html"]
        }
      },
      "models": {
        "Chamado": {
          "file": "centralservicos/models.py",
          "line": 24,
          "fields": ["servico", "status", "data_limite_atendimento"],
          "methods": ["resolver_chamado", "get_tempo_ultrapassado"]
        }
      },
      "forms": { ... },
      "urls": [
        {"pattern": "/centralservicos/chamado/<int:id>/", "view": "views.visualizar_chamado"}
      ],
      "templates": ["chamado.html", "abrir_chamado.html"]
    }
  }
}
```

### `.iac/graph.json` — Como se conecta (mapa de relações)

Grafo de dependências entre componentes. Responde a perguntas como:
*"O que a view visualizar_chamado usa? Qual model ela acessa? Qual template renderiza?"*

```json
{
  "edges": [
    {
      "from": "centralservicos/urls:/centralservicos/chamado/<int:id>/",
      "to": "centralservicos.views.visualizar_chamado",
      "type": "url_resolves"
    },
    {
      "from": "centralservicos.views.visualizar_chamado",
      "to": "centralservicos.models.Chamado",
      "type": "model_usage"
    },
    {
      "from": "centralservicos.views.visualizar_chamado",
      "to": "centralservicos.models.Chamado.get_tempo_ultrapassado",
      "type": "method_call"
    },
    {
      "from": "centralservicos.views.visualizar_chamado",
      "to": "centralservicos/templates/chamado.html",
      "type": "renders"
    }
  ]
}
```

**Tipos de aresta:**

| Tipo | Significado | Exemplo |
|------|------------|---------|
| `url_resolves` | URL aponta para view | `/chamado/<id>/` → `visualizar_chamado` |
| `model_usage` | View usa model | `visualizar_chamado` → `Chamado` |
| `method_call` | View chama método do model | `visualizar_chamado` → `Chamado.get_tempo_ultrapassado` |
| `form_usage` | View usa form | `visualizar_chamado` → `ComunicacaoFormFactory` |
| `form_model` | Form referencia model (Meta.model) | `ItemForm` → `Item` |
| `renders` | View renderiza template | `visualizar_chamado` → `chamado.html` |
| `field_definition` | Model define campo | `Chamado` → `Chamado.status` |

### Diferença entre structure.json e graph.json

| | `structure.json` | `graph.json` |
|---|---|---|
| **Pergunta que responde** | *O que existe?* | *Como se conecta?* |
| **Conteúdo** | Inventário de componentes com atributos | Arestas tipadas entre componentes |
| **Uso pelo agente** | Localizar e ler um componente | Navegar o fluxo a partir de um ponto de entrada |
| **Analogia** | Lista de peças de um motor | Diagrama de montagem do motor |

Quando o agente recebe um incidente, ele usa `graph.json` para descobrir **o caminho** (URL → view → model → método) e `structure.json` para **abrir e ler** cada componente no caminho.

### Exemplo de saída (`iac init --stats`)

```
Framework: django
Inspecionado em: 2026-04-07T16:01:49
Apps: 94
Views: 3573
Models: 1852
Forms: 2102
URLs: 2223
Templates: 2121
Arestas no grafo: 33244
  field_definition: 11798
  form_model: 959
  form_usage: 1623
  method_call: 14466
  model_usage: 2538
  renders: 44
  url_resolves: 1816
```

## Arquitetura

O agente opera em três camadas:

1. **Inspeção estrutural** — Mapeia o repositório via AST, gerando `structure.json` e `graph.json`
2. **Recuperação híbrida** — Encontra trechos de código relevantes ao incidente navegando pelo grafo
3. **Orquestração do agente** — LLM investiga o código com ferramentas, classifica e propõe resolução

### Fluxo

```
1. iac init       → Gera .iac/ (project.json + structure.json + graph.json)

2. iac analyze    → Recebe incidente (issue URL ou descrição)
                  → Parser extrai: app, view, URL, traceback, interessado
                  → Agente navega pelo grafo: view → models → forms → templates
                  → Classifica: bug / configuração / dados / prazo / não-é-erro
                  → Simula no banco de teste (se configurado)
                  → Gera resposta operacional estruturada
```

### Modos de operação

| Modo | Requisito | Descrição |
|------|-----------|-----------|
| Agente | LLM com tool calling (Gemini, >= 14B) | LLM navega autonomamente pelo grafo, decide o que investigar |
| Dirigido | Qualquer LLM | Navegação em ordem fixa (view → models → forms), prompts encadeados |

## Frameworks suportados

- **Django** (implementado)
- Flask (planejado)
- FastAPI (planejado)

## Integrações

- **Issue trackers:** GitLab, GitHub
- **LLM backends:** Ollama (local), Gemini (API)

## Desenvolvimento

```bash
# Rodar testes
pytest

# Lint
ruff check src/ tests/
ruff format src/ tests/

# Pre-commit
pre-commit run --all-files
```

## Licença

MIT
