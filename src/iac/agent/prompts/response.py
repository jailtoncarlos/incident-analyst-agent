"""Prompt de resposta ao usuário — rascunho "Prezado(a)..."."""

from __future__ import annotations

from iac.agent.prompts.utils import extract_tipo_from_analysis

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
        result: Dict retornado por analyze_issue() com classification.
        llm_analysis: Texto da análise produzida pelo LLM.

    Returns:
        Prompt para o LLM gerar o rascunho de resposta.
    """
    classification = result['classification']
    nome = classification.get('interessado', 'Usuário')

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
