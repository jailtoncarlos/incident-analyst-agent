"""Ferramentas de inspeção e extração de informações de código para o agente.

Funções para extrair chamadas de funções, seguir referências no grafo
de dependências, listar imports de módulos e buscar símbolos no
repositório via grep — complementando as ferramentas de navegação.

Todas as funções recebem structure/graph como dicts já carregados
e o base_dir do projeto. Não fazem I/O nos JSONs — isso é
responsabilidade do orquestrador.
"""

from __future__ import annotations

import ast
import logging
from pathlib import Path

from .tools_navigation import localizar_arquivo

logger = logging.getLogger(__name__)


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

    # 1. Tentar resolver como method_call no grafo (prioriza from_app)
    if tail:
        candidates = []
        for edge in graph.get('edges', []):
            if edge['type'] == 'method_call' and edge['to'].endswith(f'.{tail}'):
                target_parts = edge['to'].split('.')
                if len(target_parts) >= 4:
                    t_app = target_parts[0]
                    t_model = target_parts[2]
                    model_data = apps.get(t_app, {}).get('models', {}).get(t_model, {})
                    if model_data:
                        method_info = model_data.get('methods', {}).get(tail, {})
                        candidates.append((t_app, t_model, model_data, method_info))
        # Priorizar: mesmo app primeiro
        candidates.sort(key=lambda c: (0 if c[0] == from_app else 1))
        if candidates:
            t_app, t_model, model_data, method_info = candidates[0]
            return {
                'app': t_app,
                'kind': 'models',
                'name': t_model,
                'method': tail,
                'file': model_data.get('file', ''),
                'line': model_data.get('line', 0),
                'method_line': method_info.get('line'),
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
        result = subprocess.run(  # noqa: S603
            ['grep', '-rn', '--include=*.py', '-E', pattern, str(base_dir)],  # noqa: S607
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
