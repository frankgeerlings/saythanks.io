# -*- coding: utf-8 -*-

#  _____         _____ _           _
# |   __|___ _ _|_   _| |_ ___ ___| |_ ___
# |__   | .'| | | | | |   | .'|   | '_|_ -|
# |_____|__,|_  | |_| |_|_|__,|_|_|_,_|___|
#           |___|

import os
import jwt

from base64 import b64decode
from functools import wraps
from uuid import uuid4
from flask import Flask, request, session, render_template, abort, jsonify
from flask import _request_ctx_stack


# Application Basics
# ------------------


app = Flask(__name__)
app.secret_key = os.environ.get('APP_SECRET', 'CHANGEME')
app.debug = True


# Application Security
# --------------------

# CSRF Protection.
# @app.before_request
def csrf_protect():
    """Blocks incoming POST requests if a proper CSRF token is not provided."""
    if request.method == "POST":
        token = session.pop('_csrf_token', None)
        if not token or token != request.form.get('_csrf_token'):
            abort(403)

def generate_csrf_token():
    """Generates a CSRF token."""
    if '_csrf_token' not in session:
        session['_csrf_token'] = str(uuid4())
    return session['_csrf_token']

# Register the CSRF token with jinja2.
app.jinja_env.globals['csrf_token'] = generate_csrf_token


# Auth0 Integration
# -----------------

auth_id = os.environ['AUTH0_CLIENT_ID']
auth_secret = os.environ['AUTH0_CLIENT_SECRET']
auth_callback_url = os.environ['AUTH0_CALLBACK_URL']
auth_domain = os.environ['AUTH0_DOMAIN']

# Format error response and append status code.
def handle_error(error, status_code):
    """Error handler for incorrect authorization usage."""
    resp = jsonify(error)
    resp.status_code = status_code
    return resp

def requires_auth(f):
    """Decorator—used for API routes that reuqire authorization."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get('Authorization', None)
        if not auth:
            return handle_error({'code': 'authorization_header_missing', 'description': 'Authorization header is expected'}, 401)

        parts = auth.split()

        if parts[0].lower() != 'bearer':
            return handle_error({'code': 'invalid_header', 'description': 'Authorization header must start with Bearer'}, 401)
        elif len(parts) == 1:
            return handle_error({'code': 'invalid_header', 'description': 'Token not found'}, 401)
        elif len(parts) > 2:
            return handle_error({'code': 'invalid_header', 'description': 'Authorization header must be Bearer + \s + token'}, 401)

        token = parts[1]
        try:
            payload = jwt.decode(
                token,
                b64decode(auth_secret.replace("_","/").replace("-","+")),
                audience=auth_id
            )
        except jwt.ExpiredSignature:
            return handle_error({'code': 'token_expired', 'description': 'token is expired'}, 401)
        except jwt.InvalidAudienceError:
            return handle_error({'code': 'invalid_audience', 'description': 'incorrect audience, expected: ' + client_id}, 401)
        except jwt.DecodeError:
            return handle_error({'code': 'token_invalid_signature', 'description': 'token signature is invalid'}, 401)
        except Exception:
            return handle_error({'code': 'invalid_header', 'description':'Unable to parse authentication token.'}, 400)

        _request_ctx_stack.top.current_user = user = payload
        return f(*args, **kwargs)

    return decorated


# Application Routes
# ------------------

@app.route('/')
def index():
    return render_template('index.htm.j2')

@app.route('/register')
def registration():
    return render_template('register.htm.j2',
        callback_url=auth_callback_url,
        auth_id=auth_id,
        auth_domain=auth_domain
    )

@app.route('/ping')
def ping():
    return "All good. You don't need to be authenticated to call this"

@app.route('/me')
@requires_auth
def me():
    return jsonify(me=_request_ctx_stack.top.current_user)

@app.route('/secured/ping')
@requires_auth
def securedPing():
    return "All good. You only get this message if you're authenticated"

@app.route('/callback', methods=['POST'])
def display_auth():
    token = request.form
    return jsonify(token=token)



