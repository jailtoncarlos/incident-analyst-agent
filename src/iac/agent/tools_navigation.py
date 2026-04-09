"""Ferramentas de navegação de código para o agente.

Funções para localizar e ler código-fonte a partir de structure.json:
resolver URLs para views, encontrar símbolos por nome qualificado e
extrair trechos de código-fonte de funções e classes via AST.

Todas as funções recebem structure/graph como dicts já carregados
e o base_dir do projeto. Não fazem I/O nos JSONs — isso é
responsabilidade do orquestrador.
"""

from __future__ import annotations

import ast
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


def resolver_rota(url_path: str, structure: dict) -> dict | None:
    """Resolve um URL path para a view associada.

    Os patterns em structure.json são relativos ao app (ex: "/chamado/<int:id>/"),
    enquanto a URL de entrada inclui o prefixo (ex: "/centralservicos/chamado/123/").
    A função tenta match com e sem o prefixo do app.

    Args:
        url_path: Path da URL (ex: "/centralservicos/chamado/516785/")
        structure: Conteúdo de structure.json

    Returns:
        dict com app, view_name, file, line ou None se não encontrar.
    """
    # Limpar query string e fragment
    url_path = re.sub(r'[?#].*', '', url_path)
    # Gerar variantes de normalização (IDs podem ser <int> ou <str>)
    norm_int = re.sub(r'/\d+', '/<int>', url_path)
    norm_str = re.sub(r'/\d+', '/<str>', url_path)
    # Normalizar slugs com hífens → <slug>
    norm_int = re.sub(r'/([a-z][\w-]*[a-z\d])(?=/|$)', lambda m: '/<slug>' if '-' in m.group(1) else m.group(0), norm_int)
    norm_str = re.sub(r'/([a-z][\w-]*[a-z\d])(?=/|$)', lambda m: '/<slug>' if '-' in m.group(1) else m.group(0), norm_str)
    normalizations = [norm_int.rstrip('/')]
    if norm_str != norm_int:
        normalizations.append(norm_str.rstrip('/'))

    best_match = None
    best_score = -1

    for app_name, app_data in structure.get('apps', {}).items():
        # Gerar variantes sem o prefixo do app para cada normalização
        candidates = list(normalizations)
        prefix = f'/{app_name}'
        for norm in normalizations:
            if norm.startswith(prefix):
                candidates.append(norm[len(prefix):])

        for url_entry in app_data.get('urls', []):
            pattern = url_entry['pattern'].rstrip('/')
            # Normalizar pattern: <int:id>, <int:pk>, <slug:s> → <int>, <slug>
            norm_pattern = re.sub(r'<\w+:\w+>', lambda m: '<' + m.group(0).split(':')[0][1:] + '>', pattern)

            for candidate in candidates:
                if norm_pattern == candidate:
                    view_name = url_entry['view'].split('.')[-1]
                    view_data = app_data.get('views', {}).get(view_name, {})
                    return {
                        'app': app_name,
                        'view_name': view_name,
                        'file': view_data.get('file', ''),
                        'line': view_data.get('line', 0),
                        'url_pattern': url_entry['pattern'],
                    }

                score = _match_score(norm_pattern, candidate)
                if score > best_score:
                    best_score = score
                    view_name = url_entry['view'].split('.')[-1]
                    view_data = app_data.get('views', {}).get(view_name, {})
                    best_match = {
                        'app': app_name,
                        'view_name': view_name,
                        'file': view_data.get('file', ''),
                        'line': view_data.get('line', 0),
                        'url_pattern': url_entry['pattern'],
                        'match_score': score,
                    }

    if best_match and best_score >= 3:
        return best_match
    return None


def _match_score(pattern: str, path: str) -> int:
    """Calcula score de similaridade entre pattern e path."""
    p_parts = [p for p in pattern.split('/') if p]
    u_parts = [p for p in path.split('/') if p]
    score = 0
    for pp, up in zip(p_parts, u_parts, strict=False):
        if pp == up:
            score += 2
        elif pp.startswith('<'):
            score += 1
    return score


