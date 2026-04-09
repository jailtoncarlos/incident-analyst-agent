"""Prompt de análise — classificação + análise aprofundada + resolução.

Modo single-prompt: envia tudo de uma vez ao LLM.
"""

from __future__ import annotations

from iac.agent.deep import format_deep_analysis
from iac.agent.format import format_context_for_prompt
from iac.agent.prompts.utils import _strip_context_header
from iac.agent.structural import format_structural_analysis

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
    """Constrói o prompt de análise completo (modo single-prompt).

    Args:
        result: Dict retornado por analyze_issue() com structural, context e deep.

    Returns:
        Prompt completo para enviar ao LLM.
    """
    sections = [SYSTEM_ANALYSIS, '\n---\n']

    structural_text = format_structural_analysis(result['structural'])
    sections.append(structural_text)

    context_text = format_context_for_prompt(result['context'])
    context_text = _strip_context_header(context_text)
    if context_text.strip():
        sections.append('\n---\n')
        sections.append(context_text)

    deep = result.get('deep', [])
    if deep:
        deep_text = format_deep_analysis(deep)
        if deep_text.strip():
            sections.append('\n---\n')
            sections.append(deep_text)

    sections.append('\n---\n')
    sections.append(TEMPLATE_ANALYSIS)

    return '\n'.join(sections)
