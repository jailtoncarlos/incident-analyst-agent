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
import os
import sys
from pathlib import Path

import click

from iac import __version__
from iac.config.settings import IAC_DIR

logger = logging.getLogger(__name__)


logger = logging.getLogger('iac.cli')


@click.group()
@click.version_option(version=__version__, prog_name='iac')
@click.option('--verbose', '-v', is_flag=True, help='Ativar logs detalhados (DEBUG) no terminal.')
def main(verbose: bool):
    """Incident Analyst Agent — análise técnica de incidentes de software."""
    # Terminal: INFO por default, DEBUG com -v
    console_level = logging.DEBUG if verbose else logging.INFO
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s', datefmt='%H:%M:%S'))

    # Root logger em DEBUG (o FileHandler no analyze vai receber tudo)
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(console_handler)

    # Silenciar libs verbosas no log
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('gitlab').setLevel(logging.WARNING)


def _generate_default_artifacts(iac_dir: Path, result: dict) -> None:
    """Gera artefatos de configuração padrão se não existem."""
    framework = result.get('framework', 'Python')

    # .env
    env_file = iac_dir / '.env'
    if not env_file.exists():
        env_file.write_text(
            '# IAC — Variáveis de ambiente\n'
            '# Preencha e descomente conforme necessário\n'
            '# Ref: .env.example no repositório do IAC\n\n'
            '# GITLAB_TOKEN=\n'
            '# IAC_LLM_BACKEND=groq\n'
            '# IAC_LLM_MODEL=llama-3.3-70b-versatile\n'
            '# GROQ_API_KEY=\n'
            '# IAC_ANALYZE_MODE=multi\n'
            '# IAC_LLM_RATE_DELAY=30\n',
            encoding='utf-8',
        )
        click.echo('  → .iac/.env (template de configuração)')

    # profile.yaml
    profile_file = iac_dir / 'profile.yaml'
    if not profile_file.exists():
        import yaml

        profile = {
            'name': iac_dir.parent.name,
            'system_description': f'{framework}',
            'rules': [],
        }
        with open(profile_file, 'w', encoding='utf-8') as f:
            yaml.dump(profile, f, default_flow_style=False, allow_unicode=True)
        click.echo(f'  → .iac/profile.yaml (perfil do projeto: {framework})')

    # logs/
    log_dir = iac_dir / 'logs'
    log_dir.mkdir(exist_ok=True)

    # diagrams/
    diagrams_dir = iac_dir / 'diagrams'
    if not diagrams_dir.exists():
        try:
            from iac.diagram.generator import generate_diagrams

            generate_diagrams(iac_dir)
            click.echo('  → .iac/diagrams/ (visualizações interativas)')
        except Exception as e:
            logging.getLogger(__name__).debug(f'Diagramas não gerados: {e}')


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

    # Gerar artefatos de configuração se não existem
    _generate_default_artifacts(iac_dir, result)


