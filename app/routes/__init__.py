#from ._cards import card_bp
from ..mtg.routes import mtg_bp
from ..lorcana.routes import lorcana_bp
from flask import render_template

def register_routes(app):
    #app.register_blueprint(card_bp)
    app.register_blueprint(mtg_bp, url_prefix='/mtg')
    app.register_blueprint(lorcana_bp, url_prefix='/lorcana')

# Register the landing page route directly on the app
    @app.route('/')
    def landing():
        return render_template('landing.html')
