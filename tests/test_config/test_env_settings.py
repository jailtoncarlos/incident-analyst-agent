"""Testes para validar que .env gerado no init contém todas as variáveis do app_settings.

Garante que o template env.template (usado no iac init) documenta
todas as variáveis que app_settings.py aceita.
"""

from pathlib import Path


def _get_env_template_vars() -> set[str]:
    """Extrai variáveis do env.template (comentadas ou não)."""
    from iac.config.settings import get_defaults_dir

    template = get_defaults_dir() / 'env.template'
    content = template.read_text(encoding='utf-8')
    variables = set()
    for line in content.splitlines():
        line = line.strip()
        if line.startswith('#'):
            line = line.lstrip('#').strip()
        if '=' in line and not line.startswith('Copie') and not line.startswith('Hierarquia'):
            var_name = line.split('=')[0].strip()
            if var_name and var_name[0].isupper():
                variables.add(var_name)
    return variables


def _get_app_settings_vars() -> set[str]:
    """Extrai variáveis aceitas pelo app_settings.py."""
    return {
        # LLMSettings (env_prefix: IAC_LLM_)
        'IAC_LLM_BACKEND',
        'IAC_LLM_MODEL',
        'IAC_LLM_URL',
        'IAC_LLM_KEY',
        'IAC_LLM_RATE_DELAY',
        'IAC_LLM_MAX_RETRIES',
        # API keys diretas
        'GROQ_API_KEY',
        'DEEPSEEK_API_KEY',
        'GEMINI_API_KEY',
        # GitLabSettings (env_prefix: IAC_GITLAB_)
        'GITLAB_TOKEN',
        # AnalyzeSettings (env_prefix: IAC_ANALYZE_)
        'IAC_ANALYZE_MODE',
    }


def test_env_template_contem_todas_variaveis_do_settings():
    """O env.template deve documentar TODAS as variáveis que app_settings aceita."""
    template_vars = _get_env_template_vars()
    settings_vars = _get_app_settings_vars()

    missing = settings_vars - template_vars
    assert not missing, f'Variáveis em app_settings mas ausentes no env.template: {missing}'


def test_env_template_nao_tem_variaveis_orfas():
    """O env.template NÃO deve ter variáveis que app_settings não conhece."""
    template_vars = _get_env_template_vars()
    settings_vars = _get_app_settings_vars()

    orphans = template_vars - settings_vars
    assert not orphans, f'Variáveis no env.template mas desconhecidas pelo app_settings: {orphans}'


def test_env_gerado_no_init_contem_todas_variaveis(tmp_path):
    """O .env gerado pelo iac init deve conter todas as variáveis."""
    from iac.cli import _generate_default_artifacts

    project = tmp_path / 'test-project'
    project.mkdir()
    iac_dir = project / '.iac'
    iac_dir.mkdir()
    _generate_default_artifacts(iac_dir, {'framework': 'Django'})

    env_content = (iac_dir / '.env').read_text(encoding='utf-8')
    settings_vars = _get_app_settings_vars()

    for var in settings_vars:
        assert var in env_content, f'Variável {var} ausente no .env gerado pelo init'


def test_env_gerado_tem_instrucoes_de_api_keys(tmp_path):
    """O .env gerado deve ter instruções de onde obter API keys."""
    from iac.cli import _generate_default_artifacts

    project = tmp_path / 'test-project'
    project.mkdir()
    iac_dir = project / '.iac'
    iac_dir.mkdir()
    _generate_default_artifacts(iac_dir, {'framework': 'Django'})

    env_content = (iac_dir / '.env').read_text(encoding='utf-8')
    assert 'console.groq.com' in env_content
    assert 'platform.deepseek.com' in env_content
    assert 'aistudio.google.com' in env_content