@main.command()
@click.option('--issue-url', type=str, default=None, help='URL da issue no GitLab.')
@click.option('--title', type=str, default=None, help='Título do incidente.')
@click.option('--description', type=str, default=None, help='Descrição do incidente.')
@click.option('--base-dir', type=click.Path(exists=True), default='.', help='Diretório raiz do projeto.')
@click.option('--llm', type=click.Choice(['ollama', 'groq', 'deepseek', 'gemini']), envvar='IAC_LLM_BACKEND', default=None, help='Backend LLM (env: IAC_LLM_BACKEND).')
@click.option('--llm-url', type=str, envvar='IAC_LLM_URL', default=None, help='Endpoint do LLM (env: IAC_LLM_URL).')
@click.option('--llm-key', type=str, default=None, help='API key do LLM (env: GROQ_API_KEY, GEMINI_API_KEY).')
@click.option('--llm-model', type=str, envvar='IAC_LLM_MODEL', default=None, help='Modelo do LLM (env: IAC_LLM_MODEL).')
@click.option('--gitlab-token', type=str, envvar='GITLAB_TOKEN', default=None, help='Token GitLab (env: GITLAB_TOKEN).')
@click.option('--mode', type=click.Choice(['auto', 'single', 'multi', 'loop']), envvar='IAC_ANALYZE_MODE', default=None, help='Modo (env: IAC_ANALYZE_MODE).')
@click.option('--env-file', type=click.Path(), default=None, help='Caminho para .env (default: .iac/.env).')
@click.option('--dry-run', is_flag=True, help='Não posta comentários nem aplica labels.')
@click.option('--post', is_flag=True, help='Postar análise como comentário na issue.')
def analyze(
    issue_url: str,
    title: str,
    description: str,
    base_dir: str,
    llm: str,
    llm_url: str,
    llm_key: str,
    llm_model: str,
    gitlab_token: str,
    mode: str,
    env_file: str,
    dry_run: bool,
    post: bool,
):
    """Analisa um incidente reportado."""
    if not issue_url and not title and not description:
        click.echo('Informe --issue-url, --title ou --description.')
        sys.exit(1)

    base = Path(base_dir).resolve()
    iac_dir = base / IAC_DIR

    if not iac_dir.exists():
        click.echo('Nenhuma inspeção encontrada. Execute `iac init` primeiro.')
        sys.exit(1)

    # FileHandler em .iac/logs/ — cada execução em arquivo separado
    from datetime import datetime

    from iac.config.settings import get_effective_config, load_graph, load_profile, load_structure
    log_dir = iac_dir / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    log_filename = f'iac_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
    file_handler = logging.FileHandler(log_dir / log_filename, encoding='utf-8')
    file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s', datefmt='%H:%M:%S'))
    file_handler.setLevel(logging.DEBUG)
    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)
    # Root logger precisa estar em DEBUG para o FileHandler receber tudo
    root_logger.setLevel(logging.DEBUG)
    from iac.agent.orchestrator import analyze_issue, format_structural_analysis
    from iac.agent.prompts import extract_classificacao

    # Configuração efetiva: .env + CLI args
    cfg = get_effective_config(iac_dir, {
        'llm': llm, 'llm_model': llm_model, 'llm_url': llm_url, 'llm_key': llm_key,
        'gitlab_token': gitlab_token, 'mode': mode,
    })

    profile = load_profile(iac_dir)

    # Resolução: CLI args (já com envvar via click) → .env → defaults
    llm = llm or cfg['llm'].get('backend')
    llm_model = llm_model or cfg['llm'].get('model') or 'qwen2.5:7b'
    llm_url = llm_url or cfg['llm'].get('url')
    llm_key = llm_key or cfg['llm'].get('key') or os.environ.get('GROQ_API_KEY') or os.environ.get('DEEPSEEK_API_KEY') or os.environ.get('GEMINI_API_KEY')
    gitlab_token = gitlab_token or cfg['gitlab'].get('token') or os.environ.get('GITLAB_TOKEN')
    mode = mode or cfg['analyze'].get('mode') or 'auto'

    structure = load_structure(iac_dir)
    graph = load_graph(iac_dir)

    # 1. Obter título e descrição
    issue_id = None
    gitlab_client = None

    if issue_url:
        from iac.integrations.gitlab import GitLabClient, parse_issue_url

        parsed = parse_issue_url(issue_url)
        if not parsed:
            click.echo(f'URL não reconhecida: {issue_url}')
            sys.exit(1)

        gitlab_url_parsed, project_path, issue_id = parsed
        token = gitlab_token
        if not token:
            click.echo('Token GitLab necessário. Use --gitlab-token, GITLAB_TOKEN ou .iac/.env.')
            sys.exit(1)

        click.echo(f'Buscando issue {issue_id} no GitLab...')
        try:
            gitlab_client = GitLabClient(gitlab_url_parsed, token, project_path=project_path)
        except Exception:
            click.echo(f'Projeto {project_path} não encontrado.')
            sys.exit(1)
        issue_data = gitlab_client.get_issue(issue_id)
        title = issue_data['title']
        description = issue_data['description']
        click.echo(f'Issue: {title}')

    if not title:
        title = ''

    if not description:
        description = ''

    # Log dos argumentos de entrada
    # Validar API key para backends que exigem
    if llm in ('groq', 'deepseek', 'gemini') and not llm_key:
        env_vars = {'groq': 'GROQ_API_KEY', 'deepseek': 'DEEPSEEK_API_KEY', 'gemini': 'GEMINI_API_KEY'}
        click.echo(f'API key necessária para {llm}. Use --llm-key, {env_vars[llm]} ou .iac/.env.')
        sys.exit(1)

    # URL default por backend (se não informado)
    if llm == 'groq' and (not llm_url or 'localhost' in llm_url):
        llm_url = 'https://api.groq.com/openai/v1/chat/completions'
    elif llm == 'deepseek' and (not llm_url or 'localhost' in llm_url):
        llm_url = 'https://api.deepseek.com/v1/chat/completions'

    logger.info('=== iac analyze iniciado ===')
    logger.info(f'Base dir: {base}')
    logger.info(f'Issue URL: {issue_url or "(não informado)"}')
    logger.info(f'Título: {title or "(não informado)"}')
    logger.info(f'Descrição: {description or "(não informado)"}')
    logger.info(f'LLM: backend={llm or "(não informado)"}, modelo={llm_model}, url={llm_url or "(config)"}')
    logger.info(f'Modo: {mode}')
    if issue_id:
        logger.info(f'GitLab issue: {issue_id}')

    # 2. Análise completa
    click.echo(f'Analisando (modelo: {llm_model})...')
    result = analyze_issue(
        title=title,
        description=description,
        structure=structure,
        graph=graph,
        base_dir=base,
        model_name=llm_model,
    )

    # 3. Exibir análise estrutural
    structural_text = format_structural_analysis(result['structural'])
    click.echo('')
    click.echo(structural_text)

    # 4. Determinar modo e executar LLM
    from iac.agent.loop import run_loop
    from iac.agent.orchestrator import MODEL_PROFILES, get_model_profile
    from iac.agent.runner import run_auto, run_multi, run_response, run_single

    effective_mode = mode
    if mode == 'auto' and llm:
        profile = get_model_profile(llm_model)
        is_small = any(profile is v for k, v in MODEL_PROFILES.items() if k == 'small')
        # small (7B): multi estável. medium/large (14B+): auto (single → loop se incerto)
        effective_mode = 'multi' if is_small else 'auto'
        logger.info(f'[auto] Perfil {"small" if is_small else "medium/large"} → modo {effective_mode}')

    llm_analysis = None
    loop_result = None

    if llm and effective_mode == 'auto':
        click.echo(f'\n[Modo auto] Single como fast-path + loop se incerto ({llm} {llm_model})...')
        loop_result = run_auto(result, structure, graph, base, llm, llm_model, llm_url, llm_key, profile=profile)
        mode_used = loop_result.get('mode_used', '?')
        click.echo(f'[auto] Modo usado: {mode_used}')

    elif llm and effective_mode == 'loop':
        click.echo(f'\n[Modo loop] Análise interativa com {llm} ({llm_model})...')
        loop_result = run_loop(result, structure, graph, base, llm, llm_model, llm_url, llm_key, profile=profile)
        llm_analysis = loop_result.get('analysis')
        if loop_result.get('alteracoes'):
            click.echo(f'\n--- Alterações de código sugeridas ({len(loop_result["alteracoes"])}) ---\n')
            for alt in loop_result['alteracoes']:
                click.echo(alt)
                click.echo('')

    elif llm and effective_mode == 'multi':
        click.echo(f'\n[Modo multi-prompt] Enviando ao {llm} ({llm_model})...')
        llm_analysis = run_multi(result, structure, graph, base, llm, llm_model, llm_url, llm_key, profile=profile)

    elif llm:
        click.echo(f'\nEnviando prompt ao {llm} ({llm_model})...')
        llm_analysis = run_single(result, llm, llm_model, llm_url, llm_key, profile=profile)

    if llm_analysis:
        click.echo('\n--- Análise do LLM ---\n')
        click.echo(llm_analysis)

        classificacao = extract_classificacao(llm_analysis)
        tipo = loop_result.get('tipo') if loop_result else classificacao['classificacao']
        subtipo = classificacao.get('subclassificacao')

        if tipo:
            click.echo(f'\nClassificação: {tipo}')
            result['classification']['tipo_sugerido'] = tipo
            if tipo not in result['classification']['labels_sugeridos']:
                result['classification']['labels_sugeridos'].append(tipo)
        if subtipo:
            click.echo(f'Subclassificação: {subtipo}')
            result['classification']['subtipo_sugerido'] = subtipo
            if subtipo not in result['classification']['labels_sugeridos']:
                result['classification']['labels_sugeridos'].append(subtipo)

        logger.info(f'[Resultado] Classificação: tipo={tipo}, subtipo={subtipo}, labels={result["classification"].get("labels_sugeridos", [])}')

        if result['classification'].get('interessado') and tipo:
            click.echo('\nGerando relatório técnico...')
            response_text = run_response(result, llm_analysis, llm, llm_model, llm_url, llm_key, profile=profile)
            if response_text:
                click.echo('\n--- Relatório técnico ---\n')
                click.echo(response_text)
        elif not tipo:
            logger.warning('[LLM] Classificação inconclusiva — relatório técnico não gerado')
            click.echo('\nClassificação inconclusiva — relatório técnico não gerado.')
    elif llm:
        logger.warning('[LLM] Nenhuma resposta do LLM')
        click.echo('LLM não retornou resposta.')

    # 5. Labels sugeridos
    labels = result['classification'].get('labels_sugeridos', [])
    if labels:
        click.echo(f'\nLabels sugeridos: {", ".join(labels)}')

    # 6. Postar na issue (se --post e tem GitLab)
    if post and gitlab_client and issue_id and not dry_run:
        comment = structural_text
        if llm_analysis:
            comment += f'\n\n---\n\n## Análise do LLM\n\n{llm_analysis}'
        gitlab_client.add_comment(issue_id, comment)
        click.echo(f'\nComentário postado na issue {issue_id}.')

        if labels:
            gitlab_client.add_labels(issue_id, labels)
            click.echo(f'Labels aplicados: {", ".join(labels)}')
    elif post and not gitlab_client:
        click.echo('\n--post requer --issue-url com --gitlab-token.')

    click.echo('\nAnálise concluída.')


