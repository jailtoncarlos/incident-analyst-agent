"""Prompt de análise — classificação + análise aprofundada + resolução.

Modo single-prompt: envia tudo de uma vez ao LLM.
"""

from __future__ import annotations

from iac.agent.deep import format_deep_analysis
from iac.agent.format import format_context_for_prompt
from iac.agent.prompts.utils import _strip_context_header
from iac.agent.structural import format_structural_analysis

SYSTEM_ANALYSIS = """Você é um engenheiro de software sênior analisando uma issue de erro de produção \
de um sistema {system_description}.

Você receberá:
- Dados da issue (extraídos automaticamente da descrição)
- Análise estrutural (componentes e fluxo obtidos via inspeção do código)
- Código-fonte da view e referências (métodos, models, forms)

Responda em português do Brasil com as seguintes seções."""

TEMPLATE_ANALYSIS = """### 1. Análise do código
- Descreva o fluxo da view em linguagem acessível
- Quais models, forms e templates estão envolvidos e qual o papel de cada um

### 2. Análise aprofundada
- Causa raiz provável do problema reportado pelo usuário
- Condições em que o erro/situação ocorre
- Referências a arquivo:linha do código que sustentam a análise
- Marque com [ENCONTRADO] evidências no código, [INFERÊNCIA] hipóteses
- Correlacione a descrição do usuário com constantes e campos do código (ex: se o usuário menciona "prazo" ou "tempo", verifique constantes de tempo como TEMPO_AVALIACAO)

### 3. Classificação
Classifique com dois níveis:

**CLASSIFICAÇÃO:** label principal — o que é o problema.
**SUBCLASSIFICAÇÃO:** label secundário — o motivo específico.

Exemplos:
- CLASSIFICAÇÃO: tipo::bug / SUBCLASSIFICAÇÃO: tipo::logica-incorreta
- CLASSIFICAÇÃO: tipo::nao-e-erro / SUBCLASSIFICAÇÃO: tipo::prazo-expirado
- CLASSIFICAÇÃO: tipo::nao-e-erro / SUBCLASSIFICAÇÃO: tipo::configuracao
- CLASSIFICAÇÃO: tipo::bug / SUBCLASSIFICAÇÃO: tipo::excecao-nao-tratada

Labels comuns: `bug`, `configuracao`, `dados-cadastrais`, `prazo-expirado`, `nao-e-erro`, `permissao`.
Se nenhum se aplica, crie um descritivo.

### 4. Sugestão de resolução
- Se bug: inclua diff sugerido (antes/depois com arquivo:linha)
- Se configuração/dados: passos administrativos concretos (quem, onde, o quê)
- Se prazo expirado: explique o prazo do sistema e como proceder
- Se não é erro: explique o comportamento esperado

### 5. Plano de verificação
Para confirmar a análise, indique o que verificar:
- **Usuário afetado:** matrícula ou CPF do interessado
- **URL do erro:** path relativo da URL com erro
- **O que verificar no banco:** dados a consultar para confirmar a hipótese
- **O que verificar como admin:** ação administrativa para validar

REGRAS:
- Seja conciso e baseie-se apenas no código fornecido
- Não invente código inexistente
- Use [ENCONTRADO] para evidências e [INFERÊNCIA] para hipóteses
- Correlacione sempre a descrição do usuário com o código analisado
{rules}"""


def build_analysis_prompt(result: dict, include_deep: bool = True, profile: dict | None = None) -> str:
    """Constrói o prompt de análise completo (modo single-prompt).

    Args:
        result: Dict retornado por analyze_issue() com structural, context e deep.
        include_deep: Se False, omite a análise profunda do prompt.
        profile: Perfil do cliente (.iac/profile.yaml) com system_description e rules.

    Returns:
        Prompt completo para enviar ao LLM.
    """
    profile = profile or {}
    system_desc = profile.get('system_description', 'Django')
    rules = profile.get('rules', [])
    rules_text = '\n'.join(f'- {r}' for r in rules) if rules else ''

    system = SYSTEM_ANALYSIS.format(system_description=system_desc)
    template = TEMPLATE_ANALYSIS.format(rules=rules_text)

    sections = [system, '\n---\n']

    structural_text = format_structural_analysis(result['structural'])
    sections.append(structural_text)

    context_text = format_context_for_prompt(result['context'])
    context_text = _strip_context_header(context_text)
    if context_text.strip():
        sections.append('\n---\n')
        sections.append(context_text)

    if include_deep:
        deep = result.get('deep', [])
        if deep:
            deep_text = format_deep_analysis(deep)
            if deep_text.strip():
                sections.append('\n---\n')
                sections.append(deep_text)

    sections.append('\n---\n')
    sections.append(template)

    return '\n'.join(sections)
