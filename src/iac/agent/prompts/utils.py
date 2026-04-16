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
    """Extrai o label principal de classificação da resposta do LLM.

    Args:
        analysis: Texto completo da resposta do LLM.

    Returns:
        Label tipo::* normalizado ou None.
    """
    result = extract_classificacao(analysis)
    return result['classificacao']


def extract_classificacao(analysis: str) -> dict:
    """Extrai classificação e subclassificação da resposta do LLM.

    Procura padrões como::

        CLASSIFICAÇÃO: tipo::nao-e-erro
        SUBCLASSIFICAÇÃO: tipo::prazo-expirado

    Ou formatos alternativos com markdown, prefixos variados, etc.

    Args:
        analysis: Texto completo da resposta do LLM.

    Returns:
        Dict com classificacao (str|None) e subclassificacao (str|None).
    """
    clean = analysis.replace('**', '').replace('`', '')

    classificacao = None
    subclassificacao = None

    # Classificação principal
    match = re.search(r'CLASSIFICA[CÇ][AÃ]O:\s*(.+?)(?:\n|/|$)', clean)
    if match:
        raw = match.group(1).strip()
        if '::' in raw:
            classificacao = _normalize_label(raw)
        # Checar se tem subclassificação na mesma linha: CLASSIFICAÇÃO: x / SUBCLASSIFICAÇÃO: y
        sub_inline = re.search(r'SUBCLASSIFICA[CÇ][AÃ]O:\s*(.+?)(?:\n|$)', clean[match.end():])
        if sub_inline:
            raw_sub = sub_inline.group(1).strip()
            if '::' in raw_sub:
                subclassificacao = _normalize_label(raw_sub)

    # Fallback: SUBCLASSIFICAÇÃO em linha separada
    if not subclassificacao:
        match_sub = re.search(r'SUBCLASSIFICA[CÇ][AÃ]O:\s*(.+?)(?:\n|$)', clean)
        if match_sub:
            raw_sub = match_sub.group(1).strip()
            if '::' in raw_sub:
                subclassificacao = _normalize_label(raw_sub)

    # Fallback: tipo::nome no texto (sem CLASSIFICAÇÃO:)
    if not classificacao:
        match_tipo = re.search(r'(tipo::[a-z][a-z0-9_-]*)', clean)
        if match_tipo:
            classificacao = match_tipo.group(1).strip()

    return {
        'classificacao': classificacao,
        'subclassificacao': subclassificacao,
    }


# Mapeamento de labels comuns fora do catálogo → label conhecido
_LABEL_ALIASES = {
    'tipo::avaliacao-nao-disponivel': 'tipo::prazo-expirado',
    'tipo::prazo-avaliacao': 'tipo::prazo-expirado',
    'tipo::tempo-expirado': 'tipo::prazo-expirado',
    'tipo::tempo-esgotado': 'tipo::prazo-expirado',
    'tipo::validacao-falhada': 'tipo::bug',
    'tipo::logica-incorreta': 'tipo::bug',
    'tipo::excecao-nao-tratada': 'tipo::bug',
    'tipo::erro-de-codigo': 'tipo::bug',
    'tipo::acesso-negado': 'tipo::permissao',
    'tipo::sem-permissao': 'tipo::permissao',
}


def normalize_to_known(tipo: str) -> str | None:
    """Normaliza label fora do catálogo para o mais próximo conhecido.

    Args:
        tipo: Label tipo::* fora de KNOWN_TIPOS.

    Returns:
        Label conhecido ou None se não houver mapeamento.
    """
    return _LABEL_ALIASES.get(tipo)


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
