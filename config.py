import os

class Config:
    SQLALCHEMY_DATABASE_URI = "sqlite:///instance/mtg.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    IMAGE_PATH = os.path.join("static", "images")
