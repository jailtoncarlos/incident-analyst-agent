"""Ferramentas de inspeção de código para o agente — fachada pública.

Consultam .iac/structure.json e .iac/graph.json para navegar
o código sem grep, permitindo que modelos pequenos (7B) operem
com eficiência em repositórios grandes.

Todas as funções recebem structure/graph como dicts já carregados
e o base_dir do projeto. Não fazem I/O nos JSONs — isso é
responsabilidade do orquestrador.

Os detalhes de implementação estão em:
  - tools_navigation.py   → resolver_rota, localizar_arquivo, ler_funcao
  - tools_inspection.py   → extrair_chamadas, seguir_referencia, listar_imports, buscar_simbolo
"""

from __future__ import annotations

from .tools_inspection import buscar_simbolo, extrair_chamadas, listar_imports, seguir_referencia
from .tools_navigation import _match_score, ler_funcao, localizar_arquivo, resolver_rota

__all__ = [
    'resolver_rota',
    'localizar_arquivo',
    'ler_funcao',
    '_match_score',
    'extrair_chamadas',
    'seguir_referencia',
    'listar_imports',
    'buscar_simbolo',
]
