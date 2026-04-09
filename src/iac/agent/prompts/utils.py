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
    'tipo::permissao',
}

# Labels "nus" (sem tipo::) aceitos pelo parser — mapeiam para tipo::*
_BARE_LABELS = {
    'bug': 'tipo::bug',
    'configuracao': 'tipo::configuracao',
    'configuração': 'tipo::configuracao',
    'dados-cadastrais': 'tipo::dados-cadastrais',
    'prazo-expirado': 'tipo::prazo-expirado',
    'nao-e-erro': 'tipo::nao-e-erro',
    'não é erro': 'tipo::nao-e-erro',
    'permissao': 'tipo::permissao',
    'permissão': 'tipo::permissao',
    'logica-incorreta': 'tipo::bug',
    'comportamento-esperado': 'tipo::nao-e-erro',
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
        classificacao = _resolve_label(raw)
        # Checar subclassificação inline ou em linhas seguintes
        sub_inline = re.search(r'SUBCLASSIFICA[CÇ][AÃ]O:\s*(.+?)(?:\n|$)', clean[match.end():])
        if sub_inline:
            subclassificacao = _resolve_label(sub_inline.group(1).strip())

    # Fallback: SUBCLASSIFICAÇÃO em linha separada
    if not subclassificacao:
        match_sub = re.search(r'SUBCLASSIFICA[CÇ][AÃ]O:\s*(.+?)(?:\n|$)', clean)
        if match_sub:
            subclassificacao = _resolve_label(match_sub.group(1).strip())

    # Fallback: tipo::nome no texto (sem CLASSIFICAÇÃO:)
    if not classificacao:
        match_tipo = re.search(r'(tipo::[a-z][a-z0-9_-]*)', clean)
        if match_tipo:
            classificacao = match_tipo.group(1).strip()

    # Normalizar subclassificação para labels conhecidos
    if subclassificacao and subclassificacao not in KNOWN_TIPOS:
        normalized = normalize_to_known(subclassificacao)
        if normalized:
            subclassificacao = normalized

    return {
        'classificacao': classificacao,
        'subclassificacao': subclassificacao,
    }


def _resolve_label(raw: str) -> str | None:
    """Resolve um label bruto — com ou sem prefixo tipo::.

    Aceita: 'tipo::bug', 'Bug::Avaliação', 'bug', 'logica-incorreta'.
    """
    if '::' in raw:
        return _normalize_label(raw)
    # Label "nu" — tentar mapear
    bare = raw.lower().strip()
    if bare in _BARE_LABELS:
        return _BARE_LABELS[bare]
    # Tentar normalizar como se fosse tipo::
    normalized = _normalize_label(f'tipo::{raw}')
    if normalized and normalized in KNOWN_TIPOS:
        return normalized
    return _normalize_label(f'tipo::{raw}')


# Mapeamento de labels comuns fora do catálogo → label conhecido
_LABEL_ALIASES = {
    # prazo-expirado
    'tipo::avaliacao-nao-disponivel': 'tipo::prazo-expirado',
    'tipo::prazo-avaliacao': 'tipo::prazo-expirado',
    'tipo::tempo-expirado': 'tipo::prazo-expirado',
    'tipo::tempo-esgotado': 'tipo::prazo-expirado',
    'tipo::tempo-de-execucao-insuficiente': 'tipo::prazo-expirado',
    'tipo::tempo-insuficiente-para-avaliacao': 'tipo::prazo-expirado',
    'tipo::tempo-habil-para-avaliacao': 'tipo::prazo-expirado',
    'tipo::tempo-de-avaliacao-expirado': 'tipo::prazo-expirado',
    'tipo::tempo-de-avaliacao-insuficiente': 'tipo::prazo-expirado',
    # bug
    'tipo::validacao-falhada': 'tipo::bug',
    'tipo::logica-incorreta': 'tipo::bug',
    'tipo::excecao-nao-tratada': 'tipo::bug',
    'tipo::erro-de-codigo': 'tipo::bug',
    'tipo::erro-de-negocio': 'tipo::bug',
    # nao-e-erro
    'tipo::comportamento-esperado': 'tipo::nao-e-erro',
    'tipo::filtro-avaliacoes': 'tipo::nao-e-erro',
    # permissao
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
