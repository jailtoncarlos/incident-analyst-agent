"""Prompt de resposta — relatório técnico para o desenvolvedor."""

from __future__ import annotations

from iac.agent.prompts.utils import extract_tipo_from_analysis

PROMPT_RESPONSE = """Você é um engenheiro de software sênior de um sistema {system_description} \
produzindo um relatório técnico sobre um incidente reportado.

Com base na análise abaixo, gere um relatório conciso para o desenvolvedor que vai tratar o chamado.

## Orientações

- Escreva para um desenvolvedor, não para o usuário final
- Use linguagem técnica (nomes de models, views, constantes, campos)
- Estruture em seções claras:
  1. **Resumo** — o que foi reportado e classificação
  2. **Diagnóstico** — causa raiz identificada com referências ao código (arquivo:linha)
  3. **Evidências** — constantes, campos e métodos relevantes encontrados
  4. **Ação recomendada** — o que fazer para resolver
     - Se bug: descreva o fix necessário (arquivo, método, lógica)
     - Se configuração/dados: descreva a ação administrativa (admin, shell, SQL)
     - Se prazo expirado: descreva o prazo do sistema e se cabe reabertura
     - Se não é erro: explique o comportamento esperado
  5. **Verificação** — como confirmar que o diagnóstico está correto
- Marque com [ENCONTRADO] evidências no código e [INFERÊNCIA] hipóteses
- Seja conciso — máximo 20 linhas

## Dados do incidente

**Interessado:** {nome}
**Classificação:** {tipo}

## Análise técnica

{analise}"""


def build_response_prompt(result: dict, llm_analysis: str, profile: dict | None = None) -> str:
    """Constrói o prompt de relatório técnico.

    Args:
        result: Dict retornado por analyze_issue() com classification.
        llm_analysis: Texto da análise produzida pelo LLM.
        profile: Perfil do cliente (.iac/profile.yaml).

    Returns:
        Prompt para o LLM gerar o relatório técnico.
    """
    profile = profile or {}
    system_desc = profile.get('system_description', 'Django')

    classification = result['classification']
    nome = classification.get('interessado', 'Usuário')
    tipo = extract_tipo_from_analysis(llm_analysis, profile=profile) or classification.get('tipo_sugerido', 'não classificado')

    return PROMPT_RESPONSE.format(
        nome=nome,
        tipo=tipo,
        analise=llm_analysis,
        system_description=system_desc,
    )
