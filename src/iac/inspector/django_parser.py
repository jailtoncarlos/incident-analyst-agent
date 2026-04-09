"""Parsing AST de módulos Python em projetos Django.

Extrai funções, classes, campos de model, referências FK,
chamadas de função, renders de template e metadados de CBVs
— tudo via ast.parse, sem executar código.
"""

from __future__ import annotations

import ast
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


def _parse_module(app_dir: Path, module_name: str) -> dict[str, dict]:
    """Parseia um módulo (views, models ou forms) extraindo funções e classes."""
    result: dict[str, dict] = {}

    # Arquivo único: app/views.py
    single_file = app_dir / f'{module_name}.py'
    if single_file.exists():
        result.update(_parse_python_file(single_file, app_dir))

    # Pacote: app/views/__init__.py + submodules
    package_dir = app_dir / module_name
    if package_dir.is_dir():
        for py_file in sorted(package_dir.glob('*.py')):
            if py_file.name == '__init__.py':
                continue
            result.update(_parse_python_file(py_file, app_dir))

    return result


def _fix_legacy_syntax(source: str) -> str:
    """Corrige sintaxes Python 2 que impedem o ast.parse no Python 3.

    Transformações:
        except TypeError, ValueError:             →  except (TypeError, ValueError):
        except A, B, C.DoesNotExist:              →  except (A, B, C.DoesNotExist):
        except A.DoesNotExist, KeyError:          →  except (A.DoesNotExist, KeyError):
    """

    def _fix_except(match: re.Match) -> str:
        """Converte cláusula except Python 2 para tupla Python 3."""
        types_str = match.group(1)
        # Separar por vírgula, preservando nomes qualificados (A.B)
        types = [t.strip() for t in types_str.split(',')]
        return f'except ({", ".join(types)}):'

    return re.sub(
        r'except\s+([\w.]+(?:\s*,\s*[\w.]+)+)\s*:',
        _fix_except,
        source,
    )


def _parse_python_file(file_path: Path, app_dir: Path) -> dict[str, dict]:
    """Parseia um arquivo Python extraindo funções e classes de topo."""
    result: dict[str, dict] = {}
    relative = str(file_path.relative_to(app_dir.parent))

    try:
        source = file_path.read_text(encoding='utf-8', errors='replace')
        try:
            tree = ast.parse(source, filename=str(file_path))
        except SyntaxError:
            source = _fix_legacy_syntax(source)
            tree = ast.parse(source, filename=str(file_path))
    except SyntaxError:
        logger.debug(f'SyntaxError ao parsear {file_path}, pulando.')
        return result

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            entry = {
                'file': relative,
                'line': node.lineno,
                'type': 'function',
            }
            # Extrair chamadas dentro da função
            calls = _extract_calls(node)
            if calls:
                entry['calls'] = calls
            # Extrair renders (template)
            renders = _extract_renders(node)
            if renders:
                entry['renders'] = renders
            result[node.name] = entry

        elif isinstance(node, ast.ClassDef):
            entry = {
                'file': relative,
                'line': node.lineno,
                'type': 'class',
            }
            # Extrair campos (para models)
            fields = _extract_model_fields(node)
            if fields:
                entry['fields'] = fields
            # Extrair métodos
            methods = _extract_methods(node)
            if methods:
                entry['methods'] = methods
            # Extrair referências FK/M2M (para models)
            fk_refs = _extract_fk_references(node)
            if fk_refs:
                entry['fk_references'] = fk_refs
            # Extrair constantes de classe (UPPER_CASE = valor)
            constants = _extract_class_constants(node)
            if constants:
                entry['constants'] = constants
            # Extrair Meta.model (para forms)
            meta_model = _extract_meta_model(node)
            if meta_model:
                entry['meta_model'] = meta_model
            # Nível 1: Extrair template_name de class-based views
            class_template = _extract_class_template_name(node)
            if class_template:
                entry['renders'] = [class_template]
            result[node.name] = entry

    return result


def _extract_calls(node: ast.AST) -> list[str]:
    """Extrai nomes de chamadas de função/método dentro de um nó."""
    calls: list[str] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            name = _call_name(child)
            if name and name not in calls:
                calls.append(name)
    return calls[:20]  # limitar a 20 chamadas mais relevantes


def _call_name(node: ast.Call) -> str | None:
    """Extrai o nome de uma chamada."""
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        # ex: chamado.resolver_chamado() → chamado.resolver_chamado
        parts = []
        current = node.func
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
        parts.reverse()
        return '.'.join(parts)
    return None


