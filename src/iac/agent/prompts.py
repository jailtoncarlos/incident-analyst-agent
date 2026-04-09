"""Prompts encadeados para análise de incidentes.

Constrói prompts para o LLM a partir do resultado de analyze_issue(),
combinando dados da issue + análise estrutural + código-fonte.

Dois prompts:
    1. build_analysis_prompt: classificação + análise aprofundada + resolução
    2. build_response_prompt: rascunho de resposta ao usuário
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

from iac.agent.format import format_context_for_prompt
from iac.agent.deep import format_deep_analysis
from iac.agent.structural import format_structural_analysis


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

    # Análise profunda (models em profundidade)
    deep = result.get('deep', [])
    if deep:
        deep_text = format_deep_analysis(deep)
        if deep_text.strip():
            sections.append('\n---\n')
            sections.append(deep_text)

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
# Multi-prompt — LLM decide o que investigar
# ---------------------------------------------------------------------------

PROMPT_INVESTIGATION = """Você é um engenheiro de software sênior investigando uma issue de erro de produção do SUAP (ERP Django).

Analise os dados abaixo e o código da view. Depois, liste exatamente o que você PRECISA VER para entender a causa raiz.

{context}

---

Com base na descrição do usuário e no código da view, responda:

### 1. Primeira impressão
Descreva em 2-3 linhas o que parece estar acontecendo.

### 2. O que preciso investigar
Liste EXATAMENTE o que você precisa ver para confirmar a causa. Use este formato:

```
INVESTIGAR: app.models.Model.method_name — motivo
INVESTIGAR: app.models.Model — motivo (ver fields e constantes)
```

Liste no máximo 5 itens, priorizando o que é mais relevante para a causa raiz.

REGRAS: Não invente conclusões ainda. Foque em listar o que falta ver."""

PROMPT_EVIDENCE = """Você pediu para investigar código adicional. Aqui está o que foi encontrado:

{evidence}

---

Agora, com base em TODA a evidência (código da view + código adicional acima), responda em português do Brasil com EXATAMENTE estas 5 seções:

### 1. Análise do código
- Fluxo da view em linguagem acessível
- Models, forms e templates envolvidos e seu papel

### 2. Análise aprofundada
- Causa raiz do problema reportado pelo usuário
- Condições em que o erro/situação ocorre
- Marque com [ENCONTRADO] evidências no código, [INFERÊNCIA] hipóteses

### 3. Classificação
Responda com EXATAMENTE UMA destas opções (copie literal):
- CLASSIFICAÇÃO: tipo::bug
- CLASSIFICAÇÃO: tipo::configuracao
- CLASSIFICAÇÃO: tipo::dados-cadastrais
- CLASSIFICAÇÃO: tipo::prazo-expirado
- CLASSIFICAÇÃO: tipo::nao-e-erro

### 4. Sugestão de resolução
Se bug: diff sugerido (antes/depois com arquivo:linha).
Se não-bug: passos administrativos concretos.

### 5. Plano de simulação
- **Usuário afetado:** <matrícula ou CPF>
- **URL do erro:** <path relativo>
- **Admin para validação:** <username admin>
- **URL admin:** <path admin relativo>
- **O que verificar:** <o que confirmar>

