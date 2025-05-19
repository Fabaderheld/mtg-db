# app/lorcana/routes.py
from flask import Blueprint, render_template

lorcana_bp = Blueprint("lorcana", __name__, url_prefix="/lorcana")

@lorcana_bp.route("/")
def index():
    return render_template("lorcana/index.html")