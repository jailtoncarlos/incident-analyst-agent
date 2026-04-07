"""
Entry point do CLI iac.

Uso:
    iac init                    # Inspeciona o repositório atual
    iac init --stats            # Mostra estatísticas da inspeção
    iac init --force            # Re-inspeciona do zero
    iac analyze --issue-url URL # Analisa um incidente
    iac analyze --description D # Analisa por descrição
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import click

from iac import __version__
from iac.config.settings import IAC_DIR, load_config

logger = logging.getLogger(__name__)


@click.group()
@click.version_option(version=__version__, prog_name='iac')
@click.option('--verbose', '-v', is_flag=True, help='Ativar logs detalhados.')
def main(verbose: bool):
    """Incident Analyst Agent — análise técnica de incidentes de software."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s %(levelname)s %(name)s: %(message)s',
        datefmt='%H:%M:%S',
    )


@main.command()
@click.option('--base-dir', type=click.Path(exists=True), default='.', help='Diretório raiz do projeto.')
@click.option('--force', is_flag=True, help='Re-inspecionar do zero.')
@click.option('--stats', is_flag=True, help='Mostrar estatísticas da inspeção existente.')
def init(base_dir: str, force: bool, stats: bool):
    """Inspeciona o repositório e gera mapa estrutural."""
    from iac.inspector import inspect_project

    base = Path(base_dir).resolve()
    iac_dir = base / IAC_DIR

    if stats:
        if not iac_dir.exists():
            click.echo('Nenhuma inspeção encontrada. Execute `iac init` primeiro.')
            sys.exit(1)
        from iac.inspector import show_stats

        show_stats(iac_dir)
        return

    if iac_dir.exists() and not force:
        click.echo(f'Inspeção já existe em {iac_dir}. Use --force para re-inspecionar.')
        sys.exit(1)

    click.echo(f'Inspecionando {base}...')
    result = inspect_project(base, force=force)
    click.echo(f'Inspeção concluída: {result["summary"]}')


@main.command()
@click.option('--issue-url', type=str, default=None, help='URL da issue no GitLab/GitHub.')
@click.option('--description', type=str, default=None, help='Descrição do incidente.')
@click.option('--base-dir', type=click.Path(exists=True), default='.', help='Diretório raiz do projeto.')
@click.option('--dry-run', is_flag=True, help='Não posta comentários nem aplica labels.')
@click.option('--simulate', is_flag=True, help='Executar simulação em ambiente controlado.')
@click.option('--llm', type=click.Choice(['ollama', 'gemini']), default=None, help='Backend LLM.')
@click.option('--model', type=str, default=None, help='Modelo do LLM.')
def analyze(issue_url: str, description: str, base_dir: str, dry_run: bool, simulate: bool, llm: str, model: str):
    """Analisa um incidente reportado."""
    if not issue_url and not description:
        click.echo('Informe --issue-url ou --description.')
        sys.exit(1)

    base = Path(base_dir).resolve()
    iac_dir = base / IAC_DIR

    if not iac_dir.exists():
        click.echo('Nenhuma inspeção encontrada. Execute `iac init` primeiro.')
        sys.exit(1)

    load_config(iac_dir)
    click.echo('Analisando incidente...')
    # TODO: implementar fluxo de análise
    click.echo('Análise ainda não implementada. Veja issue #1.')


if __name__ == '__main__':
    main()
