from flask import Flask
from .models import db
from .routes import register_routes
from .utils.helpers import fetch_and_cache_sets
import logging
import re
import os


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

    return app

app = create_app()
