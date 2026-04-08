"""Rastreamento e logging por camada de execução.

Gera logs estruturados em .iac/logs/ para cada execução do analyze_issue.
Cada execução cria um diretório timestamped com arquivos por etapa:

    .iac/logs/
    └── 2026-04-08T17-30-00_16118/
        ├── 00_metadata.json
        ├── 01_classifier.json
        ├── 02_orchestrator.json
        ├── 03_structural.json
        ├── 04_deep.json
        ├── 05_prompt_investigation.txt
        ├── 06_llm_response_investigation.txt
        ├── 07_evidence_requests.json
        ├── 08_evidence_resolved.txt
        ├── 09_prompt_analysis.txt
        ├── 10_llm_response_analysis.txt
        ├── 11_prompt_response.txt
        └── 12_llm_response_response.txt
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class Tracer:
    """Rastreador de execução por camada.

    Uso:
        tracer = Tracer(iac_dir, issue_id='16118')
        tracer.log_step('classifier', data)
        tracer.log_prompt('investigation', prompt_text)
        tracer.log_llm_response('investigation', response_text)
    """

    def __init__(self, iac_dir: Path, issue_id: str | None = None, enabled: bool = True):
        self.enabled = enabled
        if not enabled:
            return

        timestamp = datetime.now().strftime('%Y-%m-%dT%H-%M-%S')
        suffix = f'_{issue_id}' if issue_id else ''
        self.log_dir = iac_dir / 'logs' / f'{timestamp}{suffix}'
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._step_counter = 0

        logger.info(f'Tracer: logs em {self.log_dir}')

    def _next_step(self, name: str) -> str:
        """Retorna o prefixo numerado para o próximo passo."""
        self._step_counter += 1
        return f'{self._step_counter:02d}_{name}'

    def log_step(self, name: str, data: dict) -> None:
        """Registra uma etapa como JSON."""
        if not self.enabled:
            return
        filename = self._next_step(name) + '.json'
        filepath = self.log_dir / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        logger.info(f'Tracer: {filename} ({len(json.dumps(data, default=str))} chars)')

    def log_text(self, name: str, text: str, ext: str = 'txt') -> None:
        """Registra texto (prompt ou resposta)."""
        if not self.enabled:
            return
        filename = self._next_step(name) + f'.{ext}'
        filepath = self.log_dir / filename
        filepath.write_text(text, encoding='utf-8')
        logger.info(f'Tracer: {filename} ({len(text)} chars)')

    def log_prompt(self, name: str, prompt: str) -> None:
        """Registra um prompt enviado ao LLM."""
        self.log_text(f'prompt_{name}', prompt, ext='md')

    def log_llm_response(self, name: str, response: str) -> None:
        """Registra uma resposta do LLM."""
        self.log_text(f'llm_response_{name}', response or '(sem resposta)', ext='md')

    def log_metadata(self, **kwargs) -> None:
        """Registra metadados da execução (primeiro passo)."""
        if not self.enabled:
            return
        data = {
            'timestamp': datetime.now().isoformat(),
            'log_dir': str(self.log_dir),
            **kwargs,
        }
        # Metadata usa step 0
        filepath = self.log_dir / '00_metadata.json'
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)


class NullTracer:
    """Tracer que não faz nada — usado quando logging está desabilitado."""

    def log_step(self, name, data):
        pass

    def log_text(self, name, text, ext='txt'):
        pass

    def log_prompt(self, name, prompt):
        pass

    def log_llm_response(self, name, response):
        pass

    def log_metadata(self, **kwargs):
        pass
