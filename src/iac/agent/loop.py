"""Loop de análise interativo — LLM decide quando parar.

O LLM responde com uma ação por iteração:
    INVESTIGAR — pedir mais código
    VERIFICAR_BANCO — pedir simulação no banco
    ALTERAR_CODIGO — sugerir diff
    CLASSIFICAR — análise final (encerra o loop)
"""

from __future__ import annotations

import logging
import re

from iac.agent.format import format_context_for_prompt
from iac.agent.prompts.multi import parse_investigation_requests, resolve_investigation_requests
from iac.agent.prompts.utils import extract_tipo_from_analysis
from iac.agent.runner import send_to_llm
from iac.agent.structural import format_structural_analysis

logger = logging.getLogger(__name__)

PROMPT_LOOP = """Você é um engenheiro de software sênior investigando uma issue de erro de produção do SUAP (ERP Django).

{context}

---

{history}

---

Analise o que você já sabe e responda com EXATAMENTE UMA ação.

## Ações disponíveis

**Se precisa ver mais código:**
```
AÇÃO: INVESTIGAR
INVESTIGAR: app.models.Model.method — motivo
INVESTIGAR: app.models.Model — motivo (ver fields e constantes)
```

**Se precisa verificar dados no banco para confirmar hipótese:**
```
AÇÃO: VERIFICAR_BANCO
CONSULTA: Descrição em linguagem natural do que verificar no banco.
Exemplo: "Buscar DiscenteAptosAvaliacao com matricula=20231124120023, verificar situacao da avaliacao e data_liberacao_avaliacao"
```

**Se identificou necessidade de alterar código:**
```
AÇÃO: ALTERAR_CODIGO
ARQUIVO: caminho/do/arquivo.py
ANTES:
código atual
DEPOIS:
código corrigido
MOTIVO: explicação da alteração
```

**Se já tem informação suficiente para concluir:**
```
AÇÃO: CLASSIFICAR
CLASSIFICAÇÃO: tipo::nome

### Análise
Causa raiz, evidências [ENCONTRADO]/[INFERÊNCIA], resolução.

### Plano de verificação
O que verificar no banco e como admin para confirmar.
```

Responda com UMA ação apenas. Correlacione a descrição do usuário com constantes e campos do código."""

PROMPT_HISTORY_EMPTY = "Esta é a primeira iteração. Analise o código da view e a descrição do usuário."

PROMPT_HISTORY_PREFIX = "Histórico das iterações anteriores:\n\n"


