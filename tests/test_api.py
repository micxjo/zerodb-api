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


def test_delete(api_server, session, db):
    oid = next(db[Page].all())._p_uid
    url = "{}/Page/{}".format(api_server, oid)
    resp = session.delete(url)
    assert resp.status_code == 204

    resp = session.get(url)
    assert resp.status_code == 404


def test_delete_forbidden(api_server):
    assert_forbidden(requests.delete(api_server + '/Page/0'))


def test_delete_not_found(api_server, session):
    # Is 404 appropriate here?
    resp = session.delete(api_server + '/Page/0')
    assert resp.status_code == 404


def test_insert(api_server, session):
    obj = {
        'title': "A title",
        'text': "Some text",
        'num': 4
    }

    resp = session.post(api_server + '/Page', json=obj)
    assert_success(resp)
    oid = resp.json()["$oid"]

    resp = session.get("{}/Page/{}".format(api_server, oid))
    assert_success(resp)
    assert resp.json() == obj


def test_insert_forbidden(api_server):
    assert_forbidden(requests.post(api_server + '/Page', json={
        'title': "A title",
        'text': "Some text",
        'num': 4
    }))


def test_insert_not_found(api_server, session):
    resp = session.post(api_server + '/Nonexistent', json={'foo': 'bar'})
    assert resp.status_code == 404


def test_find(api_server, session):
    criteria = {'text': {'$text': "something"}}

    resp = session.get(api_server + '/Page/_find', json={
        'criteria': criteria
    })
    assert_success(resp)
    data = resp.json()
    assert data['count'] == 10
    assert len(data['objects']) == 10

    resp = session.get(api_server + '/Page/_find', json={
        'criteria': criteria,
        'limit': 9
    })
    assert_success(resp)
    data = resp.json()
    assert data['count'] == 9
    assert len(data['objects']) == 9

    # TODO: Test skip w/o limit once the behavior is clarified
    resp = session.get(api_server + '/Page/_find', json={
        'criteria': criteria,
        'skip': 2,
        'limit': 10
    })
    assert_success(resp)
    data = resp.json()
    assert data['count'] == 8
    assert len(data['objects']) == 8


def test_find_sort(api_server, session):
    criteria = {'text': {'$text': "something"}}

    resp = session.get(api_server + '/Page/_find', json={
        'criteria': criteria,
        'sort': 'title'
    })
    assert_success(resp)
    data = resp.json()
    assert data['count'] == 10
    assert len(data['objects']) == 10

    rev_resp = session.get(api_server + '/Page/_find', json={
        'criteria': criteria,
        'sort': '-title'
    })
    assert_success(rev_resp)
    rev_data = rev_resp.json()
    assert rev_data['count'] == 10
    assert rev_data['objects'] == list(reversed(data['objects']))


def test_find_forbidden(api_server):
    assert_forbidden(requests.get(api_server + '/Page/_find', json={
        'title': "Foo"
    }))


def test_find_not_found(api_server, session):
    resp = session.get(api_server + '/Nonexistent/_find', json={
        'title': "Foo"
    })
    assert resp.status_code == 404
