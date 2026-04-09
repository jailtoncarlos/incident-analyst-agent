"""Pacote iac.agent.prompts — prompts encadeados para análise de incidentes.

Módulos:
    analysis — prompt de análise + classificação (single-prompt)
    multi — prompts iterativos (investigação + evidência)
    response — prompt de resposta ao usuário
    utils — extração de tipo e compactação de código
"""

# Re-exports para retrocompatibilidade (from iac.agent.prompts import ...)
from iac.agent.prompts.analysis import build_analysis_prompt  # noqa: F401
from iac.agent.prompts.multi import (  # noqa: F401
    build_evidence_prompt,
    build_investigation_prompt,
    parse_investigation_requests,
    resolve_investigation_requests,
)
from iac.agent.prompts.response import build_response_prompt  # noqa: F401
from iac.agent.prompts.utils import (  # noqa: F401
    _strip_context_header,
    compact_code,
    extract_classificacao,
    extract_tipo_from_analysis,
    normalize_to_known,
)