def run_loop(
    result: dict,
    structure: dict,
    graph: dict,
    base_dir,
    llm: str,
    llm_model: str,
    llm_url: str | None,
    llm_key: str | None,
    max_iterations: int = 4,
) -> dict:
    """Executa loop interativo de análise.

    O LLM decide a cada iteração se precisa de mais informação ou se
    pode concluir. Retorna quando recebe CLASSIFICAR ou atinge max_iterations.

    Args:
        result: Dict retornado por analyze_issue().
        structure: Mapa estrutural (.iac/structure.json).
        graph: Grafo de dependências (.iac/graph.json).
        base_dir: Diretório raiz do projeto.
        llm: Backend LLM.
        llm_model: Nome do modelo.
        llm_url: Endpoint da API.
        llm_key: API key.
        max_iterations: Máximo de iterações do loop.

    Returns:
        Dict com analysis (texto), tipo, alteracoes, iterations.
    """
    # Contexto base (não muda entre iterações)
    structural_text = format_structural_analysis(result['structural'])
    context_text = format_context_for_prompt(result['context'])

    # Incluir constantes do deep (alto valor)
    deep_constants = ''
    for m in result.get('deep', []):
        if m.get('depth', 0) <= 1 and m.get('constants'):
            deep_constants += f'\n**Constantes de `{m["fqn"]}`:**\n'
            for name, value in m['constants'].items():
                deep_constants += f'- `{name} = {value}`\n'

    base_context = structural_text + '\n---\n' + context_text
    if deep_constants:
        base_context += '\n---\n' + deep_constants

    history_entries = []
    alteracoes = []
    final_analysis = None
    final_tipo = None

    for iteration in range(1, max_iterations + 1):
        logger.info(f'[Loop iteração {iteration}/{max_iterations}]')

        # Montar histórico
        if not history_entries:
            history = PROMPT_HISTORY_EMPTY
        else:
            history = PROMPT_HISTORY_PREFIX + '\n---\n'.join(history_entries)

        # Enviar prompt
        prompt = PROMPT_LOOP.format(context=base_context, history=history)
        logger.info(f'[Loop iteração {iteration}] Prompt: {len(prompt)} chars → enviando ao {llm}')
        logger.debug(f'[Loop iteração {iteration}] Prompt conteúdo:\n{prompt}')

        response = send_to_llm(prompt, llm, llm_model, llm_url, llm_key)
        if not response:
            logger.warning(f'[Loop iteração {iteration}] LLM não respondeu')
            break

        logger.info(f'[Loop iteração {iteration}] Resposta: {len(response)} chars')
        logger.debug(f'[Loop iteração {iteration}] Resposta conteúdo:\n{response}')

        # Detectar ação
        action = _detect_action(response)
        logger.info(f'[Loop iteração {iteration}] Ação: {action}')

        if action == 'CLASSIFICAR':
            final_analysis = response
            final_tipo = extract_tipo_from_analysis(response)
            logger.info(f'[Loop] Classificação final: {final_tipo}')
            break

        elif action == 'INVESTIGAR':
            requests = parse_investigation_requests(response)
            if requests:
                evidence = resolve_investigation_requests(requests, structure, graph, base_dir)
                history_entries.append(f'**Iteração {iteration} — INVESTIGAR**\n\nPedidos: {len(requests)}\n\nResultado:\n{evidence}')
                logger.info(f'[Loop iteração {iteration}] Evidência: {len(evidence)} chars')
            else:
                history_entries.append(f'**Iteração {iteration} — INVESTIGAR** (sem pedidos parseáveis)')

        elif action == 'VERIFICAR_BANCO':
            consulta = _extract_consulta(response)
            # TODO: executar no simulator (#44)
            history_entries.append(
                f'**Iteração {iteration} — VERIFICAR_BANCO**\n\n'
                f'Consulta solicitada: {consulta}\n\n'
                f'⚠️ Simulação no banco não implementada ainda. '
                f'Tente classificar com as informações disponíveis.'
            )
            logger.info(f'[Loop iteração {iteration}] VERIFICAR_BANCO: {consulta[:100]}')

        elif action == 'ALTERAR_CODIGO':
            alteracao = _extract_alteracao(response)
            alteracoes.append(alteracao)
            history_entries.append(f'**Iteração {iteration} — ALTERAR_CODIGO**\n\n{alteracao}')
            logger.info(f'[Loop iteração {iteration}] ALTERAR_CODIGO registrada')

        else:
            # Ação não reconhecida — tentar extrair classificação mesmo assim
            tipo = extract_tipo_from_analysis(response)
            if tipo:
                final_analysis = response
                final_tipo = tipo
                logger.info(f'[Loop] Classificação implícita: {final_tipo}')
                break
            history_entries.append(f'**Iteração {iteration}** (ação não reconhecida)\n\n{response[:500]}')

    # Se esgotou iterações sem CLASSIFICAR
    if not final_analysis and history_entries:
        logger.warning(f'[Loop] Max iterações ({max_iterations}) sem CLASSIFICAR — forçando')
        final_analysis = '\n---\n'.join(history_entries)
        final_tipo = extract_tipo_from_analysis(final_analysis)

    return {
        'analysis': final_analysis,
        'tipo': final_tipo,
        'alteracoes': alteracoes,
        'iterations': len(history_entries),
    }


def _detect_action(response: str) -> str:
    """Detecta a ação na resposta do LLM.

    Args:
        response: Texto da resposta do LLM.

    Returns:
        'CLASSIFICAR', 'INVESTIGAR', 'VERIFICAR_BANCO', 'ALTERAR_CODIGO' ou 'DESCONHECIDO'.
    """
    # Procurar AÇÃO: explícita
    match = re.search(r'AÇÃO:\s*(CLASSIFICAR|INVESTIGAR|VERIFICAR_BANCO|ALTERAR_CODIGO)', response)
    if match:
        return match.group(1)

    # Inferir pela presença de marcadores
    if 'CLASSIFICAÇÃO:' in response or 'tipo::' in response:
        return 'CLASSIFICAR'
    if 'INVESTIGAR:' in response:
        return 'INVESTIGAR'
    if 'VERIFICAR_BANCO' in response or 'CONSULTA:' in response:
        return 'VERIFICAR_BANCO'
    if 'ALTERAR_CODIGO' in response or 'ANTES:' in response:
        return 'ALTERAR_CODIGO'

    return 'DESCONHECIDO'


def _extract_consulta(response: str) -> str:
    """Extrai a consulta ao banco da resposta do LLM."""
    match = re.search(r'CONSULTA:\s*(.+?)(?:\n\n|\n```|$)', response, re.DOTALL)
    return match.group(1).strip() if match else response[:200]


def _extract_alteracao(response: str) -> str:
    """Extrai sugestão de alteração de código da resposta do LLM."""
    # Capturar bloco ARQUIVO + ANTES + DEPOIS + MOTIVO
    parts = []
    for label in ('ARQUIVO:', 'ANTES:', 'DEPOIS:', 'MOTIVO:'):
        match = re.search(rf'{label}\s*(.+?)(?:\n[A-Z]+:|$)', response, re.DOTALL)
        if match:
            parts.append(f'{label} {match.group(1).strip()}')
    return '\n'.join(parts) if parts else response[:500]
