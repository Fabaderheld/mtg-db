import logging
import os
import re
import secrets
from flask import Flask, render_template, jsonify, request, session, current_app
from flask_login import LoginManager
from markupsafe import Markup
from flask import Flask
from .mtg.routes import mtg_bp
from .lorcana.routes import lorcana_bp

from .models import db,User
from .routes import register_routes
from .utils.mtg_helpers import fetch_and_cache_mtg_sets
from .utils.lorcana_helpers import fetch_and_cache_lorcana_sets

def configure_logging(app):
    """Configure logging for the app."""
    logging.basicConfig(
        level=logging.DEBUG,  # Log level
        format='%(asctime)s - %(levelname)s - %(message)s',  # Log format
        handlers=[
            logging.StreamHandler()  # Use StreamHandler to output logs to the console
        ]
    )

    # Custom filter to strip ANSI escape codes
    class StripColorFilter(logging.Filter):
        def filter(self, record):
            ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')
            record.msg = ansi_escape.sub('', record.msg)
            return True

    # Add the custom filter to the root logger
    logging.getLogger().addFilter(StripColorFilter())

# For importing the app instance in other modules

def create_app():
    # Initialize Flask application
    app = Flask(__name__,
        template_folder='../templates',
        static_folder='../static')

    # Load configuration from config.py
    app.config.from_object("config.Config")

    # Configure logging
    configure_logging(app)

    # Ensure folders exist
    logging.info("Creating necessary directories...")
    logging.debug(f"Creating MTG upload folder at {app.config['MTG_UPLOAD_FOLDER']}")
    os.makedirs(app.config['MTG_UPLOAD_FOLDER'], exist_ok=True)
    logging.debug(f"Creating Lorcana upload folder at {app.config['LORCANA_UPLOAD_FOLDER']}")
    os.makedirs(app.config['LORCANA_UPLOAD_FOLDER'], exist_ok=True)

    logging.debug(f"Creating database folder at {os.path.dirname(app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', ''))}")
    os.makedirs(os.path.dirname(app.config['SQLALCHEMY_DATABASE_URI'].replace("sqlite:///", "")), exist_ok=True)

    # Initialize database with the Flask app
    db.init_app(app)

    # Register routes
    register_routes(app)

    # Create database tables within the app context
    with app.app_context():
        db.create_all()
        fetch_and_cache_mtg_sets()
        fetch_and_cache_lorcana_sets()

    @app.template_filter('mana_icons')
    def mana_icons_filter(mana_cost, mana_icons):
        import re
        symbols = re.findall(r'\{.*?\}', mana_cost or "")
        html = ""
        for symbol in symbols:
            icon_path = mana_icons.get(symbol)
            if icon_path:
                # Use current_app.url_for to generate the URL
                icon_url = current_app.url_for('static', filename=icon_path)
                html += f'<img src="{icon_url}" alt="{symbol}" style="width:20px; height:20px; vertical-align:middle;">'
            else:
                html += symbol
        return Markup(html)

    @app.template_filter('oracle_icons')
    def oracle_icons_filter(text, mana_icons):
        # Find all symbols like {1}, {R}, {T}, etc.
        symbols = re.findall(r'\{.*?\}', text or "")
        html = text or ""
        for symbol in set(symbols):  # Use set to avoid replacing the same symbol multiple times
            icon_path = mana_icons.get(symbol)
            if icon_path:
                icon_url = current_app.url_for('static', filename=icon_path)
                img_tag = f'<img src="{icon_url}" alt="{symbol}" style="width:20px; height:20px; vertical-align:middle;">'
                html = html.replace(symbol, img_tag)
        return Markup(html)

    @app.template_filter('lorcana_icons')
    def lorcana_icons_filter(text):
        logging.debug(f"Filtering text: {text}")
        # Define the mapping of symbols to icon paths
        lorcana_icons = {
            '{I}': 'images/lorcana/ink-cost.svg',
            '{E}': 'images/lorcana/tap.svg',
            '{S}': 'images/lorcana/strength.svg',
            '{L}': 'images/lorcana/lore.svg'
        }

        # Find all symbols like {I}, {E}, {S}, {L}
        symbols = re.findall(r'\{[IESL]\}', text or "")
        html = text or ""

        for symbol in set(symbols):  # Use set to avoid replacing the same symbol multiple times
            icon_path = lorcana_icons.get(symbol)
            if icon_path:
                icon_url = current_app.url_for('static', filename=icon_path)
                img_tag = f'<img src="{icon_url}" alt="{symbol}" class="lorcana-icon" style="width:20px; height:20px; vertical-align:middle;">'
                html = html.replace(symbol, img_tag)

        return Markup(html)


    return app

app = create_app()
