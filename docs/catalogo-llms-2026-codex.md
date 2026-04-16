Relatório gerado em [docs/catalogo-llms-2026-codex.md](/home/jailton/workspace/incident-analyst-agent/docs/catalogo-llms-2026-codex.md).

O arquivo tem 489 linhas e cobre o escopo pedido: tabela mestre, classificação por custo/especialização/proveniência/origem/tamanho, custos por análise IAC, projeções mensais, gráfico ASCII, rankings por caso de uso, matriz ponderada, riscos, recomendações e metodologia. Também marquei explicitamente com `⚠️ não verificado` os pontos em que não encontrei dado oficial confiável, especialmente preços diretos de alguns modelos open-weights ou legados.

Usei web search e deixei as fontes no próprio relatório, priorizando páginas oficiais como OpenAI, Anthropic, Google Gemini, DeepSeek, Mistral, xAI, Cohere, AI21, Alibaba/Qwen, MiniMax, Groq, Together, Fireworks, OpenRouter, Hugging Face, Replicate e Perplexity. O arquivo está não rastreado no Git (`?? docs/catalogo-llms-2026-codex.md`).
 / Qwen3 32B | Custo por análise abaixo de US$0,004 em alguns casos; latência boa. |
| Produção balanceada | Gemini 2.5 Flash | GPT-4.1 mini / Haiku 4.5 | Bom código, multimodal, 1M contexto, preço baixo. |
| Produção premium | Claude Sonnet 4.6 | GPT-4.1 / o3 / Gemini 2.5 Pro | Melhor equilíbrio para código, debugging e relatórios longos. |
| Casos críticos | Claude Opus 4.6 | o3 / Gemini 2.5 Pro | Máxima qualidade, custo secundário. |

## Premissas e caveats

- Modelos open-weights não têm preço oficial único: o custo depende do provedor, GPU, região e quantização. Quando não há preço oficial do criador do modelo, uso preço de provedor hospedado e marco isso.
- “Gratuito permanente” raramente significa produção grátis. Em geral é quota pequena, roteamento variável ou uso sujeito a coleta de dados.
- Latência pública é inconsistente. Uso números oficiais quando existem; caso contrário marco `⚠️ não verificado`.
- “Open-source completo” é raro. Llama, Qwen, DeepSeek, Mistral e Kimi têm pesos públicos ou licenças abertas, mas nem sempre OSI-open-source.
- Preços mudam com frequência; os riscos são maiores em agregadores e modelos “preview”.

## Fórmula de custo IAC

```text
custo_por_analise = (0,008 * preço_input_1M) + (0,002 * preço_output_1M)
custo_BRL = custo_USD * 4,9905
```

## Tabela mestre

Legenda de qualidade: ★ fraco, ★★ aceitável, ★★★ bom, ★★★★ muito bom, ★★★★★ frontier.
Preço I/O em USD por 1M tokens. Informações complementares (arquitetura, API, observações) logo abaixo de cada sub-tabela.
API: `OA` = OpenAI-compatible, `Nativa` = SDK/API própria.

### OpenAI (EUA)

| Modelo | Perfil | Contexto | Preço I/O | IAC US$ | Qual. |
|---|---|---:|---:|---:|---:|
| GPT-4o | multimodal | 128K | 2.50 / 10.00 | 0.0400 | ★★★★ |
| GPT-4o mini | baixo custo | 128K | 0.15 / 0.60 | 0.0024 | ★★★ |
| GPT-4.1 | código | 1.05M | 2.00 / 8.00 | 0.0320 | ★★★★ |
| o3 | reasoning | ⚠️ | 2.00 / 8.00 | 0.0320 | ★★★★★ |
| o3-mini | reasoning barato | ⚠️ | 1.10 / 4.40 | 0.0176 | ★★★★ |
| o1 | reasoning legado | ⚠️ | 15.00 / 60.00 | 0.2400 | ★★★★ |
| Codex mini / GPT Codex | code-specialized | 256K-? | 1.50 / 6.00 | 0.0240 | ★★★★ |

**Complementares:**
- **GPT-4o** — closed/dense · API Nativa/OA · Legado útil; API mantida, ChatGPT aposentou.
- **GPT-4o mini** — closed · API Nativa/OA · Excelente triagem barata.
- **GPT-4.1** — closed · API Nativa/OA · Forte em código; SWE-bench Verified 54,6% divulgado.
- **o3** — closed · API Nativa/OA · Melhor quando há análise causal difícil.
- **o3-mini** — closed · API Nativa/OA · Boa opção de fallback reasoning.
- **o1** — closed · API Nativa/OA · Caro; evitar salvo compatibilidade antiga.
- **Codex mini / GPT Codex** — closed · API Nativa/OA · Para edição/agentes de código; há variantes GPT-5.1 Codex mini mais baratas.

### Anthropic (EUA)

| Modelo | Perfil | Contexto | Preço I/O | IAC US$ | Qual. |
|---|---|---:|---:|---:|---:|
| Claude Opus 4.6 | reasoning/código | 1M beta | 5.00 / 25.00 | 0.0900 | ★★★★★ |
| Claude Sonnet 4.6 | coding/agentic | 1M beta | 3.00 / 15.00 | 0.0540 | ★★★★★ |
| Claude Haiku 4.5 | rápido | ⚠️ | 1.00 / 5.00 | 0.0180 | ★★★★ |

**Complementares:**
- **Claude Opus 4.6** — closed · API Nativa · Premium; melhor para issues críticas.
- **Claude Sonnet 4.6** — closed · API Nativa · Melhor default premium para IAC.
- **Claude Haiku 4.5** — closed · API Nativa · Boa triagem com qualidade acima do preço.

### Google Gemini (EUA)

| Modelo | Perfil | Contexto | Preço I/O | IAC US$ | Qual. |
|---|---|---:|---:|---:|---:|
| Gemini 2.5 Pro | multimodal/reasoning | 1M | 1.25 / 10.00 | 0.0300 | ★★★★★ |
| Gemini 2.5 Flash | baixo custo/reasoning | 1M | 0.30 / 2.50 | 0.0074 | ★★★★ |
| Gemini 2.0 Flash | multimodal barato | 1M | 0.10 / 0.40 | 0.0016 | ★★★ |

**Complementares:**
- **Gemini 2.5 Pro** — closed · API Nativa/OA parcial · Ótimo long-context; output caro.
- **Gemini 2.5 Flash** — closed · API Nativa/OA parcial · Melhor custo-benefício geral.
- **Gemini 2.0 Flash** — closed · API Nativa/OA parcial · Fortíssimo para volume e testes pagos.

### Meta Llama (EUA)

| Modelo | Perfil | Contexto | Preço I/O | IAC US$ | Qual. |
|---|---|---:|---:|---:|---:|
| Llama 3.3 70B | open-weights | 128K | 0.59-0.88 / 0.79-0.88 | 0.0063-0.0088 | ★★★ |
| Llama 3.1 405B | open-weights | 128K | variável | ⚠️ | ★★★★ |
| Llama 3.1 70B | open-weights | 128K | variável | ⚠️ | ★★★ |
| Llama 3.1 8B | open-weights small | 128K | 0.05 / 0.08 | 0.0006 | ★★ |
| Llama 4 Scout | open-weights multimodal | 10M | 0.11 / 0.34 | 0.0016 | ★★★★ |
| Llama 4 Maverick | open-weights multimodal | 1M | variável | ⚠️ | ★★★★ |

