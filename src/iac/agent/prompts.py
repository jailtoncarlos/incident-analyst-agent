"""Prompts encadeados para análise de incidentes.

Constrói prompts para o LLM a partir do resultado de analyze_issue(),
combinando dados da issue + análise estrutural + código-fonte.

Dois prompts:
    1. build_analysis_prompt: classificação + análise aprofundada + resolução
    2. build_response_prompt: rascunho de resposta ao usuário
"""

from __future__ import annotations

import re

from iac.agent.orchestrator import format_context_for_prompt, format_structural_analysis


# ---------------------------------------------------------------------------
# Prompt de análise
# ---------------------------------------------------------------------------

SYSTEM_ANALYSIS = """Você é um engenheiro de software sênior analisando uma issue de erro de produção do SUAP \
(ERP Django, Python 3.14, Django 5.2, 100+ apps).

Você receberá:
- Dados da issue (extraídos automaticamente da descrição)
- Análise estrutural (componentes e fluxo obtidos via inspeção do código)
- Código-fonte da view e referências (métodos, models, forms)

Responda em português do Brasil com EXATAMENTE estas 5 seções numeradas."""

TEMPLATE_ANALYSIS = """### 1. Análise do código
- Descreva o fluxo da view em linguagem acessível
- Quais models, forms e templates estão envolvidos e qual o papel de cada um

### 2. Análise aprofundada
- Causa raiz provável do problema reportado pelo usuário
- Condições em que o erro/situação ocorre
- Referências a arquivo:linha do código que sustentam a análise
- Marque com [ENCONTRADO] evidências no código, [INFERÊNCIA] hipóteses

### 3. Classificação
Responda com EXATAMENTE UMA destas opções (copie literal):
- CLASSIFICAÇÃO: tipo::bug
- CLASSIFICAÇÃO: tipo::configuracao
- CLASSIFICAÇÃO: tipo::dados-cadastrais
- CLASSIFICAÇÃO: tipo::prazo-expirado
- CLASSIFICAÇÃO: tipo::nao-e-erro

### 4. Sugestão de resolução
Se bug: inclua diff sugerido (antes/depois com arquivo:linha).
Se não-bug: passos administrativos concretos (Admin > Seção > Campo).

### 5. Plano de simulação
COPIE este formato exato, preenchendo os valores:
- **Usuário afetado:** <matrícula ou CPF>
- **URL do erro:** <path relativo>
- **Admin para validação:** <username admin>
- **URL admin:** <path admin relativo>
- **O que verificar:** <o que confirmar>

REGRAS:
- Seja conciso.
- Não invente código inexistente — use apenas o código fornecido.
- Use [ENCONTRADO] para evidências e [INFERÊNCIA] para hipóteses.
- A classificação deve ser baseada na análise do código + descrição do usuário."""


def build_analysis_prompt(result: dict) -> str:
    """Constrói o prompt de análise a partir do resultado de analyze_issue().

    Args:
        result: dict com classification, context, structural (saída de analyze_issue)

    Returns:
        Prompt completo para enviar ao LLM.
    """
    sections = [SYSTEM_ANALYSIS, '\n---\n']

    # Dados da issue + análise estrutural (sem código)
    structural_text = format_structural_analysis(result['structural'])
    sections.append(structural_text)

    # Código-fonte (view + referências)
    context_text = format_context_for_prompt(result['context'])
    # Remover header duplicado (app/view/arquivo já estão no structural)
    context_text = _strip_context_header(context_text)
    if context_text.strip():
        sections.append('\n---\n')
        sections.append(context_text)

    # Instruções
    sections.append('\n---\n')
    sections.append(TEMPLATE_ANALYSIS)

    return '\n'.join(sections)


def _strip_context_header(context: str) -> str:
    """Remove o header do format_context_for_prompt (já presente no structural)."""
    lines = context.split('\n')
    # Pular linhas até encontrar "### Código da view"
    start = 0
    for i, line in enumerate(lines):
        if line.startswith('### Código'):
            start = i
            break
    return '\n'.join(lines[start:])


# ---------------------------------------------------------------------------
# Prompt de resposta ao usuário
# ---------------------------------------------------------------------------