def _extract_renders(node: ast.AST) -> list[str]:
    """Extrai nomes de templates passados a render, render_to_string, etc."""
    templates: list[str] = []
    render_funcs = ('render', 'render_to_string', 'TemplateResponse', 'get_template', 'select_template')

    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        name = _call_name(child)
        if not name:
            continue

        # Funções de render: render(request, 'template.html', ...)
        if name in render_funcs:
            for arg in child.args:
                _collect_template_string(arg, templates)
            for kw in child.keywords:
                if kw.arg in ('template_name', 'template'):
                    _collect_template_string(kw.value, templates)

        # Variáveis de template: template_name = 'template.html' ou self.template_name = '...'
        if isinstance(child, ast.Call) and name == 'render':
            continue  # já tratado acima

    # Também buscar atribuições do tipo template = '...' ou template_name = '...'
    for child in ast.walk(node):
        if isinstance(child, ast.Assign):
            for target in child.targets:
                target_name = None
                if isinstance(target, ast.Name):
                    target_name = target.id
                elif isinstance(target, ast.Attribute):
                    target_name = target.attr
                if target_name and 'template' in target_name.lower():
                    _collect_template_string(child.value, templates)

    return templates


def _collect_template_string(node: ast.AST, templates: list[str]) -> None:
    """Coleta string de template de um nó AST."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        value = node.value.strip()
        if ('/' in value or value.endswith('.html')) and value not in templates:
            templates.append(value)


def _extract_model_fields(node: ast.ClassDef) -> list[str]:
    """Extrai nomes de campos de um Model Django."""
    fields: list[str] = []
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.Assign):
            for target in child.targets:
                if isinstance(target, ast.Name) and isinstance(child.value, ast.Call):
                    call_name = _call_name(child.value)
                    if call_name and ('Field' in call_name or 'ForeignKey' in call_name or 'ManyToMany' in call_name):
                        fields.append(target.id)
        elif isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name):
            fields.append(child.target.id)
    return fields


def _extract_fk_references(node: ast.ClassDef) -> list[str]:
    """Extrai models referenciados via ForeignKey, OneToOne e ManyToMany."""
    refs: list[str] = []
    fk_types = ('ForeignKey', 'ForeignKeyPlus', 'OneToOneField', 'OneToOneFieldPlus', 'ManyToManyField', 'ManyToManyFieldPlus')
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.Assign) and isinstance(child.value, ast.Call):
            call_name = _call_name(child.value)
            if call_name and any(fk in call_name for fk in fk_types) and child.value.args:
                    arg = child.value.args[0]
                    if isinstance(arg, ast.Name) and arg.id not in refs:
                        refs.append(arg.id)
                    elif isinstance(arg, ast.Constant) and isinstance(arg.value, str) and arg.value not in refs:
                        refs.append(arg.value)
    return refs


def _extract_class_constants(node: ast.ClassDef) -> dict[str, str]:
    """Extrai constantes de classe (atributos UPPER_CASE com valor literal)."""
    constants: dict[str, str] = {}
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.Assign):
            for target in child.targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    # Só capturar valores literais simples
                    if isinstance(child.value, ast.Constant):
                        constants[target.id] = str(child.value.value)
                    elif isinstance(child.value, ast.Tuple | ast.List):
                        # Tuplas/listas de constantes — representar como resumo
                        constants[target.id] = f'({len(child.value.elts)} items)'
    return constants


def _extract_methods(node: ast.ClassDef) -> dict[str, dict]:
    """Extrai métodos de uma classe com número da linha."""
    methods: dict[str, dict] = {}
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef) and (
            not child.name.startswith('_') or child.name in ('__str__', '__repr__')
        ):
            methods[child.name] = {'line': child.lineno}
    return methods


def _extract_meta_model(node: ast.ClassDef) -> str | None:
    """Extrai o model referenciado em Meta.model de um Form."""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.ClassDef) and child.name == 'Meta':
            for meta_child in ast.iter_child_nodes(child):
                if isinstance(meta_child, ast.Assign):
                    for target in meta_child.targets:
                        if (
                            isinstance(target, ast.Name)
                            and target.id == 'model'
                            and isinstance(meta_child.value, ast.Name)
                        ):
                            return meta_child.value.id
    return None


def _extract_class_template_name(node: ast.ClassDef) -> str | None:
    """Extrai template_name de atributo de classe (CBV Django)."""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.Assign):
            for target in child.targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id == 'template_name'
                    and isinstance(child.value, ast.Constant)
                    and isinstance(child.value.value, str)
                ):
                    return child.value.value
    return None
