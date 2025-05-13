import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    DB_PATH = os.path.join(BASE_DIR, 'data', 'cards.db')  # go up from app/ if config is in app/
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{DB_PATH}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # This is the folder where images are stored for web access
    IMAGE_PATH = os.path.join("static", "images")  # Relative for HTML
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "images")  # Absolute for saving files
