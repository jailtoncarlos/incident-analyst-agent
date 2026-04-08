"""Casos de teste reais — issues resolvidas do GitLab SUAP.

Cada caso contém a descrição da issue como entrada e o resultado esperado
(app, tipo, view) como saída para validação do orchestrator.

Estes testes requerem o .iac/ do SUAP gerado via `iac init`.
Marcados com @pytest.mark.real para execução separada.

Uso:
    pytest tests/test_agent/test_real_cases.py -v -m real
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# Diretório do SUAP — ajustar se necessário
SUAP_DIR = Path('/home/jailton/workspace/ifrn/suap')
IAC_DIR = SUAP_DIR / '.iac'

# Pular se .iac/ não existir (CI sem inspeção)
pytestmark = pytest.mark.real
skip_no_iac = pytest.mark.skipif(
    not (IAC_DIR / 'structure.json').exists(),
    reason='Requer .iac/ do SUAP (rode iac init primeiro)',
)


@pytest.fixture(scope='module')
def suap_context():
    """Carrega structure.json e graph.json do SUAP."""
    with open(IAC_DIR / 'structure.json') as f:
        structure = json.load(f)
    with open(IAC_DIR / 'graph.json') as f:
        graph = json.load(f)
    return structure, graph, SUAP_DIR


# ---------------------------------------------------------------------------
# Casos de teste reais — issues resolvidas via resposta ao usuário
# ---------------------------------------------------------------------------

# Formato: (issue_id, app_esperado, tipo_esperado, url_ou_view, descricao_resumida)
CASES_NAO_BUG = [
    {
        'issue': 16190,
        'app': 'comum',
        'tipo': 'dados-cadastrais',
        'descricao': 'Matrícula OK no SUAP, sincronização Moodle pendente',
    },
    {
        'issue': 16177,
        'app': 'centralservicos',
        'tipo': 'configuracao',
        'descricao': 'Exigência de patrimônio é config do chamado',
    },
    {
        'issue': 16175,
        'app': 'centralservicos',
        'tipo': 'configuracao',
        'descricao': 'Resolvido via resposta ao usuário',
    },
    {
        'issue': 16174,
        'app': 'enquete',
        'tipo': 'nao-e-erro',
        'descricao': 'Vínculo de servidor sem setor sincronizado',
    },
    {
        'issue': 16172,
        'app': 'edu',
        'tipo': 'dados-cadastrais',
        'descricao': 'Solicitação administrativa — e-mail de exclusão de conta para aluno em intercâmbio',
    },
    {
        'issue': 16166,
        'app': 'eventos',
        'tipo': 'dados-cadastrais',
        'descricao': 'Resolvido via resposta ao usuário',
    },
    {
        'issue': 16134,
        'app': 'eventos',
        'tipo': 'configuracao',
        'descricao': 'Modelo de certificado sem config para tipo Ouvinte',
    },
    {
        'issue': 16130,
        'app': 'comum',
        'tipo': 'dados-cadastrais',
        'descricao': 'Nome incorreto em documentos — dado cadastral errado na PessoaFisica',
    },
    {
        'issue': 16125,
        'app': 'comum',
        'tipo': 'dados-cadastrais',
        'descricao': 'Widget Jornada Estudante com dados inconsistentes — registro cadastral do aluno',
    },
    {
        'issue': 16124,
        'app': 'processo_seletivo',
        'tipo': 'prazo-expirado',
        'descricao': 'Botão AÇÕES oculto porque data_limite_avaliacao expirou',
    },
    {
        'issue': 16122,
        'app': 'centralservicos',
        'tipo': 'configuracao',
        'descricao': 'Resolvido via resposta ao usuário',
    },
    {
        'issue': 16119,
        'app': 'centralservicos',
        'tipo': 'configuracao',
        'descricao': 'Perfil sem permissão para grupo de atendimento',
    },
    {
        'issue': 16118,
        'app': 'progressao_docente',
        'tipo': 'prazo-expirado',
        'descricao': 'Prazo de avaliação discente expirado (10 dias)',
        'refs': {
            'correcoes': [16174, 16176],
            'sentry': [16203, 16138, 16183, 16198],
        },
    },
]
