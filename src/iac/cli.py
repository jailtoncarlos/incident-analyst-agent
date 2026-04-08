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
@click.option('--issue-url', type=str, default=None, help='URL da issue no GitLab.')
@click.option('--title', type=str, default=None, help='Título do incidente.')
@click.option('--description', type=str, default=None, help='Descrição do incidente.')
@click.option('--base-dir', type=click.Path(exists=True), default='.', help='Diretório raiz do projeto.')
@click.option('--llm', type=click.Choice(['ollama', 'gemini']), default=None, help='Backend LLM.')
@click.option('--llm-url', type=str, default=None, help='Endpoint do LLM.')
@click.option('--llm-key', type=str, default=None, help='API key do LLM.')
@click.option('--llm-model', type=str, default='qwen2.5:7b', help='Modelo do LLM.')
@click.option('--gitlab-token', type=str, envvar='GITLAB_TOKEN', default=None, help='Token GitLab.')
@click.option('--mode', type=click.Choice(['auto', 'single', 'multi']), default='auto', help='Modo: auto (detecta pelo modelo), single (1 prompt), multi (iterativo).')
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

    from iac.config.settings import load_graph, load_structure, get_effective_config
    from iac.agent.orchestrator import analyze_issue, format_structural_analysis, format_context_for_prompt, get_model_profile
    from iac.agent.prompts import (
        build_analysis_prompt, build_response_prompt, extract_tipo_from_analysis,
        build_investigation_prompt, parse_investigation_requests,
        resolve_investigation_requests, build_evidence_prompt,
    )

    # Configuração efetiva: config.yaml + CLI args
    cfg = get_effective_config(iac_dir, {
        'llm': llm, 'llm_model': llm_model, 'llm_url': llm_url, 'llm_key': llm_key,
        'gitlab_token': gitlab_token, 'mode': mode,
    })

    # Aplicar config (CLI args já sobrescreveram)
    llm = llm or cfg['llm'].get('backend')
    llm_model = cfg['llm']['model']
    llm_url = llm_url or cfg['llm'].get('url')
    llm_key = llm_key or cfg['llm'].get('key')
    gitlab_token = gitlab_token or cfg['gitlab'].get('token')
    mode = cfg['analyze'].get('mode', mode)

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
            click.echo('Token GitLab necessário. Use --gitlab-token, GITLAB_TOKEN ou config.yaml.')
            sys.exit(1)

        click.echo(f'Buscando issue {issue_id} no GitLab...')
        gl = __import__('gitlab').Gitlab(gitlab_url_parsed, private_token=token)
        gl.auth()
        try:
            project = gl.projects.get(project_path)
        except Exception:
            click.echo(f'Projeto {project_path} não encontrado.')
            sys.exit(1)

        gitlab_client = GitLabClient(gitlab_url_parsed, token, project.id)
        issue_data = gitlab_client.get_issue(issue_id)
        title = issue_data['title']
        description = issue_data['description']
        click.echo(f'Issue: {title}')

    if not title:
        title = ''

    if not description:
        description = ''

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

    # 4. Determinar modo
    if mode == 'auto' and llm:
        profile = get_model_profile(llm_model)
        use_multi = profile is get_model_profile('qwen2.5:7b')  # small → multi
        # Heurística: small usa multi, medium/large usa single
        for profile_name, profile_val in __import__('iac.agent.orchestrator', fromlist=['MODEL_PROFILES']).MODEL_PROFILES.items():
            if profile is profile_val:
                use_multi = profile_name == 'small'
                break
    elif mode == 'multi':
        use_multi = True
    else:
        use_multi = False

    # Helper para enviar ao LLM
    def _send_llm(prompt_text):
        if llm == 'ollama':
            from iac.integrations import ollama
            _url = llm_url or 'http://localhost:11434/v1/chat/completions'
            return ollama.chat(prompt_text, url=_url, model=llm_model, api_key=llm_key)
        elif llm == 'gemini':
            from iac.integrations import gemini
            if not llm_url or not llm_key:
                click.echo('Gemini requer --llm-url e --llm-key.')
                return None
            return gemini.chat(prompt_text, url=llm_url, api_key=llm_key)
        return None

    # 5. Enviar ao LLM
    llm_analysis = None
    if llm and use_multi:
        # --- MODO MULTI-PROMPT ---
        click.echo(f'\n[Modo multi-prompt] Passo 1: investigação...')
        investigation_prompt = build_investigation_prompt(result)
        click.echo(f'Enviando prompt ao {llm} ({llm_model}, {len(investigation_prompt)} chars)...')

        investigation_response = _send_llm(investigation_prompt)
        if investigation_response:
            click.echo('\n--- Passo 1: O que o LLM quer investigar ---\n')
            click.echo(investigation_response)

            # Parsear pedidos
            requests = parse_investigation_requests(investigation_response)
            if requests:
                click.echo(f'\n[Modo multi-prompt] Passo 2: resolvendo {len(requests)} pedidos...')
                evidence = resolve_investigation_requests(requests, structure, graph, base)
                click.echo(f'Evidência coletada: {len(evidence)} chars')

                # Enviar evidência + pedir análise final
                evidence_prompt = build_evidence_prompt(evidence)
                click.echo(f'Enviando prompt final ao {llm} ({len(evidence_prompt)} chars)...')
                llm_analysis = _send_llm(evidence_prompt)
            else:
                click.echo('LLM não pediu investigação adicional.')
                # Fallback: usar prompt único
                prompt = build_analysis_prompt(result)
                llm_analysis = _send_llm(prompt)
        else:
            click.echo('LLM não respondeu no passo 1.')

    elif llm:
        # --- MODO SINGLE-PROMPT ---
        prompt = build_analysis_prompt(result)
        click.echo(f'\nEnviando prompt ao {llm} ({llm_model}, {len(prompt)} chars)...')
        llm_analysis = _send_llm(prompt)

    if llm_analysis:
        click.echo('\n--- Análise do LLM ---\n')
        click.echo(llm_analysis)

        # Extrair tipo
        tipo = extract_tipo_from_analysis(llm_analysis)
        if tipo:
            click.echo(f'\nClassificação: {tipo}')
            result['classification']['tipo_sugerido'] = tipo
            if tipo not in result['classification']['labels_sugeridos']:
                result['classification']['labels_sugeridos'].append(tipo)

        # Gerar resposta ao usuário (se tem interessado)
        if result['classification'].get('interessado'):
            response_prompt = build_response_prompt(result, llm_analysis)
            click.echo(f'\nGerando resposta ao usuário...')
            response_text = _send_llm(response_prompt)
            if response_text:
                click.echo('\n--- Rascunho de resposta ---\n')
                click.echo(response_text)
    elif llm:
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
    """Gerencia configuração do projeto (.iac/config.yaml)."""
    base = Path(base_dir).resolve()
    iac_dir = base / IAC_DIR

    if not iac_dir.exists():
        click.echo('Nenhuma inspeção encontrada. Execute `iac init` primeiro.')
        sys.exit(1)

    from iac.config.settings import load_user_config, save_user_config

    config = load_user_config(iac_dir)

    if set_values:
        for item in set_values:
            if '=' not in item:
                click.echo(f'Formato inválido: {item}. Use seção.chave=valor')
                continue
            key, value = item.split('=', 1)
            parts = key.split('.')
            if len(parts) == 2:
                section, field = parts
                if section not in config:
                    config[section] = {}
                config[section][field] = value
                click.echo(f'{section}.{field} = {value}')
            else:
                click.echo(f'Formato inválido: {item}. Use seção.chave=valor')

        save_user_config(iac_dir, config)

    if show or not set_values:
        import yaml
        click.echo(yaml.dump(config, default_flow_style=False, allow_unicode=True))


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