**Complementares:**
- **Llama 3.3 70B** — 70B dense · Meta via Groq/Together · API OA via provedor · Boa alternativa barata; menos forte que Sonnet/GPT em RCA complexo.
- **Llama 3.1 405B** — 405B dense · Meta via provedores · API OA via provedor · Peso público; caro de hospedar.
- **Llama 3.1 70B** — 70B dense · Meta via provedores · API OA via provedor · Superado por 3.3 70B na maioria dos usos.
- **Llama 3.1 8B** — 8B dense · Meta via Groq/local · API OA/local · Bom para testes, ruim para análise causal profunda.
- **Llama 4 Scout** — MoE 109B total/17B ativo · Meta via Groq/Together · API OA via provedor · Muito interessante para contexto enorme.
- **Llama 4 Maverick** — MoE ~400B/17B ativo · Meta via provedores · API OA via provedor · Mais forte que Scout; disponibilidade/preço variam.

### Mistral AI (Europa)

| Modelo | Perfil | Contexto | Preço I/O | IAC US$ | Qual. |
|---|---|---:|---:|---:|---:|
| Mistral Large 2.1 | proprietário legado | 128K | 2.00 / 6.00 | 0.0280 | ★★★★ |
| Mistral Medium 3.1 | proprietário | ⚠️ | ⚠️ / ⚠️ | ⚠️ | ★★★★ |
| Mistral Small 4 | open-weights hybrid | 256K | 0.15 / 0.60 | 0.0024 | ★★★★ |
| Mixtral 8x7B | open-weights | 32K | 0.60 / 0.60 | 0.0060 | ★★ |
| Mixtral 8x22B | open-weights | 64K | ~1.20 / ~1.20 | 0.0120 | ★★★ |
| Codestral 25.08 | code-specialized | 128K | 0.30 / 0.90 | 0.0042 | ★★★★ |

**Complementares:**
- **Mistral Large 2.1** — closed · API Nativa/OA · Legado; Large 3 é open-weight mais novo.
- **Mistral Medium 3.1** — closed · API Nativa/OA · Preço oficial não verificado no crawl; modelo recomendado pela Mistral.
- **Mistral Small 4** — MoE 119B/6.5B ativo · API Nativa/OA · Forte opção europeia e barata.
- **Mixtral 8x7B** — MoE ~47B/13B ativo · Mistral/Together · API OA via provedor · Legado; evitar para IAC moderno.
- **Mixtral 8x22B** — MoE ~141B/39B ativo · Mistral/Fireworks · API OA via provedor · Ainda útil, mas superado por Small 4/DeepSeek.
- **Codestral 25.08** — closed/premier · API Nativa/OA · Bom para FIM/código; não é melhor RCA geral.

### DeepSeek (China)

| Modelo | Perfil | Contexto | Preço I/O | IAC US$ | Qual. |
|---|---|---:|---:|---:|---:|
| DeepSeek V3/V3.1 | open-weights | 64K-128K | 0.28-0.60 / 0.42-1.70 | 0.0031-0.0082 | ★★★★ |
| DeepSeek Coder | open-weights código | variável | ⚠️ / ⚠️ | ⚠️ | ★★★★ |
| DeepSeek Reasoner/R1 | open-weights reasoning | 128K | 0.28-0.55 / 0.42-2.19 | 0.0031-0.0088 | ★★★★★ |

**Complementares:**
- **DeepSeek V3/V3.1** — MoE 671B/37B ativo · DeepSeek/provedores · API OA · Excelente custo/qualidade; cautela LGPD.
- **DeepSeek Coder** — variável · DeepSeek/provedores · API OA/local · Bom local; preço oficial atual não verificado.
- **DeepSeek Reasoner/R1** — MoE · API OA · Muito bom em custo; output reasoning pode inflar.

### Alibaba Qwen (China)

| Modelo | Perfil | Contexto | Preço I/O | IAC US$ | Qual. |
|---|---|---:|---:|---:|---:|
| Qwen 2.5 72B | open-weights | 128K | variável | ⚠️ | ★★★★ |
| Qwen 2.5 32B | open-weights | 128K | variável | ⚠️ | ★★★ |
| Qwen 2.5 14B | open-weights | 128K | variável | ⚠️ | ★★ |
| Qwen 2.5 7B | open-weights | 128K | 0.30 / 0.30 (Together) | 0.0030 | ★★ |
| Qwen3 32B | open-weights reasoning | 131K | 0.29 / 0.59 (Groq) | 0.0035 | ★★★★ |
| Qwen3 235B | open-weights/MoE | 128K+ | variável | ⚠️ | ★★★★ |
| Qwen-Coder | code-specialized | até 1M em qwen3-coder | 1.00+ / 5.00+ | 0.0180+ | ★★★★ |
| QwQ | reasoning | 32K-128K | variável | ⚠️ | ★★★ |

**Complementares:**
- **Qwen 2.5 72B** — 72B dense · Alibaba/provedores · API OA/local · Bom para código e pt-BR; preço depende do host.
- **Qwen 2.5 32B** — 32B dense · Alibaba/provedores · API OA/local · Ótimo local/baixo custo.
- **Qwen 2.5 14B** — 14B dense · Alibaba/provedores · API OA/local · Testes e dev local.
- **Qwen 2.5 7B** — 7B dense · Alibaba/provedores · API OA/local · Apenas triagem simples.
- **Qwen3 32B** — 32B dense · Groq/Alibaba/provedores · API OA via provedor · Bom custo e latência no Groq.
- **Qwen3 235B** — MoE 235B/A22B · Alibaba/provedores · API OA · Forte; preço oficial por variante DashScope é confuso.
- **Qwen-Coder** — MoE/dense por versão · Alibaba · API OA · Caro em janelas longas; bom em agentic coding.
- **QwQ** — 32B · Alibaba/provedores · API OA/local · Superado por Qwen3 reasoning/DeepSeek R1.

### MiniMax (China)

| Modelo | Perfil | Contexto | Preço I/O | IAC US$ | Qual. |
|---|---|---:|---:|---:|---:|
| MiniMax abab6.5 | proprietário legado | ⚠️ | ⚠️ / ⚠️ | ⚠️ | ★★★ |
| MiniMax M1 | open-weight reasoning | 1M | 0.40* / 2.20* | 0.0076 | ★★★★ |
| MiniMax M2.5 | proprietário código/agentic | 204.8K | 0.30 / 1.20 (Fireworks/Together) | 0.0048 | ★★★★ |

**Complementares:**
- **MiniMax abab6.5** — closed · API OA parcial · Legado; docs atuais priorizam M2.x.
- **MiniMax M1** — MoE 456B/45.9B ativo · API OA/Anthropic compat · *Preço não oficial direto; pesos e specs oficiais.
- **MiniMax M2.5** — closed · API OA/Anthropic compat · Docs oficiais confirmam 60-100 tps.

### xAI (EUA)

