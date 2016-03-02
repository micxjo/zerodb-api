import socket
import time
from multiprocessing import Process

from os import path

import pkg_resources
import pytest
import sys

import requests

from zerodbext import api


@pytest.fixture(scope='module')
def api_server(request, db):
    """The URL of a test instance of the API.

    A ZeroDB server and an instance of the API configured for the test models
    located in db.py will be spun up in separate processes (and cleaned
    up on when the fixture is finalized).
    """
    # Get an available TCP socket
    sock = socket.socket()
    sock.bind(('localhost', 0))
    _, port = sock.getsockname()
    sock.close()

    def api_run(**kw):
        api.run(use_reloader=False, **kw)

    server = Process(
        target=api_run,
        kwargs={
            'host': 'localhost',
            'port': port,
            'data_models': path.join(path.dirname(__file__), 'db.py'),
            'zeo_socket': db._storage._addr
        })

    @request.addfinalizer
    def fin():
        server.terminate()
        server.join()

    server.start()
    time.sleep(0.2)

    return "http://localhost:{}".format(port)


def assert_success(response):
    """Asserts that the response has a 200 status and json content type."""
    assert response.status_code == 200
    assert response.headers['Content-Type'] == 'application/json'


def test_version(api_server):
    resp = requests.get(api_server + '/_version')
    assert_success(resp)

    data = resp.json()
    assert data['zerodb'] == pkg_resources.get_distribution('zerodb').version
    assert data['zerodb-api'] == api.__version__
    assert data['python'] == sys.version
