"""Client GitLab para leitura de issues e postagem de comentários.

Usa a biblioteca python-gitlab para autenticação e acesso à API.
"""

from __future__ import annotations

import logging
import re

import gitlab

logger = logging.getLogger(__name__)


class GitLabClient:
    """Client para interagir com issues do GitLab."""

    def __init__(self, url: str, private_token: str, project_id: int | str | None = None, project_path: str | None = None):
        """Inicializa e autentica o client GitLab.

        Aceita project_id (int) ou project_path (str 'group/project').
        """
        self.gl = gitlab.Gitlab(url, private_token=private_token)
        self.gl.auth()
        if project_path and not project_id:
            self.project = self.gl.projects.get(project_path)
        else:
            self.project = self.gl.projects.get(int(project_id))
        logger.info(f'Conectado ao GitLab project {self.project.id}')

    def get_issue(self, issue_id: int) -> dict:
        """Busca uma issue e retorna como dict com title, description, labels.

        Args:
            issue_id: Identificador interno (iid) da issue no projeto.

        Returns:
            Dict com title, description, labels, iid e state.
        """
        issue = self.project.issues.get(int(issue_id))
        return {
            'title': issue.title,
            'description': issue.description or '',
            'labels': issue.labels,
            'iid': issue.iid,
            'state': issue.state,
        }

    def add_comment(self, issue_id: int, body: str) -> None:
        """Adiciona comentário a uma issue.

        Args:
            issue_id: Identificador interno (iid) da issue no projeto.
            body: Texto do comentário em Markdown.
        """
        issue = self.project.issues.get(int(issue_id))
        issue.discussions.create({'body': body})
        logger.info(f'Comentário adicionado à issue {issue_id}.')

    def add_labels(self, issue_id: int, labels: list[str]) -> None:
        """Adiciona labels a uma issue (preserva existentes).

        Args:
            issue_id: Identificador interno (iid) da issue no projeto.
            labels: Lista de labels a adicionar.
        """
        issue = self.project.issues.get(int(issue_id))
        current = set(issue.labels)
        current.update(labels)
        issue.labels = list(current)
        issue.save()
        logger.info(f'Labels {labels} adicionados à issue {issue_id}.')


def parse_issue_url(url: str) -> tuple[str, int, int] | None:
    """Extrai gitlab_url, project_id e issue_id de uma URL de issue.

    Suporta formatos::

        https://gitlab.example.com/group/project/-/issues/123
        https://gitlab.example.com/group/project/-/work_items/123

    Args:
        url: URL completa da issue no GitLab.

    Returns:
        Tupla (gitlab_url, project_path, issue_id) ou None se não reconhecer.
    """
    # work_items ou issues
    match = re.match(
        r'(https?://[^/]+)/([^/]+/[^/]+)/-/(?:issues|work_items)/(\d+)',
        url,
    )
    if match:
        gitlab_url = match.group(1)
        project_path = match.group(2)
        issue_id = int(match.group(3))
        return gitlab_url, project_path, issue_id
    return None