| Modelo | Perfil | Contexto | Preço I/O | IAC US$ | Qual. |
|---|---|---:|---:|---:|---:|
| Grok 2 | proprietário legado | ⚠️ | ⚠️ / ⚠️ | ⚠️ | ★★★ |
| Grok 3 | proprietário | 131K | 3.00 / 15.00 | 0.0540 | ★★★★ |
| Grok 4 | proprietário reasoning | 256K | 3.00 / 15.00 | 0.0540 | ★★★★ |
| Grok 4.20 | proprietário agentic | 2M | 2.00 / 6.00 | 0.0280 | ★★★★ |

**Complementares:**
- **Grok 2** — closed · API OA · Substituído por Grok 3/4.
- **Grok 3** — closed · API OA · Mesmo preço de Sonnet; menos atraente para IAC.
- **Grok 4** — closed · API OA · Bom, mas Grok 4.20/4.1 Fast já mudaram o cenário.
- **Grok 4.20** — closed · API OA · Atual flagship listado pela xAI; incluir como sucessor prático.

### Cohere e AI21

| Modelo | Origem | Perfil | Contexto | Preço I/O | IAC US$ | Qual. |
|---|---|---|---:|---:|---:|---:|
| Cohere Command R+ | Canadá/EUA | RAG/tool | 128K | 2.50 / 10.00 | 0.0400 | ★★★ |
| Cohere Command R | Canadá/EUA | RAG barato | 128K | 0.15 / 0.60 | 0.0024 | ★★★ |
| AI21 Jamba 1.5 Large | Israel | open-weights long-context | 256K | 2.00 / 8.00 | 0.0320 | ★★★ |
| AI21 Jamba 1.5 Mini | Israel | open-weights | 256K | 0.20 / 0.40 | 0.0024 | ★★★ |

**Complementares:**
- **Cohere Command R+** — closed · API Nativa · Forte em RAG/citações; caro frente a Flash.
- **Cohere Command R** — closed · API Nativa · Bom para extração e RAG simples.
- **AI21 Jamba 1.5 Large** — hybrid SSM-Transformer MoE 398B/94B · API Nativa/Bedrock · Long-context bom; ecossistema menor.
- **AI21 Jamba 1.5 Mini** — hybrid MoE 52B/12B · API Nativa/Bedrock · Barato, bom para documentos longos simples.

### Chineses adicionais (China)

| Modelo | Perfil | Contexto | Preço I/O | IAC US$ | Qual. |
|---|---|---:|---:|---:|---:|
| Zhipu GLM-4/4.5 | open/proprietário por versão | 128K | 0.60* / 2.20* | 0.0092 | ★★★★ |
| Moonshot Kimi K2 | open-weights/MoE | 128K-256K | 0.15-0.60 / 2.00-2.50 | 0.0062 | ★★★★ |
| 01.AI Yi | open-weights | 32K-200K | ⚠️ / ⚠️ | ⚠️ | ★★ |

**Complementares:**
- **Zhipu GLM-4/4.5** — GLM-4.5 MoE 355B/32B · API OA · *Preço de agregador; confirmar no console oficial.
- **Moonshot Kimi K2** — 1T/32B ativo · API OA/Anthropic compat · Bom para agentes/código; origem China.
- **01.AI Yi** — 6B-34B+ · API OA via host · Menos relevante em 2026; evitar salvo legado/local.

Fontes principais do bloco: OpenAI pricing/model docs, Anthropic pricing/news/rate-limit docs, Google Gemini pricing, Groq pricing, Together pricing, Fireworks pricing, DeepSeek docs, Mistral docs, Cohere docs, AI21 pricing/research, xAI docs/API page, Alibaba Model Studio pricing, MiniMax docs/news, Meta/Hugging Face model cards, OpenRouter pricing/rate limits, Hugging Face pricing, Replicate pricing, Perplexity pricing.

## Dados por família e fontes

### OpenAI

| Modelo | Lançamento/atualização | Free tier | Contexto | Latência | Benchmarks | Forças | Fraquezas |
|---|---|---|---:|---|---|---|---|
| GPT-4o | 2024; mantido na API | Sem free API permanente verificável; limites por tier no console | 128K | ⚠️ não verificado | ⚠️ | Multimodal, robusto, maduro | Custo maior que GPT-4.1 mini/Gemini Flash. |
| GPT-4o mini | 2024 | Sem free API permanente verificável | 128K | ⚠️ | ⚠️ | Muito barato, bom para triagem | Fraco para RCA complexo. |
| GPT-4.1 | 14/04/2025 | Sem free API permanente verificável | 1.047.576 | baixa, sem reasoning step | SWE-bench Verified 54,6% | Código, instrução, long-context | Não é reasoning profundo. |
| o3/o3-mini/o1 | 2024-2025 | Sem free API permanente verificável | ⚠️ | Mais lenta por reasoning | ⚠️ | Raciocínio e investigação | Pode gerar custo oculto por reasoning tokens. |
| Codex | 2025+ | Sem free API permanente verificável | ⚠️ | ⚠️ | ⚠️ | Edição e agentes de código | Nome/modelos mudam; pinagem necessária. |

