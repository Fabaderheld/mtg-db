from .cards import card_bp
from ..mtg.routes import mtg_bp
from ..lorcana.routes import lorcana_bp

def register_routes(app):
    app.register_blueprint(card_bp)
    app.register_blueprint(mtg_bp, url_prefix='/mtg')
    app.register_blueprint(lorcana_bp, url_prefix='/lorcana')
