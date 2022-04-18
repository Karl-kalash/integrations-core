# (C) Datadog, Inc. 2022-present
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import csv
import json
import os
import re
import sys
import time
from contextlib import contextmanager
from copy import deepcopy

import mock
import pytest

from datadog_checks.dev import get_here

from .common import E2E_METADATA, TERADATA_DD_PW, TERADATA_DD_USER, TERADATA_SERVER, USE_TD_SANDBOX

TABLE_EXTRACTION_PATTERN = re.compile(r'SELECT .* FROM \w+\.(\w+)')
HERE = get_here()

sys.modules['teradatasql'] = mock.MagicMock()

CONFIG = {
    'server': 'tdserver',
    'username': 'datadog',
    'password': 'td_datadog',
    'database': 'AdventureWorksDW',
    'use_tls': False,
    'collect_res_usage': True,
    'tags': ['td_env:dev'],
}

E2E_CONFIG = {
    'server': TERADATA_SERVER,
    'username': TERADATA_DD_USER,
    'password': TERADATA_DD_PW,
    'database': 'AdventureWorksDW',
    'use_tls': False,
    'collect_res_usage': True,
}


@pytest.fixture(scope='session')
def dd_environment(e2e_instance, instance):
    if USE_TD_SANDBOX:
        if not TERADATA_SERVER or not TERADATA_DD_USER or not TERADATA_DD_PW:
            raise Exception("Please set TERADATA_SERVER, TERADATA_DD_USER, TERADATA_DD_PW environment variables to valid Teradata sandbox credentials.")
        else:
            dd_instance = e2e_instance
            e2e_metadata = E2E_METADATA
    else:
        dd_instance = instance
        e2e_metadata = {}

    yield dd_instance, e2e_metadata


@pytest.fixture(scope='session')
def instance():
    return deepcopy(CONFIG)


@pytest.fixture
def bad_instance():
    bad_config = deepcopy(CONFIG)
    bad_config['server'] = 'localhost'
    return bad_config


@pytest.fixture(scope='session')
def e2e_instance():
    return deepcopy(E2E_CONFIG)


@pytest.fixture
def cursor_factory():
    """
    This cursor factory fixture yields a mock cursor returned from the mock `teradatasql.connect` connection.
    If the factory receives the argument `exception=True`, it raises an Exception side effect from
    the mock `teradatasql.connect` connection.
    """

    @contextmanager
    def _cursor(exception=False):
        with mock.patch('datadog_checks.teradata.check.teradatasql') as teradatasql:
            cursor = mock.MagicMock(name='cursor')

            if exception:
                connect = mock.MagicMock(
                    name='connect',
                    cursor=lambda: cursor,
                    side_effect=Exception(
                        'Unable to connect to Teradata. [Version 17.10.0.11] [Session 0] '
                        '[Teradata SQL Driver] Failed to connect to localhost'
                    ),
                )
                teradatasql.connect.side_effect = connect
            else:
                connect = mock.MagicMock(name='connect', cursor=lambda: cursor)
                teradatasql.connect.return_value = connect

            cursor.execute = lambda x: setattr(cursor, 'mock_last_query', x)  # noqa
            cursor.rowcount = float('+inf')
            cursor.fetchall = lambda: _mock_execute(cursor.mock_last_query)
            yield

    yield _cursor


def _mock_execute(query):
    table = TABLE_EXTRACTION_PATTERN.search(query).groups()[0].lower()
    file = os.path.join(HERE, 'fixtures', table + '.csv')
    with open(file, 'r') as f:
        reader = csv.reader(f)
        for line in reader:
            for idx, col in enumerate(line):
                # replace res usage csv timestamp with current timestamp
                if table == 'resspmaview':
                    line[0] = int(time.time())
                # transform empty column result to None type
                if col == '':
                    line[idx] = None
            yield line


@pytest.fixture()
def expected_metrics():
    file_names = ['allspacev.json', 'ampusagev.json', 'resspmaview.json']
    metrics = []
    for file_name in file_names:
        with open(os.path.join(HERE, 'results', file_name), 'r') as f:
            metrics.extend(json.load(f))
    return metrics
