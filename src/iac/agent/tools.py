"""Ferramentas de inspeção de código para o agente.

Consultam .iac/structure.json e .iac/graph.json para navegar
o código sem grep, permitindo que modelos pequenos (7B) operem
com eficiência em repositórios grandes.

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


# ---------------------------------------------------------------------------
# resolver_rota: URL path → view
# ---------------------------------------------------------------------------


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
    # Normalizar: remover IDs numéricos para casar com patterns parametrizados
    normalized = re.sub(r'/\d+', '/<int>', url_path)
    normalized = normalized.rstrip('/')

    best_match = None
    best_score = -1

    for app_name, app_data in structure.get('apps', {}).items():
        # Gerar variantes sem o prefixo do app
        candidates = [normalized]
        prefix = f'/{app_name}'
        if normalized.startswith(prefix):
            candidates.append(normalized[len(prefix):])

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
    for pp, up in zip(p_parts, u_parts):
        if pp == up:
            score += 2
        elif pp.startswith('<'):
            score += 1
    return score


# ---------------------------------------------------------------------------
# localizar_arquivo: símbolo → arquivo:linha
# ---------------------------------------------------------------------------


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
        for kind in ('views', 'models', 'forms'):
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
        for kind in ('views', 'models', 'forms'):
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


# ---------------------------------------------------------------------------
# ler_funcao: extrai código-fonte de uma função/classe via AST
# ---------------------------------------------------------------------------


def ler_funcao(file_path: str, line: int, base_dir: Path, max_lines: int = 80) -> str | None:
    """Extrai o código-fonte de uma função ou classe a partir de arquivo:linha.

    Args:
        file_path: Caminho relativo ao base_dir (ex: "centralservicos/views.py")
        line: Número da linha onde a função/classe começa
        base_dir: Diretório raiz do projeto
        max_lines: Máximo de linhas a retornar (evita enviar funções enormes ao LLM)

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
        # Fallback: retornar linhas brutas a partir da linha indicada
        lines = source.splitlines()
        start = max(0, line - 1)
        end = min(len(lines), start + max_lines)
        return '\n'.join(lines[start:end])

    # Encontrar o nó AST que começa na linha indicada
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.lineno == line:
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


# ---------------------------------------------------------------------------
# extrair_chamadas: lista calls de uma view/função
# ---------------------------------------------------------------------------


def extrair_chamadas(symbol: str, structure: dict) -> list[str]:
    """Retorna as chamadas (calls) de uma view/função a partir do mapa.

    Args:
        symbol: Nome qualificado (ex: "centralservicos.views.visualizar_chamado")
        structure: Conteúdo de structure.json

    Returns:
        Lista de chamadas (ex: ["Chamado.objects.filter", "ComunicacaoFormFactory"])
    """
    loc = localizar_arquivo(symbol, structure)
    if not loc:
        return []

    app_data = structure.get('apps', {}).get(loc['app'], {})
    comp = app_data.get(loc['kind'], {}).get(loc['name'], {})
    return comp.get('calls', [])


# ---------------------------------------------------------------------------
# seguir_referencia: navega grafo para encontrar definição
# ---------------------------------------------------------------------------


def seguir_referencia(call_name: str, from_app: str, structure: dict, graph: dict) -> dict | None:
    """Navega o grafo para encontrar a definição de um símbolo chamado.

    Args:
        call_name: Nome da chamada (ex: "chamado.get_permissoes", "ComunicacaoFormFactory")
        from_app: App de origem (para priorizar resolução local)
        structure: Conteúdo de structure.json
        graph: Conteúdo de graph.json

    Returns:
        dict com app, kind, name, file, line ou None.
    """
    apps = structure.get('apps', {})
    # Extrair o nome relevante
    parts = call_name.split('.')
    head = parts[0]
    tail = parts[-1] if len(parts) > 1 else None

    # 1. Tentar resolver como method_call no grafo
    if tail:
        for edge in graph.get('edges', []):
            if edge['type'] == 'method_call' and edge['to'].endswith(f'.{tail}'):
                # Ex: centralservicos.models.Chamado.get_permissoes
                target_parts = edge['to'].split('.')
                if len(target_parts) >= 4:
                    t_app = target_parts[0]
                    t_model = target_parts[2]
                    model_data = apps.get(t_app, {}).get('models', {}).get(t_model, {})
                    if model_data:
                        return {
                            'app': t_app,
                            'kind': 'models',
                            'name': t_model,
                            'method': tail,
                            'file': model_data.get('file', ''),
                            'line': model_data.get('line', 0),
                        }

    # 2. Tentar resolver como model (intra-app, depois global)
    search_name = head if head[0].isupper() else (tail or head)
    for kind in ('models', 'forms', 'views'):
        # Intra-app primeiro
        comp = apps.get(from_app, {}).get(kind, {}).get(search_name)
        if comp:
            return {
                'app': from_app,
                'kind': kind,
                'name': search_name,
                'file': comp.get('file', ''),
                'line': comp.get('line', 0),
            }
        # Global
        for app_name, app_data in apps.items():
            comp = app_data.get(kind, {}).get(search_name)
            if comp:
                return {
                    'app': app_name,
                    'kind': kind,
                    'name': search_name,
                    'file': comp.get('file', ''),
                    'line': comp.get('line', 0),
                }

    return None


# ---------------------------------------------------------------------------
# listar_imports: extrai imports de um módulo via AST
# ---------------------------------------------------------------------------


def listar_imports(file_path: str, base_dir: Path) -> list[dict]:
    """Extrai todos os imports de um arquivo Python.

    Args:
        file_path: Caminho relativo ao base_dir
        base_dir: Diretório raiz do projeto

    Returns:
        Lista de dicts com module, names, line.
    """
    full_path = base_dir / file_path
    if not full_path.exists():
        return []

    try:
        source = full_path.read_text(encoding='utf-8', errors='replace')
        tree = ast.parse(source, filename=str(full_path))
    except SyntaxError:
        return []

    imports = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append({
                    'module': alias.name,
                    'names': [alias.asname or alias.name],
                    'line': node.lineno,
                })
        elif isinstance(node, ast.ImportFrom):
            names = [a.asname or a.name for a in node.names]
            imports.append({
                'module': node.module or '',
                'names': names,
                'line': node.lineno,
            })
    return imports


# ---------------------------------------------------------------------------
# buscar_simbolo: grep no repositório (fallback)
# ---------------------------------------------------------------------------


def buscar_simbolo(pattern: str, base_dir: Path, max_results: int = 10) -> list[dict]:
    """Busca um símbolo no repositório via grep (fallback quando o mapa não basta).

    Args:
        pattern: Regex ou nome literal a buscar
        base_dir: Diretório raiz do projeto
        max_results: Máximo de resultados

    Returns:
        Lista de dicts com file, line, text.
    """
    import subprocess

    try:
        result = subprocess.run(
            ['grep', '-rn', '--include=*.py', '-E', pattern, str(base_dir)],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []

    results = []
    for line in result.stdout.splitlines()[:max_results]:
        parts = line.split(':', 2)
        if len(parts) >= 3:
            file_path = parts[0]
            try:
                rel_path = str(Path(file_path).relative_to(base_dir))
            except ValueError:
                rel_path = file_path
            # Ignorar migrations e __pycache__
            if 'migration' in rel_path or '__pycache__' in rel_path:
                continue
            results.append({
                'file': rel_path,
                'line': int(parts[1]) if parts[1].isdigit() else 0,
                'text': parts[2].strip(),
            })
    return results