TEMPLATE_RESPONSE_NO_BUG = """Você é um atendente técnico do SUAP respondendo a um usuário que reportou um erro.
Após análise, foi constatado que NÃO se trata de erro de código.

Gere uma resposta em português do Brasil seguindo EXATAMENTE este formato:

```
resolvido:
> Prezado(a) {nome},
>
> [Agradecimento pelo relato].
>
> A situação relatada não está relacionada a erro de funcionamento do sistema,
> mas a [explicação: configuração / dados cadastrais / prazo expirado].
>
> [Explicação técnica em linguagem acessível — o que acontece e por quê]
>
> [Orientação concreta: quem deve fazer o quê, com passos tipo "Acessar Admin > X > Y"]
>
> Caso a dúvida persista, estamos à disposição.
```

Regras:
- Tom formal e respeitoso — sempre "Prezado(a)" + nome completo
- NUNCA culpar o usuário
- Dar contexto técnico simplificado (sem jargão de código)
- Indicar quem deve resolver (coordenador, administrador, setor responsável)
- Incluir passos concretos
- Manter entre 4 e 8 parágrafos no bloco de citação"""

TEMPLATE_RESPONSE_BUG = """Você é um atendente técnico do SUAP respondendo a um usuário que reportou um erro.
Após análise, foi constatado que É um bug de código que será corrigido.

Gere uma resposta em português do Brasil seguindo EXATAMENTE este formato:

```
resolvido:
> Prezado(a) {nome},
>
> Obrigado por relatar o problema. [Reconhecimento: "Você estava correto(a)..."]
>
> [Explicação acessível do que estava errado — sem jargão técnico]
>
> A correção já foi implementada e está em processo de atualização do SUAP.
>
> Caso a dúvida persista, estamos à disposição.
```

Regras:
- Tom formal e respeitoso
- Reconhecer que o usuário estava correto ao reportar
- Explicar o erro de forma acessível
- Informar que a correção já foi feita
- Manter entre 3 e 6 parágrafos no bloco de citação"""


def build_response_prompt(result: dict, llm_analysis: str) -> str:
    """Constrói o prompt de resposta ao usuário.

    Args:
        result: dict com classification, context, structural (saída de analyze_issue)
        llm_analysis: texto da análise produzida pelo LLM (saída do prompt de análise)

    Returns:
        Prompt para o LLM gerar o rascunho de resposta.
    """
    classification = result['classification']
    nome = classification.get('interessado', 'Usuário')

    # Extrair tipo da análise do LLM
    tipo = extract_tipo_from_analysis(llm_analysis)
    is_bug = tipo == 'tipo::bug'

    template = TEMPLATE_RESPONSE_BUG if is_bug else TEMPLATE_RESPONSE_NO_BUG

    sections = [template.format(nome=nome)]

    sections.append('\n## Input\n')
    sections.append(f'**Interessado:** {nome}')
    if tipo:
        sections.append(f'**Classificação:** `{tipo}`')
    sections.append(f'**Análise:**\n{llm_analysis}')

    return '\n'.join(sections)


# ---------------------------------------------------------------------------
# Extração de tipo da resposta do LLM
# ---------------------------------------------------------------------------

VALID_TIPOS = {
    'tipo::bug',
    'tipo::configuracao',
    'tipo::dados-cadastrais',
    'tipo::prazo-expirado',
    'tipo::nao-e-erro',
}


def extract_tipo_from_analysis(analysis: str) -> str | None:
    """Extrai o label tipo::* da resposta do LLM.

    Procura padrões como:
        CLASSIFICAÇÃO: tipo::bug
        **tipo::configuracao**
        Classificação: tipo::nao-e-erro
    """
    match = re.search(r'(tipo::\S+)', analysis)
    if match:
        tipo = match.group(1).strip('*').strip('`').strip()
        if tipo in VALID_TIPOS:
            return tipo
    return None


# ---------------------------------------------------------------------------
# Compactação de código
# ---------------------------------------------------------------------------


def compact_code(source: str) -> str:
    """Compacta código removendo docstrings, comentários e linhas em branco."""
    lines = source.splitlines()
    result = []
    in_docstring = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith('#') and not stripped.startswith('#!'):
            continue
        if stripped.startswith(('"""', "'''")):
            quote = stripped[:3]
            if stripped.count(quote) >= 2 and len(stripped) > 3:
                continue
            in_docstring = not in_docstring
            continue
        if in_docstring:
            continue
        result.append(line)
    return '\n'.join(result)
