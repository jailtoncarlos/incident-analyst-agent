"""Prompts multi-prompt — LLM decide o que investigar.

Modo iterativo: prompt 1 (investigação) → parse pedidos → resolver evidência → prompt 2 (análise).
"""

from __future__ import annotations

import logging
import re

from iac.agent.format import format_context_for_prompt
from iac.agent.prompts.utils import _strip_context_header
from iac.agent.structural import format_structural_analysis

logger = logging.getLogger(__name__)

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
    """Prompt 1: LLM analisa a view e lista o que precisa investigar.

    Args:
        result: Dict retornado por analyze_issue() com structural e context.

    Returns:
        Prompt formatado para enviar ao LLM no modo multi-prompt.
    """
    structural_text = format_structural_analysis(result['structural'])
    context_text = format_context_for_prompt(result['context'])
    context_text = _strip_context_header(context_text)

    context = structural_text
    if context_text.strip():
        context += '\n---\n' + context_text

    return PROMPT_INVESTIGATION.format(context=context)


def parse_investigation_requests(llm_response: str) -> list[dict]:
    """Parseia pedidos de investigação do LLM.

    Procura linhas no formato::

        INVESTIGAR: app.models.Model.method_name — motivo
        INVESTIGAR: app.models.Model — motivo

    Args:
        llm_response: Resposta do LLM ao prompt de investigação.

    Returns:
        Lista de dicts com type, app, model/form/name, method e reason.
    """
    requests = []
    for match in re.finditer(r'INVESTIGAR:\s*(\S+)(?:\s*[—\-]\s*(.+))?', llm_response):
        target = match.group(1).strip()
        reason = match.group(2).strip() if match.group(2) else ''

        target = target.rstrip('()').strip('`')

        if '/' in target and '.py' in target:
            logger.debug(f'Pedido ignorado (arquivo): {target}')
            continue
        if '/templates/' in target or target.endswith('.html'):
            logger.debug(f'Pedido ignorado (template): {target}')
            continue

        parts = target.split('.')
        if len(parts) >= 4 and parts[1] == 'models':
            requests.append({'type': 'method', 'app': parts[0], 'model': parts[2], 'method': parts[3], 'reason': reason})
        elif len(parts) >= 3 and parts[1] == 'models':
            requests.append({'type': 'model', 'app': parts[0], 'model': parts[2], 'reason': reason})
        elif len(parts) >= 3 and parts[1] == 'forms':
            requests.append({'type': 'form', 'app': parts[0], 'form': parts[2], 'reason': reason})
        elif len(parts) >= 3:
            requests.append({'type': 'method', 'app': parts[0], 'model': parts[2], 'method': parts[-1], 'reason': reason})
        else:
            requests.append({'type': 'symbol', 'name': target, 'reason': reason})

    return requests


def resolve_investigation_requests(requests: list[dict], structure: dict, graph: dict, base_dir) -> str:
    """Resolve pedidos de investigação e retorna o código encontrado.

    Args:
        requests: Lista de dicts retornada por parse_investigation_requests().
        structure: Mapa estrutural do projeto (.iac/structure.json).
        graph: Grafo de dependências (.iac/graph.json).
        base_dir: Diretório raiz do projeto inspecionado.

    Returns:
        Texto em Markdown com o código-fonte de cada componente solicitado.
    """
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
        evidence: Código dos models/métodos investigados.
        view_context: Código da view (do prompt 1, para não perder contexto).

    Returns:
        Prompt formatado com evidência + instruções de análise.
    """
    full_evidence = ''
    if view_context:
        full_evidence += view_context + '\n\n---\n\n'
    full_evidence += evidence
    return PROMPT_EVIDENCE.format(evidence=full_evidence)