def localizar_arquivo(symbol: str, structure: dict) -> dict | None:
    """Resolve um nome qualificado para arquivo e linha.

    Args:
        symbol: Nome qualificado (ex: "centralservicos.views.visualizar_chamado",
                "centralservicos.models.Chamado", ou apenas "visualizar_chamado")
        structure: Conteúdo de structure.json

    Returns:
        dict com app, kind, name, file, line ou None.
    """
    parts = symbol.split('.')
    apps = structure.get('apps', {})

    # Formato completo: app.kind.name (ex: centralservicos.views.visualizar_chamado)
    if len(parts) >= 3:
        app_name = parts[0]
        kind = parts[1]  # views, models, forms
        name = '.'.join(parts[2:])
        app_data = apps.get(app_name, {})
        comp = app_data.get(kind, {}).get(name)
        if comp:
            return {
                'app': app_name,
                'kind': kind,
                'name': name,
                'file': comp.get('file', ''),
                'line': comp.get('line', 0),
            }

    # Formato app.name (ex: centralservicos.visualizar_chamado)
    if len(parts) == 2:
        app_name, name = parts
        app_data = apps.get(app_name, {})
        for kind in ('views', 'models', 'forms', 'admin'):
            comp = app_data.get(kind, {}).get(name)
            if comp:
                return {
                    'app': app_name,
                    'kind': kind,
                    'name': name,
                    'file': comp.get('file', ''),
                    'line': comp.get('line', 0),
                }

    # Busca global por nome simples
    name = parts[-1]
    for app_name, app_data in apps.items():
        for kind in ('views', 'models', 'forms', 'admin'):
            comp = app_data.get(kind, {}).get(name)
            if comp:
                return {
                    'app': app_name,
                    'kind': kind,
                    'name': name,
                    'file': comp.get('file', ''),
                    'line': comp.get('line', 0),
                }
    return None


def ler_funcao(file_path: str, line: int, base_dir: Path, max_lines: int = 80, method: str | None = None) -> str | None:
    """Extrai o código-fonte de uma função ou classe a partir de arquivo:linha.

    Args:
        file_path: Caminho relativo ao base_dir (ex: "centralservicos/views.py")
        line: Número da linha onde a função/classe começa
        base_dir: Diretório raiz do projeto
        max_lines: Máximo de linhas a retornar (evita enviar funções enormes ao LLM)
        method: Se especificado, busca esse método dentro da classe na linha indicada

    Returns:
        String com o código-fonte ou None se não encontrar.
    """
    full_path = base_dir / file_path
    if not full_path.exists():
        return None

    try:
        source = full_path.read_text(encoding='utf-8', errors='replace')
        tree = ast.parse(source, filename=str(full_path))
    except SyntaxError:
        lines = source.splitlines()
        start = max(0, line - 1)
        end = min(len(lines), start + max_lines)
        return '\n'.join(lines[start:end])

    # Encontrar o nó AST que começa na linha indicada
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) and node.lineno == line:
            # Se pediu um método específico dentro de uma classe
            if method and isinstance(node, ast.ClassDef):
                for child in ast.iter_child_nodes(node):
                    if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef) and child.name == method:
                        end_line = child.end_lineno or (child.lineno + max_lines)
                        lines = source.splitlines()
                        start = child.lineno - 1
                        end = min(end_line, start + max_lines)
                        return '\n'.join(lines[start:end])
                # Método não encontrado na classe — retorna a classe
                return None

            end_line = node.end_lineno or (line + max_lines)
            lines = source.splitlines()
            start = line - 1
            end = min(end_line, start + max_lines)
            return '\n'.join(lines[start:end])

    # Se não encontrou pelo AST exato, retornar linhas brutas
    lines = source.splitlines()
    start = max(0, line - 1)
    end = min(len(lines), start + max_lines)
    return '\n'.join(lines[start:end])
