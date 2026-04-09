"""Testes determinísticos — replay de respostas LLM sem Ollama.

Princípio 4 — Testes Determinísticos: cassettes com respostas pré-gravadas.
"""

import json
from pathlib import Path

from iac.agent.prompts import (
    extract_tipo_from_analysis,
    parse_investigation_requests,
)

CASSETTES_DIR = Path(__file__).parent.parent / 'fixtures' / 'cassettes'


def _load_cassette(name: str) -> dict:
    with open(CASSETTES_DIR / name) as f:
        return json.load(f)


def test_replay_investigation_parse():
    """Replay: parsear pedidos de investigação da resposta gravada."""
    cassette = _load_cassette('16118_investigation.json')
    requests = parse_investigation_requests(cassette['response'])
    assert len(requests) >= 2
    # Deve pedir DiscenteAptosAvaliacao e Avaliacao
    model_names = [r.get('model', '') for r in requests]
    assert 'DiscenteAptosAvaliacao' in model_names
    assert 'Avaliacao' in model_names


def test_replay_analysis_classification():
    """Replay: extrair tipo da análise gravada."""
    cassette = _load_cassette('16118_analysis.json')
    tipo = extract_tipo_from_analysis(cassette['response'])
    assert tipo == 'tipo::prazo-expirado'


def test_replay_analysis_has_evidence():
    """Replay: análise menciona TEMPO_AVALIACAO."""
    cassette = _load_cassette('16118_analysis.json')
    assert 'TEMPO_AVALIACAO' in cassette['response']


def test_replay_analysis_has_encontrado():
    """Replay: análise usa marcação [ENCONTRADO]."""
    cassette = _load_cassette('16118_analysis.json')
    assert '[ENCONTRADO]' in cassette['response']
