from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required
from werkzeug.security import check_password_hash, generate_password_hash
from ..models import db, User
import logging

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    game = request.args.get('game', 'mtg')  # Default to MTG if no game is specified
    template = f'auth/login_{game}.html'  # Use a game-specific template

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash("Logged in successfully.", "success")
            logging.debug(f"User {username} logged in successfully.")

            next_url = request.args.get('next')
            if next_url:
                return redirect(next_url)
            return redirect(url_for(f'{game}.index'))  # Redirect to the game's index page
        else:
            flash("Invalid username or password.", "danger")
            logging.debug(f"Failed login attempt for user {username}.")

    return render_template(template, game=game)  # Pass the game to the template

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Logged out successfully.", "info")
    return redirect(url_for('mtg.index'))

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    game = request.args.get('game', 'mtg')  # Default to MTG if no game is specified
    template = f'auth/register_{game}.html'  # Use a game-specific template

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # Check if the username is already taken
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            logging.debug(f"Registration attempt with existing username: {username}")
            flash("Username already exists. Please choose a different one.", "danger")
            return render_template(template, game=game)

        try:
            # Create a new user
            new_user = User(username=username, password=password)
            db.session.add(new_user)
            db.session.commit()

            # Verify the user was added
            check_user = User.query.filter_by(username=username).first()
            if check_user:
                logging.debug(f"New user registered and verified in DB: {username}")
            else:
                logging.error(f"User {username} was not found in DB after commit!")

            flash("Registration successful! Please log in.", "success")
            logging.debug(f"User {username} registered successfully with password hash: {password}")
            logging.debug(f"Password entered: {password}")

            return redirect(url_for('auth.login', game=game))  # Pass the game to the login route
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error registering user {username}: {str(e)}")
            flash("An error occurred during registration. Please try again.", "danger")
            return render_template(template, game=game)

    return render_template(template, game=game)  # Pass the game to the template