# Prompt — Catálogo comparativo de LLMs via API (2026)

> Uso: rode este prompt em um LLM com **web search habilitado** (Claude Code com `WebSearch`, Codex com `--search`, ChatGPT/Perplexity/Gemini web).
> Comando sugerido:
> ```bash
> claude -p "$(cat docs/prompt-catalogo-llms-2026.md)" \
>   --allowed-tools "WebSearch,WebFetch" \
>   > docs/catalogo-llms-2026.md
> ```

---

Você é um analista técnico especializado em LLMs. Produza um **relatório em Markdown** (pt-BR) com análise profunda e comparativa de todas as LLMs relevantes disponíveis via API em 2026, cobrindo opções gratuitas, de baixo custo e premium.

## Contexto do projeto (IAC — Incident Analyst Agent)

- Ferramenta CLI que analisa issues do GitLab/GitHub (stack traces, logs, código Django/Python) e gera relatórios técnicos.
- Consumo típico: **3–6 requests por issue**, **~10K tokens por análise** (input majoritariamente código + stack trace; output estruturado em Markdown).
- Volume alvo: **~150 issues por milestone**, ~4 milestones/ano.
- Modos de uso: `single` (2 req), `multi` (3–4 req), `loop` (4–6 req).
- Hoje integrados: Ollama (local), Groq, DeepSeek, Gemini. Pendentes: OpenAI, Anthropic.

## Escopo obrigatório

Inclua **no mínimo** estes provedores/famílias (não omita nenhum):

- **OpenAI:** GPT-4o, GPT-4o mini, GPT-4.1, o3, o3-mini, o1, Codex
- **Anthropic:** Claude Opus 4.6, Sonnet 4.6, Haiku 4.5
- **Google:** Gemini 2.5 Pro, 2.5 Flash, 2.0 Flash
- **Meta:** Llama 3.3 70B, Llama 3.1 (405B/70B/8B), Llama 4 (Scout/Maverick)
- **Mistral AI:** Mistral Large, Medium, Small, Mixtral 8x7B, 8x22B, Codestral
- **DeepSeek:** V3, V3.1, Coder, Reasoner (R1)
- **Alibaba Qwen:** Qwen 2.5 (72B/32B/14B/7B), Qwen3 (32B/235B), Qwen-Coder, QwQ
- **MiniMax:** abab6.5, M1 (reasoning)
- **xAI:** Grok 2, Grok 3, Grok 4 (se lançado)
- **Cohere:** Command R+, Command R
- **AI21:** Jamba 1.5 Large/Mini
- **Provedores de inferência multi-modelo:** Groq, Together.ai, Fireworks, OpenRouter, HuggingFace Inference, Replicate, Perplexity API
- **Chineses adicionais:** Zhipu (GLM-4), Moonshot (Kimi), 01.AI (Yi)

## Categorias de classificação

Organize os modelos em **todas** estas dimensões (um modelo pode aparecer em várias):

1. **Por faixa de custo:** Gratuito permanente · Crédito inicial · Baixo custo (<$1/1M tokens) · Médio · Premium
2. **Por especialização:** General-purpose · Code-specialized · Reasoning · Long-context (>200K) · Multimodal (visão) · Tool-use/Agentic
3. **Por proveniência:** Proprietário (closed) · Open-weights (pesos públicos) · Open-source completo
4. **Por origem geográfica:** EUA · Europa · China · Outros (contexto regulatório/LGPD)
5. **Por tamanho:** Small (<10B) · Medium (10–70B) · Large (70–200B) · Frontier (>200B ou closed-frontier)

## Dados obrigatórios por modelo

Para cada modelo, apresente:

- Nome e provedor
- Data de lançamento / última atualização
- **Preço input / output por 1M tokens** (USD, valores oficiais atuais — **cite a fonte com link** ao final da seção)
- **Limites do tier gratuito** (req/min, req/dia, crédito inicial)
- **Context window** (tokens)
- **Tamanho** (parâmetros, se público) e **arquitetura** (dense/MoE)
- **Latência típica** observada (tokens/s ou s por resposta de 1K tokens)
- **Qualidade** (★ de 1 a 5) em: raciocínio geral, código, instrução, long-context
- Pontuações em benchmarks relevantes (MMLU, HumanEval, SWE-bench, LMSys Arena) quando disponíveis
- **Forças e fraquezas** em 1–2 linhas cada
- Compatibilidade de API (OpenAI-compatible? nativa?)

## Análise comparativa obrigatória

Inclua estas seções/tabelas:

1. **Tabela mestre** com todas as LLMs listadas, ordenável por custo e qualidade.
2. **Custo estimado por análise IAC** (~10K tokens, ratio input/output 4:1) em USD e BRL.
3. **Custo mensal projetado** para 150, 500 e 1.500 issues/mês.
4. **Gráfico ASCII custo × qualidade** (log scale no custo).
5. **Ranking por caso de uso:**
   - Bateria de testes automatizada (volume, sem custo)
   - Produção volume baixo (<10 issues/dia)
   - Produção volume médio (150 issues/milestone)
   - Produção volume alto (1000+ issues/mês)
   - Casos críticos (máxima qualidade, custo não importa)
   - Ambiente com LGPD/dados sensíveis (on-premise ou região específica)
6. **Matriz de decisão** com pesos: custo (30%), qualidade código/stack trace (30%), latência (15%), context window (10%), maturidade API (10%), compliance (5%).
7. **Riscos e caveats:** mudanças de preço recentes, modelos deprecated, provedores instáveis, restrições geográficas/LGPD.

## Recomendações finais

- Top 3 para cada caso de uso (dev, bateria, produção, premium).
- Estratégia **multi-backend** (qual modelo usar como primário e qual como fallback).
- Modelos a **evitar** no contexto IAC e por quê.

## Requisitos de formato

- Markdown puro, sem HTML.
- Cabeçalhos hierárquicos (`#`, `##`, `###`).
- Tabelas compactas, colunas alinhadas.
- Todos os preços e limites com **link para a fonte oficial** ao final de cada bloco.
- Ao final, uma seção **"Metodologia e fontes"** listando como os dados foram coletados e a data de referência.
- Se algum dado não for verificável, marque explicitamente com `⚠️ não verificado` em vez de inventar.

Produza o relatório completo agora.