@main.command('config')
@click.option('--base-dir', type=click.Path(exists=True), default='.', help='Diretório raiz do projeto.')
@click.option('--set', 'set_values', multiple=True, help='Definir valor: seção.chave=valor (ex: llm.model=qwen2.5-coder:7b)')
@click.option('--show', is_flag=True, help='Exibir configuração atual.')
def config_cmd(base_dir: str, set_values: tuple, show: bool):
    """Gerencia configuração do projeto (.iac/.env)."""
    base = Path(base_dir).resolve()
    iac_dir = base / IAC_DIR

    if not iac_dir.exists():
        click.echo('Nenhuma inspeção encontrada. Execute `iac init` primeiro.')
        sys.exit(1)

    from iac.config.settings import get_effective_config

    env_file = iac_dir / '.env'

    if set_values:
        lines = env_file.read_text(encoding='utf-8').splitlines() if env_file.exists() else []
        for item in set_values:
            if '=' not in item:
                click.echo(f'Formato inválido: {item}. Use CHAVE=valor')
                continue
            key, value = item.split('=', 1)
            key = key.upper()
            # Atualizar ou adicionar
            updated = False
            for i, line in enumerate(lines):
                if line.startswith((f'{key}=', f'# {key}=')):
                    lines[i] = f'{key}={value}'
                    updated = True
                    break
            if not updated:
                lines.append(f'{key}={value}')
            click.echo(f'{key}={value}')
        env_file.write_text('\n'.join(lines) + '\n', encoding='utf-8')

    if show or not set_values:
        config = get_effective_config(iac_dir, {})
        for section, values in config.items():
            if isinstance(values, dict):
                for k, v in values.items():
                    if v is not None:
                        click.echo(f'{section}.{k} = {v}')


