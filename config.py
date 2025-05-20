import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    DB_PATH = os.path.join(BASE_DIR, 'data', 'cards.db')  # go up from app/ if config is in app/
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{DB_PATH}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # This is the folder where images are stored for web access
    MTG_UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "mtg_images")
    MTG_IMAGE_PATH = os.path.join("static", "mtg_images")
    LORCANA_UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "lorcana_images")
    LORCANA_IMAGE_PATH = os.path.join("static", "lorcana_images")
