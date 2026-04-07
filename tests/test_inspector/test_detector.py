"""Testes para o detector de framework."""

from pathlib import Path

from iac.inspector.detector import detect_framework


def test_detect_django(tmp_path: Path):
    """Deve detectar Django quando manage.py existe."""
    manage = tmp_path / 'manage.py'
    manage.write_text("import os\nos.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')\n")
    config = detect_framework(tmp_path)
    assert config['framework'] == 'django'
    assert config['settings_module'] == 'myproject.settings'


def test_detect_flask(tmp_path: Path):
    """Deve detectar Flask quando app.py com Flask import existe."""
    app = tmp_path / 'app.py'
    app.write_text('from flask import Flask\napp = Flask(__name__)\n')
    config = detect_framework(tmp_path)
    assert config['framework'] == 'flask'


def test_detect_fastapi(tmp_path: Path):
    """Deve detectar FastAPI quando main.py com FastAPI import existe."""
    main = tmp_path / 'main.py'
    main.write_text('from fastapi import FastAPI\napp = FastAPI()\n')
    config = detect_framework(tmp_path)
    assert config['framework'] == 'fastapi'


def test_detect_python_generic(tmp_path: Path):
    """Deve detectar Python genérico quando pyproject.toml existe."""
    pyproject = tmp_path / 'pyproject.toml'
    pyproject.write_text('[project]\nname = "mylib"\n')
    config = detect_framework(tmp_path)
    assert config['framework'] == 'python'


def test_detect_unknown(tmp_path: Path):
    """Deve retornar unknown quando nenhum framework é reconhecido."""
    config = detect_framework(tmp_path)
    assert config['framework'] == 'unknown'
