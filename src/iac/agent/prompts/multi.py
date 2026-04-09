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

Agora, com base em TODA a evidência (código da view + código adicional acima), responda em português do Brasil com as seguintes seções:

### 1. Análise do código
- Fluxo da view em linguagem acessível
- Models, forms e templates envolvidos e seu papel

### 2. Análise aprofundada
- Causa raiz do problema reportado pelo usuário
- Condições em que o erro/situação ocorre
- Marque com [ENCONTRADO] evidências no código, [INFERÊNCIA] hipóteses
- Correlacione a descrição do usuário com constantes e campos do código (ex: se o usuário menciona "prazo" ou "tempo", verifique constantes de tempo)

### 3. Classificação
Classifique com dois níveis:

**CLASSIFICAÇÃO:** label principal — o que é o problema.
**SUBCLASSIFICAÇÃO:** label secundário — o motivo específico.

Exemplos:
- CLASSIFICAÇÃO: tipo::nao-e-erro / SUBCLASSIFICAÇÃO: tipo::prazo-expirado
- CLASSIFICAÇÃO: tipo::bug / SUBCLASSIFICAÇÃO: tipo::logica-incorreta

Labels comuns: `bug`, `configuracao`, `dados-cadastrais`, `prazo-expirado`, `nao-e-erro`, `permissao`.

### 4. Sugestão de resolução
- Se bug: diff sugerido (antes/depois com arquivo:linha)
- Se configuração/dados: passos administrativos concretos
- Se prazo expirado: explique o prazo e como proceder
- Se não é erro: explique o comportamento esperado

### 5. Plano de verificação
Para confirmar a análise, indique o que verificar:
- **Usuário afetado:** matrícula ou CPF do interessado
- **URL do erro:** path relativo
- **O que verificar no banco:** dados a consultar para confirmar a hipótese
- **O que verificar como admin:** ação administrativa para validar

REGRAS: Seja conciso. Use apenas o código fornecido. Não invente código. Correlacione sempre a descrição do usuário com o código."""


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
            model_data = structure.get('apps', {}).get(req['app'], {}).get('models', {}).get(req['model'], {})
            loc = localizar_arquivo(fqn, structure)

            if model_data and loc:
                method_info = model_data.get('methods', {}).get(req['method'], {})
                method_line = method_info.get('line')
                if method_line:
                    src = ler_funcao(loc['file'], method_line, Path(base_dir), max_lines=30)
                    if src:
                        sections.append(f'### `{fqn}.{req["method"]}` ({loc["file"]}:{method_line})\n')
                        sections.append(f'```python\n{src}\n```\n')
                        continue

                # Fallback: evidência focal — destacar o que foi pedido + contexto relevante
                requested = req['method']
                constants = model_data.get('constants', {})
                fields = model_data.get('fields', [])
                methods = model_data.get('methods', {})

                sections.append(f'### `{fqn}` — foco em `{requested}` ({loc["file"]}:{loc["line"]})\n')

                # Destacar a constante/field pedida
                if requested in constants:
                    sections.append(f'**→ `{requested} = {constants[requested]}`**\n')
                elif requested in fields:
                    sections.append(f'**→ Campo `{requested}` encontrado no model**\n')

                # Fields temporais/relevantes (não todos)
                temporal_fields = [f for f in fields if any(k in f for k in ('data_', 'prazo', 'tempo', 'periodo', 'situacao', 'status'))]
                if temporal_fields:
                    sections.append(f'**Campos relevantes:** {", ".join(f"`{f}`" for f in temporal_fields)}\n')

                # Métodos que referenciam a constante pedida
                related_methods = []
                for m_name in methods:
                    if requested.lower() in m_name.lower():
                        related_methods.append(m_name)
                # Incluir código dos métodos relacionados
                if related_methods:
                    sections.append(f'**Métodos relacionados a `{requested}`:**\n')
                    for m_name in related_methods:
                        m_line = methods[m_name].get('line')
                        if m_line:
                            src = ler_funcao(loc['file'], m_line, Path(base_dir), max_lines=15)
                            if src:
                                sections.append(f'`{m_name}` (linha {m_line}):')
                                sections.append(f'```python\n{src}\n```\n')
                        else:
                            sections.append(f'- `{m_name}`\n')

                # Constantes apenas se poucas, senão só as temporais
                if len(constants) <= 5:
                    sections.append('**Constantes:**')
                    for name, value in constants.items():
                        marker = ' ← pedido' if name == requested else ''
                        sections.append(f'- `{name} = {value}`{marker}')
                    sections.append('')
                else:
                    temporal_constants = {k: v for k, v in constants.items() if any(t in k.lower() for t in ('tempo', 'prazo', 'dias', 'periodo'))}
                    if temporal_constants:
                        sections.append('**Constantes temporais:**')
                        for name, value in temporal_constants.items():
                            marker = ' ← pedido' if name == requested else ''
                            sections.append(f'- `{name} = {value}`{marker}')
                        sections.append('')
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