@main.command()
@click.option('--base-dir', type=click.Path(exists=True), default='.', help='Diretório raiz do projeto.')
@click.option('--overview', is_flag=True, help='Gerar overview (apps como nós).')
@click.option('--app', type=str, default=None, help='Gerar detalhe de um app específico.')
@click.option('--all-apps', 'all_apps', is_flag=True, help='Gerar diagramas de todos os apps.')
@click.option('--open', 'open_browser', is_flag=True, help='Abrir no browser após gerar.')
def diagram(base_dir: str, overview: bool, app: str, all_apps: bool, open_browser: bool):
    """Gera diagramas interativos do grafo e estrutura."""
    base = Path(base_dir).resolve()
    iac_dir = base / IAC_DIR

    if not iac_dir.exists():
        click.echo('Nenhuma inspeção encontrada. Execute `iac init` primeiro.')
        sys.exit(1)

    from iac.config.settings import load_structure
    from iac.diagram.generator import generate_app_detail_data, generate_overview_data, write_html

    diagrams_dir = iac_dir / 'diagrams'
    generated = []

    if overview or (not app and not all_apps):
        data = generate_overview_data(iac_dir)
        output = diagrams_dir / 'overview.html'
        write_html(output, 'overview.html', data)
        generated.append(output)
        click.echo(f'Overview: {output}')

    if app:
        data = generate_app_detail_data(iac_dir, app)
        if data['nodes']:
            output = diagrams_dir / f'{app}.html'
            write_html(output, 'app_detail.html', data)
            generated.append(output)
            click.echo(f'App {app}: {output}')
        else:
            click.echo(f'App "{app}" não encontrado ou vazio.')

    if all_apps:
        structure = load_structure(iac_dir)
        for app_name in structure.get('apps', {}):
            data = generate_app_detail_data(iac_dir, app_name)
            if data['nodes']:
                output = diagrams_dir / f'{app_name}.html'
                write_html(output, 'app_detail.html', data)
                generated.append(output)
        click.echo(f'Gerados {len(generated)} diagramas em {diagrams_dir}')

    if open_browser and generated:
        import webbrowser

        webbrowser.open(f'file://{generated[0]}')


if __name__ == '__main__':
    main()