Qualidade IAC: GPT-4.1 e o3 são fortes para stack trace/código; GPT-4o mini é triagem econômica; o1 é caro e hoje tende a ser substituído por o3/GPT-5.x.  
Fontes: [OpenAI API Pricing](https://openai.com/api/pricing/), [OpenAI pricing docs](https://platform.openai.com/docs/pricing/), [GPT-4.1 model](https://platform.openai.com/docs/models/gpt-4.1), [GPT-4o model](https://platform.openai.com/docs/models/gpt-4o), [GPT-4o mini model](https://developers.openai.com/api/docs/models/gpt-4o-mini), [GPT-4.1 release](https://openai.com/index/gpt-4-1/), [OpenAI rate limits](https://help.openai.com/en/articles/5955598-is-api-usage-subject-to-any-rate-limits).

### Anthropic

| Modelo | Lançamento/atualização | Free tier | Contexto | Latência | Benchmarks | Forças | Fraquezas |
|---|---|---|---:|---|---|---|---|
| Claude Opus 4.6 | 05/02/2026 | API exige crédito; Tier 1 após compra de US$5 | 1M beta | ⚠️ | SWE-bench Verified até 81,42% com prompt modificado; Terminal-Bench 2.0 líder | Melhor para RCA crítico, code review, agentes longos | Custo alto. |
| Claude Sonnet 4.6 | 17/02/2026 | Claude.ai Free tem acesso; API tier por crédito | 1M beta | ⚠️ | SWE-bench Verified citado por imprensa em 79,6%; confirmar system card | Melhor default premium para IAC | Ainda caro em volume alto. |
| Claude Haiku 4.5 | 2025 | API tier por crédito | ⚠️ | rápido | ⚠️ | Triagem, resumo, extração | Menos confiável em debugging profundo. |

Rate limits Tier 1: 50 RPM para Opus/Sonnet 4.x, 30K ITPM, 8K OTPM; tiers sobem por crédito comprado.  
Fontes: [Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing), [Claude Opus 4.6](https://www.anthropic.com/news/claude-opus-4-6), [Claude Sonnet 4.6](https://www.anthropic.com/news/claude-sonnet-4-6), [Anthropic rate limits](https://docs.anthropic.com/en/api/rate-limits), [Choosing Claude models](https://claude.com/resources/tutorials/choosing-the-right-claude-model).

### Google Gemini

| Modelo | Lançamento/atualização | Free tier | Contexto | Latência | Benchmarks | Forças | Fraquezas |
|---|---|---|---:|---|---|---|---|
| Gemini 2.5 Pro | 2025 | Free tier no AI Studio; dados podem melhorar produtos | 1M | ⚠️ | ⚠️ | Long-context, código, reasoning | Output caro; quota free não é produção. |
| Gemini 2.5 Flash | 2025 | Free tier; Search grounding até 500 RPD no free | 1M | rápida | ⚠️ | Melhor custo-benefício geral | Menos consistente que Sonnet em RCA difícil. |
| Gemini 2.0 Flash | 2024/2025 | Free tier; Search grounding até 500 RPD | 1M | rápida | ⚠️ | Barato, multimodal, bom para volume | Qualidade menor em bugs complexos. |

Fontes: [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing), [Gemini pricing](https://ai.google.dev/pricing).

### Meta Llama

| Modelo | Lançamento/atualização | Free tier | Contexto | Latência | Benchmarks | Forças | Fraquezas |
|---|---|---|---:|---|---|---|---|
| Llama 3.3 70B | 06/12/2024 | Grátis local; provedores podem ter free endpoints | 128K | Groq 394 tps | MMLU/benchmarks no model card | Bom open-weight geral | Menos preciso que frontier closed. |
| Llama 3.1 405B/70B/8B | 23/07/2024 | Grátis local/pesos | 128K | depende do host | MMLU 85,2 para 405B base divulgado | Open-weight, deploy privado | 405B caro; 8B fraco. |
| Llama 4 Scout | 05/04/2025 | Grátis local/pesos; via Groq pago | 10M | Groq 594 tps | ⚠️ | Contexto enorme, multimodal, baixo custo | 10M real em produção depende do host. |
| Llama 4 Maverick | 05/04/2025 | Grátis local/pesos | 1M | ⚠️ | ⚠️ | Melhor qualidade Llama 4 | Preço/disponibilidade variam. |

Fontes: [Llama 3.1 HF](https://huggingface.co/meta-llama/Llama-3.1-405B), [Llama 3.3 NVIDIA card](https://build.nvidia.com/meta/llama-3_3-70b-instruct/modelcard), [Llama 4 HF docs](https://huggingface.co/docs/transformers/en/model_doc/llama4), [Llama 4 Scout HF](https://huggingface.co/meta-llama/Llama-4-Scout-17B-16E), [Llama 4 Maverick HF](https://huggingface.co/meta-llama/Llama-4-Maverick-17B-128E), [Groq pricing](https://groq.com/pricing), [Together pricing](https://www.together.ai/pricing).

### Mistral AI

| Modelo | Lançamento/atualização | Free tier | Contexto | Latência | Benchmarks | Forças | Fraquezas |
|---|---|---|---:|---|---|---|---|
| Mistral Large / Large 2.1 | 2024 legado | Le Chat free; API sem free produção | 128K | ⚠️ | ⚠️ | Boa qualidade geral, Europa | Legado vs Large 3/Small 4. |
| Mistral Medium 3.1 | 08/2025 | ⚠️ | ⚠️ | ⚠️ | ⚠️ | Multimodal frontier Mistral | Preço oficial não capturado. |
| Mistral Small 4 | 16/03/2026 | pesos abertos | 256K | ⚠️ | ⚠️ | Barato, open, Europa, híbrido reasoning/coding | Ainda validar em RCA IAC. |
| Mixtral 8x7B/8x22B | 2023/2024 | pesos abertos | 32K/64K | ⚠️ | ⚠️ | Barato/local | Obsoleto para produção IAC. |
| Codestral | 30/07/2025 | ⚠️ | 128K | baixa | ⚠️ | FIM, geração/correção de código | Especializado; relatórios RCA podem ser piores. |

Fontes: [Mistral models](https://docs.mistral.ai/getting-started/models), [Mistral Small 4](https://docs.mistral.ai/models/mistral-small-4-0-26-03), [Codestral 25.08](https://docs.mistral.ai/models/codestral-25-08), [Fireworks pricing](https://fireworks.ai/pricing), [Together pricing](https://www.together.ai/pricing).

### DeepSeek

| Modelo | Lançamento/atualização | Free tier | Contexto | Latência | Benchmarks | Forças | Fraquezas |
|---|---|---|---:|---|---|---|---|
| DeepSeek V3/V3.1 | 2024/2025 | Sem free oficial robusto; pesos públicos | 64K-128K | ⚠️ | ⚠️ | Custo muito baixo, bom código | Compliance China; versões API/app divergem. |
| DeepSeek Coder | 2024/2025 | local | variável | depende local | ⚠️ | Código barato/local | Menos generalista. |
| DeepSeek Reasoner/R1 | 2025; API atual mapeia V3.2 thinking | 128K | 128K | ⚠️ | ⚠️ | Reasoning barato, OA-compatible | CoT/output pode aumentar custo; política de dados. |

Fontes: [DeepSeek pricing](https://api-docs.deepseek.com/quick_start/pricing/), [DeepSeek pricing details](https://api-docs.deepseek.com/quick_start/pricing-details-usd/), [DeepSeek API overview](https://api-docs.deepseek.com/), [DeepSeek reasoner](https://api-docs.deepseek.com/guides/reasoning_model), [Together DeepSeek](https://www.together.ai/models-providers/deepseek).

### Alibaba Qwen

| Modelo | Lançamento/atualização | Free tier | Contexto | Latência | Benchmarks | Forças | Fraquezas |
|---|---|---|---:|---|---|---|---|
| Qwen 2.5 72B/32B/14B/7B | 2024/2025 | pesos abertos; Alibaba dá quotas por 90 dias em alguns modelos | 128K típico | depende host | ⚠️ | Código, multilíngue, local | Preço oficial por nome open-weight não é único. |
| Qwen3 32B/235B | 2025 | pesos abertos/quotas DashScope por modelo | 128K-1M por variante | Groq 662 tps para Qwen3 32B | ⚠️ | Bom reasoning/código barato | Políticas e preços variam por região. |
| Qwen-Coder | 2025 | quota 1M tokens por 90 dias em Alibaba International | até 1M | ⚠️ | ⚠️ | Código/agentic | Custo sobe em contexto longo. |
| QwQ | 2024/2025 | pesos abertos | 32K+ | ⚠️ | ⚠️ | Reasoning local | Superado por Qwen3/DeepSeek. |

Fontes: [Alibaba Model Studio pricing](https://www.alibabacloud.com/help/en/model-studio/model-pricing), [Alibaba billing](https://www.alibabacloud.com/help/en/model-studio/billing-for-model-studio), [Groq pricing](https://groq.com/pricing), [Together pricing](https://www.together.ai/pricing).

### MiniMax

| Modelo | Lançamento/atualização | Free tier | Contexto | Latência | Benchmarks | Forças | Fraquezas |
|---|---|---|---:|---|---|---|---|
| abab6.5 | legado | ⚠️ | ⚠️ | ⚠️ | ⚠️ | Compatibilidade histórica | Não é foco atual da plataforma. |
| M1 | 16/06/2025 | pesos abertos | 1M | ⚠️ | ⚠️ | Reasoning longo, open-weight | Preço oficial API não capturado; usar host. |
| M2.5/M2.7 | 2026 | ⚠️ | 204.8K | 60 tps; highspeed 100 tps | ⚠️ | Código/agentic, boa latência | Menor maturidade de ecossistema no Brasil. |

Fontes: [MiniMax API overview](https://platform.minimax.io/docs/api-reference/api-overview), [MiniMax text generation](https://platform.minimax.io/docs/guides/text-generation), [MiniMax M1 news](https://www.minimax.io/news/minimaxm1), [MiniMax M1 GitHub](https://github.com/MiniMax-AI/MiniMax-M1), [Fireworks pricing](https://fireworks.ai/pricing), [Together pricing](https://www.together.ai/pricing).

### xAI

| Modelo | Lançamento/atualização | Free tier | Contexto | Latência | Benchmarks | Forças | Fraquezas |
|---|---|---|---:|---|---|---|---|
| Grok 2 | legado | ⚠️ | ⚠️ | ⚠️ | ⚠️ | Integração X/ecossistema | Evitar em novo backend. |
| Grok 3 | 2025 | sem free API claro | 131K | ⚠️ | ⚠️ | Geral forte | Mesmo custo de Sonnet 4.6 com menor confiança para IAC. |
| Grok 4 | 2025 | sem free API claro | 256K | ⚠️ | ⚠️ | Reasoning | Substituído operacionalmente por 4.20/4.1 Fast. |
| Grok 4.20 / 4.1 Fast | 2026 | sem free API claro | 2M | “lightning fast” oficial, sem tps | ⚠️ | Contexto 2M e tool calling | Modelo muda rápido; pinagem necessária. |

Fontes: [xAI API](https://x.ai/api), [xAI models and pricing](https://docs.x.ai/docs/models), [xAI rate limits](https://docs.x.ai/developers/rate-limits), [xAI consumption](https://docs.x.ai/docs/key-information/consumption-and-rate-limits).

### Cohere e AI21

| Modelo | Lançamento/atualização | Free tier | Contexto | Latência | Benchmarks | Forças | Fraquezas |
|---|---|---|---:|---|---|---|---|
| Command R+ | 08/2024 | Trial key no dashboard | 128K | 25% menor que versão anterior | ⚠️ | RAG, citações, tool-use | Custo alto para IAC simples. |
| Command R | 08/2024 | Trial key | 128K | 20% menor que versão anterior | ⚠️ | RAG barato | Código/debugging mediano. |
| Jamba 1.5 Large | 22/08/2024 | US$10 créditos/3 meses | 256K | AI21 cita até 2,5x em long context | Arena/benchmarks gerais | Long-context e híbrido SSM | Menor comunidade. |
| Jamba 1.5 Mini | 22/08/2024 | US$10 créditos/3 meses | 256K | rápida | Arena Hard 46,1 citado pela AWS | Barato para documentos | Menos forte em código. |

Fontes: [Command R+](https://docs.cohere.com/v2/docs/command-r-plus), [Command R](https://docs.cohere.com/docs/command-r), [Cohere pricing](https://cohere.com/pricing), [AI21 pricing](https://www.ai21.com/pricing/), [AI21 Jamba research](https://www.ai21.com/research/jamba-1-5-hybrid-transformer-mamba-models-at-scale/), [AWS Jamba Large](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-ai21-labs-jamba-1-5-large.html).

### Provedores multi-modelo

| Provedor | Free/crédito | Preço/observação | Forças | Fraquezas |
|---|---|---|---|---|
| Groq | console/free tier variável; não usar como garantia | Llama 4 Scout US$0,11/0,34; Qwen3 32B US$0,29/0,59; Llama 3.3 70B US$0,59/0,79 | Latência extrema, OpenAI-compatible | Catálogo menor; rate limits por conta. |
| Together.ai | sem free robusto verificado | DeepSeek V3.1 US$0,60/1,70; R1 US$3/7; Llama 3.3 70B US$0,88/0,88 | Bom catálogo open-weights | Mais caro que API direta em alguns modelos. |
| Fireworks | US$1 crédito inicial | DeepSeek V3 family US$0,56/1,68; MiniMax 2.5 US$0,30/1,20; tiers por tamanho | Ótimo para open models e batch 50% | Preço por família pode ocultar variante. |
| OpenRouter | 25+ modelos free, 50 req/dia; paid sem markup declarado | 5,5% platform fee em PAYG; free router 0/0 | Fallback/roteamento e catálogo enorme | Variabilidade de privacidade, latência e provider. |
| HuggingFace Inference | US$0,10/mês free; Pro US$2/mês | Pay-as-you-go por provider ou compute-time | Bom para protótipo e self-host | Crédito free simbólico. |
| Replicate | sem free destacado | Por segundo de hardware ou por token em modelos selecionados | Fácil para modelos públicos/custom | Custo variável; LLMs nem sempre baratos. |
| Perplexity API | sem free robusto verificado | Sonar US$1/1; Sonar Pro US$3/15 + taxa por busca | Busca/web factual | Não é ideal para stack trace privado sem web. |

Fontes: [Groq pricing](https://groq.com/pricing), [Together pricing](https://www.together.ai/pricing), [Fireworks pricing](https://fireworks.ai/pricing), [OpenRouter pricing](https://openrouter.ai/pricing), [OpenRouter rate limits](https://openrouter.zendesk.com/hc/en-us/articles/39501163636379-OpenRouter-Rate-Limits-What-You-Need-to-Know), [OpenRouter free](https://openrouter.ai/openrouter/free), [Hugging Face pricing](https://huggingface.co/docs/api-inference/en/pricing), [Replicate pricing](https://replicate.com/pricing), [Perplexity pricing](https://docs.perplexity.ai/docs/getting-started/pricing).

### Chineses adicionais

| Família | Estado 2026 | Forças | Fraquezas | Verificação |
|---|---|---|---|---|
| Zhipu GLM-4/GLM-4.5 | GLM-4.5 aparece como MoE 355B/32B, 128K, MIT em fontes públicas; preço direto oficial não capturado | Agentic, tool-use, open-ish | Compliance China; preço precisa confirmar no console | ⚠️ preço não verificado oficialmente |
| Moonshot Kimi K2/K2.5 | API oficial lista K2/K2.5, 256K em variantes, K2 MoE 1T/32B | Agentes, código, bom custo | Política China; preços variam por variante | Parcialmente verificado |
| 01.AI Yi | Família open-weight relevante em 2024; menor relevância em 2026 | Local, pesos públicos | Qualidade inferior aos líderes atuais | ⚠️ preço/API atual não verificado |

Fontes: [Kimi pricing docs](https://platform.moonshot.ai/docs/pricing/chat), [Kimi overview](https://platform.moonshot.ai/docs/overview), [GLM-4.5 public page](https://glm45.org/), [GLM pricing aggregator](https://lmmarketcap.com/pricing-page/model/z-ai-glm-4-5).

## Classificação por custo

| Faixa | Modelos |
|---|---|
| Gratuito permanente | Ollama/local: Llama, Qwen, DeepSeek, Mistral open-weights; OpenRouter Free com 50 req/dia; Gemini AI Studio free para experimentação; HF créditos mensais pequenos. |
| Crédito inicial | AI21 US$10/3 meses; Fireworks US$1; Hugging Face US$0,10/mês free ou US$2/mês Pro; Alibaba Model Studio 1M tokens por modelo por 90 dias em International para vários Qwen. |
| Baixo custo (<US$1/1M efetivo em input e output próximos) | Gemini 2.0 Flash, GPT-4o mini, Command R, Jamba Mini, Llama 4 Scout Groq, Qwen3 32B Groq, Mistral Small 4, DeepSeek Chat/Reasoner, Gemini 2.5 Flash input. |
| Médio | GPT-4.1, o3, Gemini 2.5 Pro, Codestral, MiniMax M2.5, Kimi K2, GLM-4.5, Llama 3.3 70B, Mistral Large legado. |
| Premium | Claude Sonnet 4.6, Claude Opus 4.6, o1, Grok 3/4, Command R+, Sonar Pro quando inclui busca. |

## Classificação por especialização

| Especialização | Modelos |
|---|---|
| General-purpose | GPT-4o, GPT-4.1, Claude Sonnet/Opus, Gemini, Llama 3.3/4, Mistral Large/Small, Command R, Jamba, Kimi, GLM |
| Code-specialized | GPT-4.1, Codex, Claude Sonnet/Opus, Codestral, DeepSeek Coder/R1, Qwen-Coder, MiniMax M2.x, Llama 4 Maverick |
| Reasoning | o3/o3-mini/o1, Claude Opus/Sonnet/Haiku 4.x, Gemini 2.5, DeepSeek R1/Reasoner, QwQ, MiniMax M1, Grok 4, Kimi thinking |
| Long-context >200K | GPT-4.1, Claude 4.6, Gemini 2.x/2.5, Llama 4 Scout/Maverick, Mistral Small 4, Jamba 1.5, Qwen Plus/Coder long, Kimi K2/K2.5, MiniMax M1/M2.x, Grok 4.20 |
| Multimodal visão | GPT-4o/4o mini/4.1 input image, Gemini, Llama 4, Mistral Small 4/Large 3, Qwen-VL, Kimi K2.5, Grok 4.20 |
| Tool-use/Agentic | GPT-4.1/o3/Codex, Claude 4.6, Gemini 2.0/2.5, Command R/R+, Kimi K2, GLM-4.5, MiniMax M2, Qwen-Coder, Grok 4.20 |

## Classificação por proveniência

| Proveniência | Modelos |
|---|---|
| Proprietário closed | OpenAI GPT/o/Codex, Anthropic Claude, Google Gemini, xAI Grok, Cohere Command, AI21 API hosted, MiniMax API closed, Mistral Medium/Large premier |
| Open-weights | Llama, DeepSeek, Qwen, Mistral Small/Large 3/Mixtral, Jamba 1.5, MiniMax M1, Kimi K2, GLM-4.5, Yi |
| Open-source completo | Poucos. GLM-4.5 declara MIT em fonte pública; vários pesos públicos têm licenças próprias e devem ser tratados como open-weights, não OSI. |

## Classificação por origem geográfica e LGPD

| Origem | Modelos/provedores | Implicação LGPD |
|---|---|---|
| EUA | OpenAI, Google, Meta, xAI, Groq, Together, Fireworks, OpenRouter, Replicate, Perplexity | Exigir DPA, retenção zero/baixa, região, subprocessadores; bom ecossistema enterprise. |
| Europa | Mistral | Melhor narrativa regulatória para clientes sensíveis; ainda confirmar região de inferência. |
| China | DeepSeek, Alibaba Qwen, MiniMax, Moonshot, Zhipu, 01.AI | Alto cuidado para dados sensíveis, logs de cliente e código proprietário; preferir self-host ou provedor ocidental com política clara. |
| Outros | Cohere Canadá/EUA, AI21 Israel | Avaliar DPA e região; bons para enterprise/RAG. |

## Classificação por tamanho

| Tamanho | Modelos |
|---|---|
| Small <10B | Llama 3.1 8B, Qwen 2.5 7B, Ministral 3B/8B, Gemma/Gemma3n via provedores |
| Medium 10-70B | Llama 3.3 70B, Qwen 14B/32B/72B, Codestral, Jamba Mini 52B/12B ativo, Qwen3 32B, Mistral 7B/Mixtral active |
| Large 70-200B | Mistral Small 4 119B/6.5B ativo, Llama 4 Scout 109B/17B ativo, Mixtral 8x22B |
| Frontier >200B ou closed-frontier | GPT-4o/4.1/o3/o1, Claude 4.6, Gemini 2.5, Llama 3.1 405B, Llama 4 Maverick, DeepSeek 671B, Qwen3 235B, Kimi 1T, MiniMax M1 456B, GLM-4.5 355B, Jamba Large 398B |

## Custo estimado por análise IAC

| Modelo | Custo US$/análise | Custo R$/análise |
|---|---:|---:|
| Gemini 2.0 Flash | 0.0016 | 0.0080 |
| GPT-4o mini | 0.0024 | 0.0120 |
| Mistral Small 4 | 0.0024 | 0.0120 |
| Cohere Command R | 0.0024 | 0.0120 |
| Jamba 1.5 Mini | 0.0024 | 0.0120 |
| DeepSeek Chat/Reasoner V3.2 | 0.0031 | 0.0154 |
| Qwen3 32B Groq | 0.0035 | 0.0175 |
| Codestral | 0.0042 | 0.0210 |
| MiniMax M2.5 | 0.0048 | 0.0240 |
| Llama 3.3 70B Groq | 0.0063 | 0.0314 |
| Gemini 2.5 Flash | 0.0074 | 0.0369 |
| DeepSeek R1 legado | 0.0088 | 0.0438 |
| Mistral Large 2.1 | 0.0280 | 0.1397 |
| Grok 4.20 | 0.0280 | 0.1397 |
| Gemini 2.5 Pro | 0.0300 | 0.1497 |
| GPT-4.1 / o3 / Jamba Large | 0.0320 | 0.1597 |
| GPT-4o / Command R+ | 0.0400 | 0.1996 |
| Claude Sonnet 4.6 / Grok 3/4 | 0.0540 | 0.2695 |
| Claude Haiku 4.5 | 0.0180 | 0.0898 |
| Claude Opus 4.6 | 0.0900 | 0.4491 |
| o1 | 0.2400 | 1.1977 |

## Custo mensal projetado

| Modelo | 150 issues/mês | 500 issues/mês | 1.500 issues/mês |
|---|---:|---:|---:|
| Gemini 2.0 Flash | US$0.24 / R$1,20 | US$0.80 / R$3,99 | US$2,40 / R$11,98 |
| GPT-4o mini | US$0.36 / R$1,80 | US$1,20 / R$5,99 | US$3,60 / R$17,97 |
| DeepSeek V3.2 | US$0.46 / R$2,31 | US$1,54 / R$7,69 | US$4,62 / R$23,05 |
| Gemini 2.5 Flash | US$1,11 / R$5,54 | US$3,70 / R$18,47 | US$11,10 / R$55,39 |
| GPT-4.1/o3 | US$4,80 / R$23,95 | US$16,00 / R$79,85 | US$48,00 / R$239,54 |
| Gemini 2.5 Pro | US$4,50 / R$22,46 | US$15,00 / R$74,86 | US$45,00 / R$224,57 |
| Claude Sonnet 4.6 | US$8,10 / R$40,42 | US$27,00 / R$134,74 | US$81,00 / R$404,23 |
| Claude Opus 4.6 | US$13,50 / R$67,37 | US$45,00 / R$224,57 | US$135,00 / R$673,72 |
| o1 | US$36,00 / R$179,66 | US$120,00 / R$598,86 | US$360,00 / R$1.796,58 |

## Gráfico ASCII custo x qualidade

Eixo X: custo por análise em log aproximado. Mais à direita = mais caro. Eixo Y implícito por grupo de qualidade.

```text
Qualidade 5  DeepSeek R1/V3.2  Gemini2.5Flash      Gemini2.5Pro GPT4.1/o3  Sonnet4.6   Opus4.6
            |----$0.003----|----$0.007----|--------$0.03--------|--$0.054--|--$0.09--|

Qualidade 4  Qwen3-32B  Codestral MiniMaxM2.5 Llama3.3   MistralSmall4   Grok4.20
            |--0.0035--|--0.004--|--0.005--|--0.006--|--0.0024--|---0.028---|

Qualidade 3  Gemini2.0Flash GPT4o-mini CommandR JambaMini Mixtral
            |--0.0016--|--0.0024--|--0.0024--|--0.0024--|---0.006+---|
```

## Ranking por caso de uso

### Bateria de testes automatizada

1. Ollama local com Qwen2.5-Coder 7B/14B/32B ou Llama 3.1 8B.
2. OpenRouter Free para testes não determinísticos e baixa frequência.
3. Gemini 2.0 Flash free/baixo custo quando a bateria precisa de API real.

### Produção volume baixo (<10 issues/dia)

1. Gemini 2.5 Flash.
2. Claude Haiku 4.5.
3. GPT-4.1 mini/GPT-4o mini para triagem, com escalation manual.

### Produção volume médio (150 issues/milestone)

1. Gemini 2.5 Flash como primário.
2. DeepSeek Reasoner/V3.2 como fallback econômico ou modo `loop`.
3. Claude Sonnet 4.6 para casos com alta severidade.

### Produção volume alto (1000+ issues/mês)

1. Gemini 2.0 Flash ou DeepSeek V3.2 para primeira passada.
2. Groq Llama 4 Scout/Qwen3 32B para baixa latência.
3. Escalonamento seletivo para Sonnet 4.6 ou o3 apenas quando heurísticas indicarem baixa confiança.

### Casos críticos

1. Claude Opus 4.6.
2. Claude Sonnet 4.6.
3. o3 ou Gemini 2.5 Pro.

### LGPD/dados sensíveis

1. Self-host open-weights: Qwen2.5-Coder/DeepSeek/Llama/Mistral em infraestrutura controlada.
2. Mistral em região europeia, se contrato e região forem adequados.
3. OpenAI/Anthropic/Google enterprise com DPA, zero-retention ou data residency contratada.

## Matriz de decisão ponderada

Pesos: custo 30%, qualidade código/stack trace 30%, latência 15%, contexto 10%, maturidade API 10%, compliance 5%. Nota 1-5.

| Modelo | Custo | Código | Latência | Contexto | API | Compliance | Score |
|---|---:|---:|---:|---:|---:|---:|---:|
| Gemini 2.5 Flash | 5 | 4 | 4 | 5 | 4 | 3 | 4.35 |
| DeepSeek V3.2/Reasoner | 5 | 4 | 3 | 3 | 4 | 2 | 4.00 |
| GPT-4o mini | 5 | 3 | 4 | 3 | 5 | 4 | 4.00 |
| Mistral Small 4 | 5 | 4 | 3 | 4 | 4 | 4 | 4.30 |
| Claude Sonnet 4.6 | 2 | 5 | 3 | 5 | 5 | 4 | 3.95 |
| GPT-4.1 | 3 | 5 | 4 | 5 | 5 | 4 | 4.20 |
| Gemini 2.5 Pro | 3 | 5 | 3 | 5 | 4 | 3 | 3.95 |
| Groq Llama 4 Scout | 5 | 4 | 5 | 5 | 4 | 3 | 4.50 |
| Claude Opus 4.6 | 1 | 5 | 2 | 5 | 5 | 4 | 3.35 |
| o3 | 3 | 5 | 2 | 3 | 5 | 4 | 3.75 |

Resultado: para produção IAC, a decisão pragmática é usar um modelo barato e rápido para 80-90% das análises, com escalonamento para Sonnet/Opus/o3 quando houver baixa confiança, stack trace incompleto, ou impacto alto.

## Estratégia multi-backend recomendada

### Pipeline prático

| Etapa | Primário | Fallback | Critério de escalonamento |
|---|---|---|---|
| Extração e normalização | Gemini 2.0 Flash | GPT-4o mini / Command R | Falha em JSON/schema. |
| Análise técnica padrão | Gemini 2.5 Flash | DeepSeek V3.2 / Qwen3 32B | Confiança baixa, erro ambíguo, contexto >128K. |
| Reasoning/RCA difícil | Claude Sonnet 4.6 | o3 / Gemini 2.5 Pro | Causa raiz incerta, múltiplos componentes. |
| Caso crítico | Claude Opus 4.6 | Sonnet 4.6 + o3 cross-check | Incidente P0/P1 ou relatório externo. |
| Dados sensíveis | Self-host Qwen/DeepSeek/Mistral | Mistral EU / contrato enterprise | Código cliente, logs pessoais, segredo. |

### Políticas de roteamento

- `single`: Gemini 2.0 Flash ou GPT-4o mini para issues simples.
- `multi`: Gemini 2.5 Flash primário; DeepSeek/Qwen fallback.
- `loop`: começar barato; a cada iteração usar métrica de confiança e só escalar para Sonnet/o3 se necessário.
- `premium`: Sonnet 4.6 primeiro; Opus 4.6 apenas para RCA realmente crítico.

## Modelos a evitar no IAC

| Modelo/família | Motivo |
|---|---|
| o1 | Custo alto e substituído operacionalmente por o3/o3-mini/GPT-4.1 em muitos fluxos. |
| Mixtral 8x7B | Contexto e qualidade defasados para stack trace/código moderno. |
| Llama 3.1 8B / Qwen 7B como produção | Bons para testes, insuficientes para RCA confiável. |
| Grok 2 | Legado e sem vantagem clara. |
| abab6.5 | Legado MiniMax; docs atuais priorizam M2.x/M1. |
| Yi/01.AI API hosted | Menor relevância e preço/limites atuais não verificados. |
| Perplexity Sonar para logs privados | Produto centrado em web search; não é ideal para código/stack trace sensível. |

## Riscos e caveats

- Preços recentes mudaram em OpenAI, Anthropic, Google, DeepSeek, xAI e Alibaba. Fixar versão de modelo e monitorar pricing semanalmente.
- Modelos ChatGPT podem ser aposentados sem afetar API; OpenAI afirmou que GPT-4o/4.1 foram aposentados no ChatGPT, não na API.
- Agregadores podem trocar provedor upstream, quantização ou região; usar pinagem de provider quando reprodutibilidade importar.
- DeepSeek, Qwen, Kimi, GLM e MiniMax podem ser excelentes tecnicamente, mas exigem avaliação jurídica para LGPD, transferência internacional e segredo de negócio.
- Reasoning tokens são cobrados como output em vários provedores; prompts `loop` podem custar mais do que a fórmula base.
- Contexto anunciado não garante qualidade em todo o comprimento. Para IAC, 128K bem usado costuma ser mais valioso que 1M mal recuperado.
- Free tiers são inadequados para SLA: podem ter filas, coleta de dados, queda de limite e roteamento imprevisível.

## Recomendações finais

### Top 3 dev

1. Ollama + Qwen2.5-Coder 32B ou DeepSeek Coder.
2. Gemini 2.0 Flash.
3. OpenRouter Free para smoke tests de API compatível.

### Top 3 bateria

1. Local open-weights.
2. Gemini 2.0 Flash.
3. GPT-4o mini ou Command R.

### Top 3 produção

1. Gemini 2.5 Flash.
2. Mistral Small 4 ou Groq Llama 4 Scout para alternativa open/europeia/rápida.
3. DeepSeek V3.2/Reasoner para custo mínimo, se compliance permitir.

### Top 3 premium

1. Claude Sonnet 4.6.
2. Claude Opus 4.6.
3. o3 ou Gemini 2.5 Pro.

### Recomendação objetiva para o IAC

Implementar OpenAI e Anthropic como backends pendentes, mas não tornar nenhum deles o único caminho de produção. A configuração mais resiliente é:

```yaml
default_backend: gemini-2.5-flash
cheap_backend: gemini-2.0-flash
fast_backend: groq/llama-4-scout
reasoning_backend: anthropic/claude-sonnet-4.6
critical_backend: anthropic/claude-opus-4.6
openai_fallback: openai/gpt-4.1
local_sensitive_backend: ollama/qwen2.5-coder:32b
```

## Metodologia e fontes

Coleta realizada por web search em 16/04/2026, priorizando documentação oficial de pricing e model cards. Quando a fonte oficial do criador do modelo não expõe preço API por token, usei provedores de inferência conhecidos e marquei a limitação. Dados de benchmark foram incluídos apenas quando apareceram em páginas oficiais ou descrições de model cards acessadas; caso contrário foram marcados como `⚠️ não verificado`.

Fontes consultadas:

- OpenAI: [API Pricing](https://openai.com/api/pricing/), [platform pricing](https://platform.openai.com/docs/pricing/), [GPT-4.1](https://platform.openai.com/docs/models/gpt-4.1), [GPT-4o](https://platform.openai.com/docs/models/gpt-4o), [GPT-4o mini](https://developers.openai.com/api/docs/models/gpt-4o-mini), [GPT-4.1 release](https://openai.com/index/gpt-4-1/), [rate limits](https://help.openai.com/en/articles/5955598-is-api-usage-subject-to-any-rate-limits).
- Anthropic: [pricing](https://platform.claude.com/docs/en/about-claude/pricing), [Opus 4.6](https://www.anthropic.com/news/claude-opus-4-6), [Sonnet 4.6](https://www.anthropic.com/news/claude-sonnet-4-6), [rate limits](https://docs.anthropic.com/en/api/rate-limits), [model selection](https://claude.com/resources/tutorials/choosing-the-right-claude-model).
- Google: [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing), [Gemini pricing](https://ai.google.dev/pricing).
- Meta/Llama: [Llama 3.1 HF](https://huggingface.co/meta-llama/Llama-3.1-405B), [Llama 3.3 NVIDIA](https://build.nvidia.com/meta/llama-3_3-70b-instruct/modelcard), [Llama 4 docs](https://huggingface.co/docs/transformers/en/model_doc/llama4), [Llama 4 Scout](https://huggingface.co/meta-llama/Llama-4-Scout-17B-16E), [Llama 4 Maverick](https://huggingface.co/meta-llama/Llama-4-Maverick-17B-128E).
- Mistral: [models](https://docs.mistral.ai/getting-started/models), [Mistral Small 4](https://docs.mistral.ai/models/mistral-small-4-0-26-03), [Codestral](https://docs.mistral.ai/models/codestral-25-08).
- DeepSeek: [pricing](https://api-docs.deepseek.com/quick_start/pricing/), [pricing details](https://api-docs.deepseek.com/quick_start/pricing-details-usd/), [overview](https://api-docs.deepseek.com/), [reasoner](https://api-docs.deepseek.com/guides/reasoning_model).
- Alibaba/Qwen: [Model Studio pricing](https://www.alibabacloud.com/help/en/model-studio/model-pricing), [billing](https://www.alibabacloud.com/help/en/model-studio/billing-for-model-studio).
- MiniMax: [API overview](https://platform.minimax.io/docs/api-reference/api-overview), [text generation](https://platform.minimax.io/docs/guides/text-generation), [M1 announcement](https://www.minimax.io/news/minimaxm1), [M1 GitHub](https://github.com/MiniMax-AI/MiniMax-M1).
- xAI: [API page](https://x.ai/api), [models/pricing](https://docs.x.ai/docs/models), [rate limits](https://docs.x.ai/developers/rate-limits), [consumption](https://docs.x.ai/docs/key-information/consumption-and-rate-limits).
- Cohere: [Command R+](https://docs.cohere.com/v2/docs/command-r-plus), [Command R](https://docs.cohere.com/docs/command-r), [pricing](https://cohere.com/pricing).
- AI21: [pricing](https://www.ai21.com/pricing/), [Jamba research](https://www.ai21.com/research/jamba-1-5-hybrid-transformer-mamba-models-at-scale/), [AWS Jamba Large](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-ai21-labs-jamba-1-5-large.html).
- Multi-modelo: [Groq pricing](https://groq.com/pricing), [Together pricing](https://www.together.ai/pricing), [Fireworks pricing](https://fireworks.ai/pricing), [OpenRouter pricing](https://openrouter.ai/pricing), [OpenRouter rate limits](https://openrouter.zendesk.com/hc/en-us/articles/39501163636379-OpenRouter-Rate-Limits-What-You-Need-to-Know), [OpenRouter Free](https://openrouter.ai/openrouter/free), [Hugging Face pricing](https://huggingface.co/docs/api-inference/en/pricing), [Replicate pricing](https://replicate.com/pricing), [Perplexity pricing](https://docs.perplexity.ai/docs/getting-started/pricing).
- Chineses adicionais: [Kimi pricing](https://platform.moonshot.ai/docs/pricing/chat), [Kimi overview](https://platform.moonshot.ai/docs/overview), [GLM-4.5 public page](https://glm45.org/), [GLM pricing aggregator](https://lmmarketcap.com/pricing-page/model/z-ai-glm-4-5).
- Câmbio: [Investing.com USD/BRL](https://www.investing.com/currencies/usd-brl-historical-data).
