from flask import Flask,current_app
from .models import db
from .routes import register_routes
from .utils.helpers import fetch_and_cache_sets
import logging
import re
import os
from markupsafe import Markup

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
    logging.debug(f"Creating upload folder at {app.config['UPLOAD_FOLDER']}")
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    logging.debug(f"Creating database folder at {os.path.dirname(app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', ''))}")
    os.makedirs(os.path.dirname(app.config['SQLALCHEMY_DATABASE_URI'].replace("sqlite:///", "")), exist_ok=True)

    # Initialize database with the Flask app
    db.init_app(app)

    # Register routes
    register_routes(app)

    # Create database tables within the app context
    with app.app_context():
        db.create_all()
        fetch_and_cache_sets()

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


    return app

app = create_app()
