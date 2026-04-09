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
from iac.agent.prompts.utils import KNOWN_TIPOS, extract_tipo_from_analysis, normalize_to_known
from iac.agent.runner import send_to_llm
from iac.agent.structural import format_structural_analysis

logger = logging.getLogger(__name__)

PROMPT_LOOP = """Você é um engenheiro de software sênior investigando uma issue de erro de produção do SUAP (ERP Django).

{context}

---

{history}

---

Analise o que você já sabe e escolha UMA ação.

## Regras importantes
- NÃO repita investigações já feitas (veja o histórico acima)
- Se já tem código + constantes + descrição do usuário, avance para CLASSIFICAR
- Se o interessado é Aluno e a view é de área discente, não assuma erro de permissão sem evidência explícita
- Se a descrição menciona "tempo", "prazo", "hábil" ou "período", priorize constantes temporais (TEMPO_*, PRAZO_*, DIAS_*)
- Correlacione a descrição do usuário com constantes do código (ex: "tempo hábil" → TEMPO_AVALIACAO)
- Se precisa confirmar com dados reais, use VERIFICAR_BANCO (não INVESTIGAR)

## Ações disponíveis

**INVESTIGAR** — pedir código que ainda não viu:
```
AÇÃO: INVESTIGAR
INVESTIGAR: app.models.Model.method — motivo
```

**VERIFICAR_BANCO** — confirmar hipótese com dados reais:
```
AÇÃO: VERIFICAR_BANCO
CONSULTA: descrição do que verificar no banco
```

**ALTERAR_CODIGO** — sugerir correção:
```
AÇÃO: ALTERAR_CODIGO
ARQUIVO: caminho/arquivo.py
ANTES: código atual
DEPOIS: código corrigido
MOTIVO: explicação
```

**CLASSIFICAR** — concluir a análise:
```
AÇÃO: CLASSIFICAR
CLASSIFICAÇÃO: tipo::label-principal
SUBCLASSIFICAÇÃO: tipo::motivo-especifico

### Análise
Causa raiz com [ENCONTRADO] e [INFERÊNCIA].

### Resolução
O que fazer para resolver.

### Plano de verificação
O que verificar no banco e como admin.
```"""

PROMPT_HISTORY_EMPTY = "Esta é a primeira iteração. Analise o código da view, as constantes dos models e a descrição do usuário."

PROMPT_HISTORY_PREFIX = "## Histórico — o que já foi investigado (NÃO repita)\n\n"

