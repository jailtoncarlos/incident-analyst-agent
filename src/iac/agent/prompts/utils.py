"""Utilitários de prompts — extração de tipo e compactação de código."""

from __future__ import annotations

import re

KNOWN_TIPOS = {
    'tipo::bug',
    'tipo::configuracao',
    'tipo::dados-cadastrais',
    'tipo::prazo-expirado',
    'tipo::nao-e-erro',
}


def extract_tipo_from_analysis(analysis: str) -> str | None:
    """Extrai o label tipo::* da resposta do LLM.

    Procura padrões como::

        CLASSIFICAÇÃO: tipo::bug
        CLASSIFICAÇÃO: tipo::permissao

    Aceita labels conhecidos e novos criados pelo LLM.

    Args:
        analysis: Texto completo da resposta do LLM.

    Returns:
        Label tipo::* encontrado ou None.
    """
    match = re.search(r'(tipo::[a-z][a-z0-9-]*)', analysis)
    if match:
        return match.group(1).strip('*').strip('`').strip()
    return None


def compact_code(source: str) -> str:
    """Compacta código removendo docstrings, comentários e linhas em branco.

    Args:
        source: Código-fonte Python original.

    Returns:
        Código compactado.
    """
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


def _strip_context_header(context: str) -> str:
    """Remove o header do format_context_for_prompt (já presente no structural)."""
    lines = context.split('\n')
    start = 0
    for i, line in enumerate(lines):
        if line.startswith('### Código'):
            start = i
            break
    return '\n'.join(lines[start:])
