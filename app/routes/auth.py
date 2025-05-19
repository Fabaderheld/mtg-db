from flask import Blueprint
from flask_login import login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from ..models import User, db
from ..utils.common import flash, redirect, render_template, request, url_for

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # login logic here
    pass

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    # registration logic here
    pass

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.index'))