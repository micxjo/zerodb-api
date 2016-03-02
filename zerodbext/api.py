import imp
import jsonpickle
import sys

import pkg_resources
import six
from flask import Flask, jsonify

__version__ = '0.1.0'

HOST = 'localhost'
PORT = 17234
DEV_SECRET_KEY = "a very secret secret"
DEBUG = True

models = None
zeo_socket = None
dbs = {}
pickler = jsonpickle.pickler.Pickler(unpicklable=False)

app = Flask(__name__)


@app.route('/_version', methods=['GET'])
def version():
    """Returns the version of zerodb, zerodb-api and python for this API."""
    return jsonify({'zerodb-api': __version__,
                    'zerodb': pkg_resources.get_distribution('zerodb').version,
                    'python': sys.version})


def run(data_models=None, host=HOST, port=PORT, debug=DEBUG,
        secret_key=DEV_SECRET_KEY, zeo_socket=None, **kw):
    """Runs the API server.

    :param data_models: the ZeroDB models to use
    :param host: the API host, default 'localhost'
    :param port: the API port, default 17234
    :param debug: run in Flask DEBUG mode
    :param secret_key: used for signing cookies
    :param zeo_socket: the ZEO socket to connect to
    :param kw: additional params are sent to Flask.run()
    """
    global models

    if isinstance(data_models, six.string_types):
        models = imp.load_source('models', data_models)
    else:
        models = data_models

    globals()['zeo_socket'] = zeo_socket

    app.config['SECRET_KEY'] = secret_key
    app.run(host=host, port=port, debug=debug, **kw)


if __name__ == '__main__':
    run()
