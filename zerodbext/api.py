import imp
import jsonpickle
import sys

import pkg_resources
import six
import transaction
import zerodb
from flask import Flask, jsonify, request, session, abort
from zerodb.catalog import query_json
from zerodb.catalog.query import optimize

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


@app.route("/_connect", methods=["POST"])
def connect():
    """Opens a ZeroDB connection.

    A JSON object containing a valid 'username' and 'passphrase' should be
    sent as the request body. Additionally, a 'host' and optional 'port' can
    be supplied to specify the ZeroDB server location; otherwise defaults will
    be used.

    The response will contain an authorization cookie that should be used
    in future requests.
    """
    data = request.get_json()
    username = data.get('username')
    passphrase = data.get('passphrase')

    if zeo_socket:
        socket = zeo_socket
    else:
        host = data.get('host')
        port = data.get('port')
        if host and port:
            socket = (host, port)
        elif host:
            socket = host
        else:
            socket = None

    if not (username and passphrase and socket):
        resp = jsonify(error="Incomplete login information.")
        resp.status_code = 400
        return resp

    try:
        db = zerodb.DB(socket, username=username, password=passphrase)
    except Exception as ex:
        resp = jsonify(error=str(ex),
                       error_class=ex.__class__.__name__)
        resp.status_code = 400
        return resp

    session['username'] = username
    dbs[username] = db

    return Flask.response_class(status=204)


@app.route('/_disconnect', methods=['POST'])
def disconnect():
    """Closes the ZeroDB connection."""
    if 'username' in session:
        username = session.pop('username')
        if username in dbs:
            del dbs[username]
    return Flask.response_class(status=204)


def session_db_or_403():
    """Gets the session DB, or raises a 403 exception if not connected."""
    try:
        return dbs[session["username"]]
    except KeyError:
        abort(403)


def model_or_404(model_name):
    """Gets the named model class, or raises a 404 if not found."""
    try:
        return getattr(models, model_name)
    except AttributeError:
        abort(404)


@app.route('/<model_name>/<int:oid>', methods=['GET'])
def get(model_name, oid):
    """Returns a jsonified object based on its model name and objectID."""
    db = session_db_or_403()
    model = model_or_404(model_name)

    try:
        obj = db[model][oid]
    except KeyError:
        abort(404)
    else:
        return jsonify(pickler.flatten(obj))


@app.route('/<model_name>/<int:oid>', methods=['DELETE'])
def delete(model_name, oid):
    """Deletes an object based on its model name and objectID."""
    db = session_db_or_403()
    model = model_or_404(model_name)

    try:
        with transaction.manager:
            db[model].remove(oid)
    except KeyError:
        abort(404)

    return Flask.response_class(status=204)


@app.route('/<model_name>', methods=['POST'])
def insert(model_name):
    """Inserts a model object.

    Returns a JSON response containing the newly created objectID.
    """
    db = session_db_or_403()
    model = model_or_404(model_name)

    try:
        data = request.get_json()
        obj = model(**data)
        with transaction.manager:
            oid = db.add(obj)
        return jsonify({"$oid": oid})
    except Exception as ex:
        resp = jsonify(error=str(ex),
                       error_class=ex.__class__.__name__)
        resp.status_code = 400
        return resp


# POST is allowed for clients that don't like GET bodies.
@app.route('/<model_name>/_find', methods=['GET', 'POST'])
def find(model_name):
    """Queries the given model.

    Request body should be a JSON object with a 'criteria' member in the
    ZeroDB query format. Optional 'skip', 'limit' and 'sort' members can be
    provided.
    """
    db = session_db_or_403()
    model = model_or_404(model_name)

    query = request.get_json()
    criteria = optimize(query_json.compile(query['criteria']))

    skip = query.get('skip')
    if skip:
        skip = int(skip)

    limit = query.get('limit')
    if limit:
        limit = int(limit)

    sort = query.get('sort')
    if isinstance(sort, six.string_types):
        if sort.startswith('-'):
            sort_index = sort[1:].strip()
            reverse = True
        else:
            sort_index = sort
            reverse = None
    elif isinstance(sort, dict):
        assert len(sort) == 1
        sort_index, direction = sort.popitem()
        reverse = direction >= 0
    else:
        sort_index = None
        reverse = None

    result = db[model].query(criteria, skip=skip, limit=limit,
                             sort_index=sort_index, reverse=reverse)
    objs = [pickler.flatten(o) for o in result]

    return jsonify(objects=objs, count=len(objs))


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
