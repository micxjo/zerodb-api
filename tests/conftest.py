import tempfile
from multiprocessing import Process

import pytest
import shutil
import zerodb
from os import path
from zerodb.crypto import ecc
from zerodb.permissions import elliptic
from zerodb.storage import ZEOServer

from db import TEST_PASSPHRASE, create_objects_and_close

TEST_PUBKEY = ecc.private(TEST_PASSPHRASE).get_pubkey()
TEST_PUBKEY_3 = ecc.private(TEST_PASSPHRASE + ' third').get_pubkey()
TEST_PERMISSIONS = """realm ZERO
root:%s
third:%s""" % (TEST_PUBKEY.encode('hex'), TEST_PUBKEY_3.encode('hex'))

ZEO_CONFIG = """<zeo>
  address %(sock)s
  authentication-protocol ecc_auth
  authentication-database %(pass_file)s
  authentication-realm ZERO
</zeo>

<filestorage>
  path %(dbfile)s
  pack-gc false
</filestorage>"""

elliptic.register_auth()


@pytest.fixture(scope='module')
def tempdir(request):
    tmpdir = tempfile.mkdtemp()

    @request.addfinalizer
    def fin():
        shutil.rmtree(tmpdir)

    return tmpdir


@pytest.fixture(scope='module')
def pass_file(request, tempdir):
    filename = path.join(tempdir, 'authdb.conf')
    with open(filename, 'w') as f:
        f.write(TEST_PERMISSIONS)
    return filename


def do_zeo_server(request, pass_file, tempdir):
    sock = path.join(tempdir, 'zeosocket_auth')
    zeroconf_file = path.join(tempdir, 'zeo.config')
    dbfile = path.join(tempdir, 'db2.fs')

    with open(zeroconf_file, 'w') as f:
        f.write(ZEO_CONFIG % {
            'sock': sock,
            'pass_file': pass_file,
            'dbfile': dbfile
        })

    server = Process(target=ZEOServer.run,
                     kwargs={'args': ('-C', zeroconf_file)})

    @request.addfinalizer
    def fin():
        server.terminate()
        server.join()

    server.start()
    return sock


@pytest.fixture(scope='module')
def zeo_server(request, pass_file, tempdir):
    sock = do_zeo_server(request, pass_file, tempdir)
    create_objects_and_close(sock)
    return sock


@pytest.fixture(scope='module')
def db(request, zeo_server):
    zdb = zerodb.DB(zeo_server, username='root', password=TEST_PASSPHRASE,
                    debug=True)

    @request.addfinalizer
    def fin():
        zdb.disconnect()

    return zdb