REGRAS: Seja conciso. Use apenas o código fornecido. Não invente código."""


def build_investigation_prompt(result: dict) -> str:
    """Prompt 1: LLM analisa a view e lista o que precisa investigar."""
    structural_text = format_structural_analysis(result['structural'])
    context_text = format_context_for_prompt(result['context'])
    context_text = _strip_context_header(context_text)

    context = structural_text
    if context_text.strip():
        context += '\n---\n' + context_text

    return PROMPT_INVESTIGATION.format(context=context)


def parse_investigation_requests(llm_response: str) -> list[dict]:
    """Parseia pedidos de investigação do LLM.

    Procura linhas no formato:
        INVESTIGAR: app.models.Model.method_name — motivo
        INVESTIGAR: app.models.Model — motivo
    """
    requests = []
    for match in re.finditer(r'INVESTIGAR:\s*(\S+)(?:\s*[—\-]\s*(.+))?', llm_response):
        target = match.group(1).strip()
        reason = match.group(2).strip() if match.group(2) else ''

        # Limpar: remover () do final e backticks
        target = target.rstrip('()').strip('`')

        # Tratar formato arquivo:linha (ex: progressao_docente/views.py:1008)
        if '/' in target and '.py' in target:
            # É um path de arquivo — ignorar (código da view já está no prompt)
            logger.debug(f'Pedido ignorado (arquivo): {target}')
            continue

        # Tratar formato template (ex: app/templates/template.html)
        if '/templates/' in target or target.endswith('.html'):
            logger.debug(f'Pedido ignorado (template): {target}')
            continue

        parts = target.split('.')
        if len(parts) >= 4 and parts[1] == 'models':
            # app.models.Model.method
            requests.append({
                'type': 'method',
                'app': parts[0],
                'model': parts[2],
                'method': parts[3],
                'reason': reason,
            })
        elif len(parts) >= 3 and parts[1] == 'models':
            # app.models.Model
            requests.append({
                'type': 'model',
                'app': parts[0],
                'model': parts[2],
                'reason': reason,
            })
        elif len(parts) >= 3 and parts[1] == 'forms':
            # app.forms.Form
            requests.append({
                'type': 'form',
                'app': parts[0],
                'form': parts[2],
                'reason': reason,
            })
        elif len(parts) >= 3:
            # app.kind.Name.method (ex: comum.models.User.get_vinculo)
            requests.append({
                'type': 'method',
                'app': parts[0],
                'model': parts[2],
                'method': parts[-1],
                'reason': reason,
            })
        else:
            # Nome simples — tentar resolver
            requests.append({
                'type': 'symbol',
                'name': target,
                'reason': reason,
            })

    return requests


def resolve_investigation_requests(
    requests: list[dict],
    structure: dict,
    graph: dict,
    base_dir,
) -> str:
    """Resolve pedidos de investigação e retorna o código encontrado."""
    from pathlib import Path
    from iac.agent.tools import ler_funcao, localizar_arquivo

    sections = []

    for req in requests:
        if req['type'] == 'method':
            fqn = f'{req["app"]}.models.{req["model"]}'
            loc = localizar_arquivo(fqn, structure)
            if loc:
                model_data = structure.get('apps', {}).get(req['app'], {}).get('models', {}).get(req['model'], {})
                method_info = model_data.get('methods', {}).get(req['method'], {})
                method_line = method_info.get('line')
                if method_line:
                    src = ler_funcao(loc['file'], method_line, Path(base_dir), max_lines=30)
                    if src:
                        sections.append(f'### `{fqn}.{req["method"]}` ({loc["file"]}:{method_line})\n')
                        sections.append(f'```python\n{src}\n```\n')
                        continue
                # Método não encontrado por linha — tentar via AST
                src = ler_funcao(loc['file'], loc['line'], Path(base_dir), method=req['method'], max_lines=30)
                if src:
                    sections.append(f'### `{fqn}.{req["method"]}` ({loc["file"]})\n')
                    sections.append(f'```python\n{src}\n```\n')
                    continue
            sections.append(f'### `{fqn}.{req["method"]}` — não encontrado\n')

        elif req['type'] == 'model':
            fqn = f'{req["app"]}.models.{req["model"]}'
            model_data = structure.get('apps', {}).get(req['app'], {}).get('models', {}).get(req['model'], {})
            if model_data:
                sections.append(f'### `{fqn}` ({model_data.get("file", "?")}:{model_data.get("line", "?")})\n')
                fields = model_data.get('fields', [])
                if fields:
                    sections.append(f'**Fields:** {", ".join(f"`{f}`" for f in fields[:20])}\n')
                constants = model_data.get('constants', {})
                if constants:
                    sections.append('**Constantes:**')
                    for name, value in constants.items():
                        sections.append(f'- `{name} = {value}`')
                    sections.append('')
                methods = model_data.get('methods', {})
                if methods:
                    sections.append(f'**Métodos:** {", ".join(f"`{m}`" for m in list(methods.keys())[:15])}\n')
            else:
                sections.append(f'### `{fqn}` — não encontrado\n')

        elif req['type'] == 'form':
            fqn = f'{req["app"]}.forms.{req["form"]}'
            loc = localizar_arquivo(fqn, structure)
            if loc:
                src = ler_funcao(loc['file'], loc['line'], Path(base_dir), max_lines=30)
                if src:
                    sections.append(f'### `{fqn}` ({loc["file"]}:{loc["line"]})\n')
                    sections.append(f'```python\n{src}\n```\n')
                    continue
            sections.append(f'### `{fqn}` — não encontrado\n')

        elif req['type'] == 'symbol':
            loc = localizar_arquivo(req['name'], structure)
            if loc:
                src = ler_funcao(loc['file'], loc['line'], Path(base_dir), max_lines=30)
                if src:
                    sections.append(f'### `{req["name"]}` ({loc["file"]}:{loc["line"]})\n')
                    sections.append(f'```python\n{src}\n```\n')
                    continue
            sections.append(f'### `{req["name"]}` — não encontrado\n')

    return '\n'.join(sections)


def build_evidence_prompt(evidence: str, view_context: str | None = None) -> str:
    """Prompt 2: LLM recebe código adicional e faz análise completa.

    Args:
        evidence: Código dos models/métodos investigados
        view_context: Código da view (do prompt 1, para não perder contexto)
    """
    full_evidence = ''
    if view_context:
        full_evidence += view_context + '\n\n---\n\n'
    full_evidence += evidence
    return PROMPT_EVIDENCE.format(evidence=full_evidence)


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
