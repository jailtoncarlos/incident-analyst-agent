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

# Analisar um incidente por URL da issue
iac analyze --issue-url https://gitlab.example.com/project/-/issues/123

# Analisar por descrição
iac analyze --description "Error 500 em /api/users/"

# Com LLM (Ollama local)
iac analyze --llm ollama --model qwen2.5-coder:7b \
    --issue-url https://gitlab.example.com/project/-/issues/123
```

## Arquitetura

O agente opera em três camadas:

1. **Inspeção estrutural** — Mapeia o repositório (apps, views, models, forms, URLs, templates) via AST
2. **Recuperação híbrida** — Encontra trechos de código relevantes ao incidente usando o mapa estrutural
3. **Orquestração do agente** — LLM investiga o código com ferramentas, classifica e propõe resolução

### Fluxo

```
1. iac init           → Gera .iac/project.json, structure.json, graph.json
2. iac analyze        → Parser da issue → Navegação no código → Classificação
                        → Simulação → Resolução → Resposta ao usuário
```

### Modos de operação

| Modo | Requisito | Descrição |
|------|-----------|-----------|
| Agente | LLM com tool calling (Gemini, >= 14B) | LLM navega autonomamente pelo código |
| Dirigido | Qualquer LLM | Navegação em ordem fixa, prompts encadeados |

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