PROMPT_REPAIR = """Sua resposta anterior contém análise mas falta a classificação no formato esperado.

Responda APENAS com:

CLASSIFICAÇÃO: tipo::label-principal
SUBCLASSIFICAÇÃO: tipo::motivo-especifico

Labels válidos: bug, configuracao, dados-cadastrais, prazo-expirado, nao-e-erro, permissao.
Se nenhum se aplica, crie um descritivo em kebab-case.

Sua análise anterior:
{analysis_snippet}"""


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
    min_iterations: int = 2,
    initial_history: str | None = None,
) -> dict:
    """Executa loop interativo de análise.

    O LLM decide a cada iteração se precisa de mais informação ou se
    pode concluir. Retorna quando recebe CLASSIFICAR ou atinge max_iterations.
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
    if initial_history:
        history_entries.append(initial_history)
    alteracoes = []
    investigated = set()
    final_analysis = None
    final_tipo = None
    consecutive_investigate = 0

    for iteration in range(1, max_iterations + 1):
        logger.info(f'[Loop iteração {iteration}/{max_iterations}]')

        # Na última iteração, forçar CLASSIFICAR
        force_classify = iteration == max_iterations

        # Montar histórico
        if not history_entries:
            history = PROMPT_HISTORY_EMPTY
        else:
            history = PROMPT_HISTORY_PREFIX + '\n---\n'.join(history_entries)
            if investigated:
                history += f'\n\n**Já investigados:** {", ".join(f"`{m}`" for m in investigated)}'

        # Se forçando classificação, adicionar instrução
        if force_classify:
            history += '\n\n⚠️ **Esta é a última iteração. Você DEVE responder com AÇÃO: CLASSIFICAR.**'

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
            tipo_candidate = extract_tipo_from_analysis(response)

            # Impedir classificação prematura (antes de min_iterations)
            if iteration < min_iterations and not force_classify:
                logger.info(f'[Loop iteração {iteration}] CLASSIFICAR prematuro (min_iterations={min_iterations}) — forçando investigação')
                history_entries.append(
                    f'**Iteração {iteration} — CLASSIFICAR prematuro**\n\n'
                    f'Você classificou como `{tipo_candidate}`, mas ainda não investigou o suficiente.\n'
                    f'Use INVESTIGAR para buscar constantes temporais (ex: TEMPO_AVALIACAO) e métodos relacionados antes de concluir.'
                )
                continue

            # Validar taxonomia — normalizar label se fora do catálogo
            if tipo_candidate and tipo_candidate not in KNOWN_TIPOS:
                normalized = normalize_to_known(tipo_candidate)
                if normalized:
                    logger.info(f'[Loop] Label normalizado: {tipo_candidate} → {normalized}')
                    tipo_candidate = normalized

            # Se não extraiu tipo, tentar repair prompt
            if not tipo_candidate:
                tipo_candidate = _repair_classification(response, llm, llm_model, llm_url, llm_key)

            final_analysis = response
            final_tipo = tipo_candidate
            logger.info(f'[Loop] Classificação final: {final_tipo}')
            break

        elif action == 'INVESTIGAR':
            consecutive_investigate += 1
            requests = parse_investigation_requests(response)
            # Filtrar pedidos já investigados
            new_requests = [r for r in requests if _request_key(r) not in investigated]
            if new_requests:
                for r in new_requests:
                    investigated.add(_request_key(r))
                evidence = resolve_investigation_requests(new_requests, structure, graph, base_dir)
                history_entries.append(f'**Iteração {iteration} — INVESTIGAR**\n\nPedidos: {len(new_requests)}\n\nResultado:\n{evidence}')
                logger.info(f'[Loop iteração {iteration}] Evidência: {len(evidence)} chars ({len(new_requests)} novos pedidos)')
            elif requests:
                # Todos já investigados — escalonar estratégia
                # Enriquecer com métodos relacionados ao último pedido
                last_req = requests[0]
                enrichment = _enrich_on_repeat(last_req, structure, graph, base_dir)
                hint = (
                    f'**Iteração {iteration} — INVESTIGAR** (todos já investigados)\n\n'
                    f'Você já investigou: {", ".join(f"`{m}`" for m in investigated)}.\n\n'
                )
                if enrichment:
                    hint += f'**Enriquecimento automático:**\n{enrichment}\n\n'
                hint += 'Avance para CLASSIFICAR ou use VERIFICAR_BANCO para confirmar com dados reais.'
                history_entries.append(hint)
                logger.info(f'[Loop iteração {iteration}] Pedidos repetidos — escalonando com enriquecimento')
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
            if not tipo:
                tipo = _repair_classification(response, llm, llm_model, llm_url, llm_key)
            if tipo:
                if tipo not in KNOWN_TIPOS:
                    normalized = normalize_to_known(tipo)
                    if normalized:
                        tipo = normalized
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
    clean = response.replace('**', '').replace('`', '')

    # Procurar AÇÃO: explícita
    match = re.search(r'AÇÃO:\s*(CLASSIFICAR|INVESTIGAR|VERIFICAR_BANCO|ALTERAR_CODIGO)', clean)
    if match:
        return match.group(1)

    # Inferir pela presença de marcadores
    if 'CLASSIFICAÇÃO:' in clean or 'CLASSIFICACAO:' in clean or 'tipo::' in clean:
        return 'CLASSIFICAR'
    # CLASSIFICAR sozinho (com ou sem markdown)
    if re.search(r'^\s*CLASSIFICAR\s*$', clean, re.MULTILINE):
        return 'CLASSIFICAR'
    # Seções finais presentes → classificação implícita
    if '### Análise' in response and '### Resolução' in response:
        return 'CLASSIFICAR'
    if 'INVESTIGAR:' in clean:
        return 'INVESTIGAR'
    if 'VERIFICAR_BANCO' in clean or 'CONSULTA:' in clean:
        return 'VERIFICAR_BANCO'
    if 'ALTERAR_CODIGO' in clean or 'ANTES:' in clean:
        return 'ALTERAR_CODIGO'

    return 'DESCONHECIDO'


def _request_key(req: dict) -> str:
    """Gera chave única para um pedido de investigação."""
    if req.get('type') == 'method':
        return f'{req.get("app")}.{req.get("model")}.{req.get("method")}'
    if req.get('type') == 'model':
        return f'{req.get("app")}.{req.get("model")}'
    if req.get('type') == 'form':
        return f'{req.get("app")}.{req.get("form")}'
    return req.get('name', str(req))


def _enrich_on_repeat(req: dict, structure: dict, graph: dict, base_dir) -> str:
    """Enriquece com métodos relacionados quando LLM repete investigação."""
    from pathlib import Path

    from iac.agent.tools import ler_funcao

    app = req.get('app', '')
    model_name = req.get('model', '')
    requested = req.get('method', '')
    model_data = structure.get('apps', {}).get(app, {}).get('models', {}).get(model_name, {})

    if not model_data or not requested:
        return ''

    sections = []
    methods = model_data.get('methods', {})
    loc_file = model_data.get('file', '')

    # Buscar métodos cujo nome contenha a constante pedida (limitar a 4)
    found = 0
    for m_name, m_info in methods.items():
        if found >= 4:
            break
        if requested.lower().replace('tempo_', '') in m_name.lower():
            m_line = m_info.get('line')
            if m_line and loc_file:
                src = ler_funcao(loc_file, m_line, Path(base_dir), max_lines=10)
                if src:
                    sections.append(f'**`{model_name}.{m_name}`** (linha {m_line}):\n```python\n{src}\n```')
                    found += 1

    return '\n'.join(sections)


def _repair_classification(response: str, llm: str, llm_model: str, llm_url: str | None, llm_key: str | None) -> str | None:
    """Tenta extrair classificação via repair prompt curto."""
    snippet = response[:1500]
    prompt = PROMPT_REPAIR.format(analysis_snippet=snippet)
    logger.info(f'[Loop] Repair prompt: {len(prompt)} chars → enviando ao {llm}')
    repair_response = send_to_llm(prompt, llm, llm_model, llm_url, llm_key)
    if not repair_response:
        return None
    tipo = extract_tipo_from_analysis(repair_response)
    if tipo:
        logger.info(f'[Loop] Repair extraiu: {tipo}')
    return tipo


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
