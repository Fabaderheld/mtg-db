from .cards import card_bp
from .inventory import inventory_bp


def register_routes(app):
    app.register_blueprint(card_bp)
    app.register_blueprint(inventory_bp)
