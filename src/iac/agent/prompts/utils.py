"""Utilitários de prompts — extração de tipo e compactação de código."""

from __future__ import annotations

import re
import unicodedata

KNOWN_TIPOS = {
    'tipo::bug',
    'tipo::configuracao',
    'tipo::dados-cadastrais',
    'tipo::prazo-expirado',
    'tipo::nao-e-erro',
}


def _normalize_label(raw: str) -> str:
    """Normaliza um label para formato tipo::nome-kebab-case.

    Args:
        raw: Label bruto (ex: 'Bug::Avaliação Não Preenchida').

    Returns:
        Label normalizado (ex: 'tipo::avaliacao-nao-preenchida').
    """
    # Remover markdown
    raw = raw.strip('*').strip('`').strip()

    # Separar prefixo e nome
    if '::' in raw:
        _prefix, nome = raw.split('::', 1)
    else:
        nome = raw

    # Remover acentos
    nome = unicodedata.normalize('NFKD', nome).encode('ascii', 'ignore').decode('ascii')

    # Lowercase, substituir espaços e underscores por hífens
    nome = nome.lower().strip()
    nome = re.sub(r'[\s_]+', '-', nome)

    # Remover caracteres inválidos
    nome = re.sub(r'[^a-z0-9-]', '', nome)

    # Remover hífens duplicados e nas pontas
    nome = re.sub(r'-+', '-', nome).strip('-')

    return f'tipo::{nome}' if nome else None


def extract_tipo_from_analysis(analysis: str) -> str | None:
    """Extrai o label de classificação da resposta do LLM.

    Procura padrões como::

        CLASSIFICAÇÃO: tipo::bug
        CLASSIFICAÇÃO: bug::tempo_habil
        **CLASSIFICAÇÃO:** Bug::Avaliação Não Preenchida
        **CLASSIFICAR** CLASSIFICAÇÃO: tipo::prazo-expirado

    Aceita qualquer formato e normaliza para tipo::nome-kebab-case.

    Args:
        analysis: Texto completo da resposta do LLM.

    Returns:
        Label tipo::* normalizado ou None.
    """
    # Limpar markdown do texto para facilitar matching
    clean = analysis.replace('**', '').replace('`', '')

    # Formato padrão: tipo::nome
    match = re.search(r'(tipo::[a-z][a-z0-9_-]*)', clean)
    if match:
        return match.group(1).strip()

    # CLASSIFICAÇÃO: xxx::yyy (qualquer prefixo, qualquer formato de nome)
    match = re.search(r'CLASSIFICA[CÇ][AÃ]O:\s*(.+?)(?:\n|$)', clean)
    if match:
        raw = match.group(1).strip()
        if '::' in raw:
            return _normalize_label(raw)

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
