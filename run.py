from flask import Flask, render_template, url_for, Blueprint, jsonify, redirect, make_response, request, session
from flask_jwt_extended import JWTManager, fresh_jwt_required, jwt_required, create_access_token, get_jwt_identity, jwt_refresh_token_required, create_refresh_token, set_access_cookies, set_refresh_cookies, unset_jwt_cookies
from werkzeug.security import check_password_hash, generate_password_hash, safe_str_cmp
from werkzeug.utils import secure_filename
import click
import functools
import sys, os
import config
from modules.auth import User, authenticate
from modules.database import db
from bson import json_util
import json
import bcrypt
from functools import wraps

app = Flask(__name__, static_folder='./static/build')
app.config['SECRET_KEY'] = b'dev'
app.config['JWT_SECRET_KEY'] = b'dev'
app.config['JWT_TOKEN_LOCATION'] = ['cookies']

# Set the cookie paths, so that you are only sending your access token
# cookie to the access endpoints, and only sending your refresh token
# to the refresh endpoint. Technically this is optional, but it is in
# your best interest to not send additional cookies in the request if
# they aren't needed.
app.config['JWT_ACCESS_COOKIE_PATH'] = '/api/'
app.config['JWT_REFRESH_COOKIE_PATH'] = '/api/token-refresh/'
app.config['JWT_CSRF_IN_COOKIES'] = True

app.config['JWT_REFRESH_CSRF_HEADER_NAME'] = 'X-CSRF-REFRESH-TOKEN'

# Disable CSRF protection for this example. In almost every case,
# this is a bad idea. See examples/csrf_protection_with_cookies.py
# for how safely store JWTs in cookies
# app.config['JWT_COOKIE_CSRF_PROTECT'] = False
jwt = JWTManager(app)


@click.command()
@click.option('--mode', '-m', default='development', help='Production mode (production, development)', required=True)
def run(mode):
    if (mode == 'development'):
        app.config.from_object('config.DevelopmentConfig')
    elif (mode == 'production'):
        app.config.from_object('config.ProductionConfig')
    else:
        click.echo("Please use either development or production mode.")
        sys.exit()
    app.run(host='0.0.0.0')

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if (request.method == 'GET'):
            try:
                if not session['username']:
                    return redirect(url_for('login', redirect=request.path), 401)
            except KeyError:
                return redirect(url_for('login', redirect=request.path), 401)
            return f(*args, **kwargs)
    return decorated_function

@app.before_request
def start_session():
    try:
        assert session['username']
    except (AssertionError, KeyError):
        session['username'] = ""
    session.permanent = True

@app.route('/')
@login_required
def index():
    return "coming soon"
    # return render_template('jacksite/home.j2', page_title="Home", module_data=page_data['Home'])

@app.route('/<page>/')
def subpage(page):
    return "coming soon"
    # page_list = []
    # for page in db.pages.find():
    #     page_list.append(page["name"])
    #
    # if page in page_list:
    #     if page == 'home':
    #         return redirect(url_for('index'))
    #     else:
    #         return render_template('site/home.j2', page_title=page, module_data=page_list[page])
    # else:
    #     return render_template('404.j2'), 404


@app.route('/login/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        permanent_session = request.form['remember']
        request_path = request.form['redirect']
        if request_path == 'None':
            request_path = 'admin'
        storedHash = db.users.find_one({'username': username}, {'hash': 1, "_id": 0})['hash']

        if (bcrypt.checkpw(password.encode(), storedHash.encode())):
            if (permanent_session):
                session.clear()
                session['username'] = username

            access_token = create_access_token(identity=username, fresh=True)
            refresh_token = create_refresh_token(identity=username)

            response = redirect(request_path) if request_path else redirect(url_for('admin_root'))
            set_access_cookies(response, access_token)
            set_refresh_cookies(response, refresh_token)
            return response, 200
        else:
            return redirect(url_for('login'))

    return render_template('admin/login.j2')

@app.route('/logout/')
def logout():
    # remove the username from the session if it's there
    session.pop('username', None)
    return redirect(url_for('index'))

@app.route('/admin/')
@login_required
def admin_root():
    return render_template('admin/admin.j2')

@app.route('/admin/<page>/')
@login_required
def admin_sub(page=None):
    return render_template('admin/admin.j2')


@app.route('/api/token-refresh/', methods=['POST'])
@jwt_refresh_token_required
def refresh():
    current_user = get_jwt_identity()
    print(current_user)
    print("-------------------")
    new_token = create_access_token(identity=current_user, fresh=False) # True or False?
    ret = {'access_token': new_token}
    return jsonify(ret), 200


# API
@app.route('/api/<action>/<endpoint>/', methods=['POST'])
@fresh_jwt_required
def response(action, endpoint):
    if (endpoint == 'siteData'):
        site_data = {}

        if (action == 'update'):
            requestData = json.loads(request.get_data(as_text=True))
            _form = requestData['dbForm']
            _name = requestData['dbName']
            _data = requestData['dbData']
            db.siteData.update_one(
                {'name': _form},
                {
                    "$set": {
                        "data." + _name: _data,
                    }
                }
            )
        elif (action == 'upload'):
            _form = request.form['dbForm']
            _name = request.form['dbName']

            f = request.files['dbData']
            f.save(os.getcwd() + '/tmp/' + secure_filename(f.filename))

            db.siteData.update_one(
                {'name': _form},
                {
                    "$set": {
                        "data." + _name: secure_filename(f.filename),
                    }
                }
            )

        for doc in db.siteData.find():
            site_data[doc["name"]] = (json.loads(json_util.dumps(doc)));

        robot_text = ""
        with app.open_resource('robots.txt') as f:
            robot_text = f.read()

        site_data["seo"]["data"]["robots"] = robot_text.decode()
        return jsonify(site_data);
    elif (endpoint == 'page-list'):
        page_list = []

        for page in db.pages.find():
            page_list.append(page["name"])
        return jsonify(page_list)
    elif (endpoint == 'robots'):
        response = ""
        robots = f.open('robots.txt')
        for line in robots:
            response += line + '\n'
        return jsonify(response)
    else:
        return jsonify("No endpoint requested")

if __name__ == '__main__':
    run()
