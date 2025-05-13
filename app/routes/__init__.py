from .cards import card_bp

def register_routes(app):
    app.register_blueprint(card_bp)
