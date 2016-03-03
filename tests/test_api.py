import socket
import time
from multiprocessing import Process

from os import path

import pkg_resources
import pytest
import sys

import requests

from db import TEST_PASSPHRASE, Page
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


def api_connect(api_server, session):
    return session.post(api_server + '/_connect', json={
        'username': 'root',
        'passphrase': TEST_PASSPHRASE
    })


def api_disconnect(api_server, session):
    return session.post(api_server + '/_disconnect')


@pytest.fixture(scope="function")
def session(request, api_server):
    """
    A requests session which has an auth cookie for the test database.

    Calls /_disconnect on finalization.
    """
    sess = requests.Session()
    api_connect(api_server, sess)

    request.addfinalizer(lambda: api_disconnect(api_server, sess))

    return sess


def assert_success(response):
    """Asserts that the response has a 200 status and json content type."""
    assert response.status_code == 200
    assert response.headers['Content-Type'] == 'application/json'


def assert_forbidden(response):
    """Asserts that the response is a 403 Forbidden."""
    assert response.status_code == 403


def test_version(api_server):
    resp = requests.get(api_server + '/_version')
    assert_success(resp)

    data = resp.json()
    assert data['zerodb'] == pkg_resources.get_distribution('zerodb').version
    assert data['zerodb-api'] == api.__version__
    assert data['python'] == sys.version


def test_connect(api_server):
    session = requests.Session()
    resp = api_connect(api_server, session)
    assert resp.status_code == 204


def test_disconnect(api_server):
    session = requests.Session()
    api_connect(api_server, session)
    resp = api_disconnect(api_server, session)
    assert resp.status_code == 204


def test_get(api_server, session, db):
    page = next(db[Page].all())
    resp = session.get("{}/Page/{}".format(api_server, page._p_uid))
    assert_success(resp)

    data = resp.json()
    assert data['title'] == page.title
    assert data['text'] == page.text
    assert data['num'] == page.num


def test_get_forbidden(api_server):
    assert_forbidden(requests.get(api_server + '/Page/0'))


def test_get_not_found(api_server, session):
    resp = session.get(api_server + '/Page/0')
    assert resp.status_code == 404
