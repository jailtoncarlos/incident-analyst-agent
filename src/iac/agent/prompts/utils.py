"""Utilitários de prompts — extração de tipo, taxonomia e compactação de código.

Toda taxonomia (known_tipos, aliases) vem do profile (.iac/profile.yaml).
Se nenhum profile for fornecido, usa defaults de settings.py.
"""

from __future__ import annotations

import re
import unicodedata

from iac.config.settings import DEFAULT_ALIASES, DEFAULT_KNOWN_TIPOS


def _normalize_label(raw: str) -> str:
    """Normaliza um label para formato tipo::nome-kebab-case.

    Args:
        raw: Label bruto (ex: 'Bug::Avaliação Não Preenchida').

    Returns:
        Label normalizado (ex: 'tipo::avaliacao-nao-preenchida').
    """
    raw = raw.strip('*').strip('`').strip()

    if '::' in raw:
        _prefix, nome = raw.split('::', 1)
    else:
        nome = raw

    nome = unicodedata.normalize('NFKD', nome).encode('ascii', 'ignore').decode('ascii')
    nome = nome.lower().strip()
    nome = re.sub(r'[\s_]+', '-', nome)
    nome = re.sub(r'[^a-z0-9-]', '', nome)
    nome = re.sub(r'-+', '-', nome).strip('-')

    return f'tipo::{nome}' if nome else None


def extract_tipo_from_analysis(analysis: str, profile: dict | None = None) -> str | None:
    """Extrai o label principal de classificação da resposta do LLM."""
    result = extract_classificacao(analysis, profile=profile)
    return result['classificacao']


def extract_classificacao(analysis: str, profile: dict | None = None) -> dict:
    """Extrai classificação e subclassificação da resposta do LLM.

    Args:
        analysis: Texto completo da resposta do LLM.
        profile: Perfil do cliente com taxonomy (known_tipos, aliases).

    Returns:
        Dict com classificacao (str|None) e subclassificacao (str|None).
    """
    taxonomy = _get_taxonomy(profile)
    known_tipos = taxonomy['known_tipos']
    aliases = taxonomy['aliases']

    clean = analysis.replace('**', '').replace('`', '')

    classificacao = None
    subclassificacao = None

    # Classificação principal
    match = re.search(r'CLASSIFICA[CÇ][AÃ]O:\s*(.+?)(?:\n|/|$)', clean)
    if match:
        raw = match.group(1).strip()
        classificacao = _resolve_label(raw, known_tipos, aliases)
        sub_inline = re.search(r'SUBCLASSIFICA[CÇ][AÃ]O:\s*(.+?)(?:\n|$)', clean[match.end():])
        if sub_inline:
            subclassificacao = _resolve_label(sub_inline.group(1).strip(), known_tipos, aliases)

    # Fallback: SUBCLASSIFICAÇÃO em linha separada
    if not subclassificacao:
        match_sub = re.search(r'SUBCLASSIFICA[CÇ][AÃ]O:\s*(.+?)(?:\n|$)', clean)
        if match_sub:
            subclassificacao = _resolve_label(match_sub.group(1).strip(), known_tipos, aliases)

    # Fallback: tipo::nome no texto (sem CLASSIFICAÇÃO:)
    if not classificacao:
        match_tipo = re.search(r'(tipo::[a-z][a-z0-9_-]*)', clean)
        if match_tipo:
            classificacao = match_tipo.group(1).strip()

    # Normalizar para labels conhecidos
    if classificacao and classificacao not in known_tipos:
        classificacao = aliases.get(classificacao, classificacao)
    if subclassificacao and subclassificacao not in known_tipos:
        subclassificacao = aliases.get(subclassificacao, subclassificacao)

    return {
        'classificacao': classificacao,
        'subclassificacao': subclassificacao,
    }


def normalize_to_known(tipo: str, profile: dict | None = None) -> str | None:
    """Normaliza label fora do catálogo para o mais próximo conhecido."""
    taxonomy = _get_taxonomy(profile)
    return taxonomy['aliases'].get(tipo)


def _resolve_label(raw: str, known_tipos: set, aliases: dict) -> str | None:
    """Resolve um label bruto — com ou sem prefixo tipo::."""
    if '::' in raw:
        normalized = _normalize_label(raw)
        if normalized and normalized not in known_tipos:
            normalized = aliases.get(normalized, normalized)
        return normalized

    # Label "nu" — normalizar e tentar resolver
    normalized = _normalize_label(f'tipo::{raw}')
    if not normalized:
        return None
    if normalized in known_tipos:
        return normalized
    return aliases.get(normalized, normalized)


def _get_taxonomy(profile: dict | None) -> dict:
    """Extrai taxonomia do profile ou retorna defaults."""
    if profile and 'taxonomy' in profile:
        tax = profile['taxonomy']
        known = tax.get('known_tipos', DEFAULT_KNOWN_TIPOS)
        als = tax.get('aliases', DEFAULT_ALIASES)
        return {
            'known_tipos': set(known) if not isinstance(known, set) else known,
            'aliases': dict(als),
        }
    return {
        'known_tipos': set(DEFAULT_KNOWN_TIPOS),
        'aliases': dict(DEFAULT_ALIASES),
    }


def compact_code(source: str) -> str:
    """Compacta código removendo docstrings, comentários e linhas em branco."""
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
