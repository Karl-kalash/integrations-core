# (C) Datadog, Inc. 2022-present
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import os

import pytest
from click.testing import CliRunner

from datadog_checks.dev.tooling.cli import ddev
from datadog_checks.dev.tooling.constants import set_root
from datadog_checks.dev.tooling.utils import load_project_file_at_cached, load_project_file_cached


def _build_pyproject_file(authors):
    return f'''
[project]
name = "datadog-my-check"
authors = {authors}
[tool.hatch.version]
path = "datadog_checks/my_check/__about__.py"
'''


@pytest.fixture
def clear_cache():
    """
    Clears all relevant caches before and after a test
    """
    _clear_cache()
    yield
    _clear_cache()


def _clear_cache():
    # project files are cached through @lru_cache
    load_project_file_at_cached.cache_clear()
    load_project_file_cached.cache_clear()
    # It's necessary to reset the root because each test runs on a different temp dir
    # but ddev caches the root
    set_root('')


@pytest.mark.usefixtures('clear_cache')
@pytest.mark.parametrize(
    'authors,expected_exit_code,expected_output',
    [
        ('[{ name = "Datadog", email = "packages@datadoghq.com" }]', 0, '1 valid'),
        ('[{ name = "Datadog"}]', 0, '1 valid'),
        ('[{ name = "Datadog", email = "invalid_email" }]', 1, 'Invalid email'),
    ],
)
def test_validate_package_validates_emails(authors, expected_exit_code, expected_output):
    runner = CliRunner()

    with runner.isolated_filesystem():
        os.mkdir('my_check')

        with open('my_check/pyproject.toml', 'w') as f:
            f.write(_build_pyproject_file(authors))

        os.makedirs('my_check/datadog_checks/my_check')
        with open('my_check/datadog_checks/my_check/__about__.py', 'w') as f:
            f.write('__version__ = "1.0.0"')

        result = runner.invoke(ddev, ['-x', 'validate', 'package', 'my_check'])

        assert result.exit_code == expected_exit_code
        assert expected_output in result.output
