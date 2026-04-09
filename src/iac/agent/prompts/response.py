"""Prompt de resposta ao usuário — rascunho para revisão humana."""

from __future__ import annotations

from iac.agent.prompts.utils import extract_tipo_from_analysis

PROMPT_RESPONSE = """Você é um atendente técnico do SUAP (Sistema Unificado de Administração Pública) \
respondendo a um usuário que reportou um problema.

Com base na análise técnica abaixo, gere um rascunho de resposta ao usuário.

## Orientações

- Comece com "Prezado(a) {nome},"
- Tom formal e respeitoso
- NUNCA culpe o usuário
- Explique o que foi identificado em linguagem acessível (sem jargão de código)
- Se for bug: reconheça que o usuário estava correto e informe que a correção será aplicada
- Se for configuração/dados: explique o que precisa ser ajustado e por quem (coordenador, secretaria, admin)
- Se for prazo expirado: explique o prazo do sistema e oriente sobre próximos passos
- Se não é erro: explique o comportamento esperado do sistema de forma clara
- Inclua orientação concreta: quem procurar, o que fazer, passos específicos
- Encerre com "Caso a dúvida persista, estamos à disposição."
- O texto deve ser precedido por "resolvido:" na primeira linha
- Use blocos de citação (>) para o corpo da resposta
- Mantenha entre 3 e 6 parágrafos

## Dados do incidente

**Interessado:** {nome}
**Classificação:** {tipo}

## Análise técnica

{analise}"""


def build_response_prompt(result: dict, llm_analysis: str) -> str:
    """Constrói o prompt de resposta ao usuário.

    Args:
        result: Dict retornado por analyze_issue() com classification.
        llm_analysis: Texto da análise produzida pelo LLM.

    Returns:
        Prompt para o LLM gerar o rascunho de resposta.
    """
    classification = result['classification']
    nome = classification.get('interessado', 'Usuário')
    tipo = extract_tipo_from_analysis(llm_analysis) or classification.get('tipo_sugerido', 'não classificado')

    return PROMPT_RESPONSE.format(
        nome=nome,
        tipo=tipo,
        analise=llm_analysis,
    )
