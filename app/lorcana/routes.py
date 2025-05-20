# app/lorcana/routes.py
import csv
import logging
from io import StringIO

from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for
)

from ..models import LorcanaCard, LorcanaSet, db
from ..utils.lorcana_helpers import (
    download_lorcana_image,
    fetch_and_cache_lorcana_cards,
    #fetch_and_cache_lorcana_mana_icons,
    #fetch_lorcana_reprints
)


lorcana_bp = Blueprint("lorcana", __name__, url_prefix="/lorcana")

@lorcana_bp.route("/")
def index():
    cards = []
    error = None
    page = request.args.get("page", 1, type=int)
    per_page = 20

    query = None
    if request.method == "POST":
        query = request.form.get("query")
    elif request.method == "GET":
        query = request.args.get("query")

    if query:
        cards = fetch_and_cache_lorcana_cards(search_string=query, page=page, per_page=per_page)

    # AJAX: return only the cards grid partial
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        if not cards:
            return '', 204
        return render_template("lorcana/partials/card_grid.html", cards=cards)

    return render_template("lorcana/index.html", cards=cards, error=error, query=query)


@lorcana_bp.route("/sets", methods=["GET"])
def sets():
    sort = request.args.get('sort', 'name')


@lorcana_bp.route("/advanced_search", methods=["GET", "POST"])
def advanced_search():
    if request.method == "POST":
        card_name = request.form.get("card_name")
        card_type = request.form.get("card_type")
        selected_ink = request.form.getlist("selected_ink")
        selected_sets = request.form.getlist("selected_sets")
        search_string = request.form.get("search_string")
        page = request.form.get("page", 1, type=int)
        per_page = 20

        cards = fetch_and_cache_lorcana_cards(
            card_name=card_name,
            card_type=card_type,
            selected_ink=selected_ink,
            selected_sets=selected_sets,
            search_string=search_string,
            page=page,
            per_page=per_page
        )

@lorcana_bp.route('/card/<card_id>')
def card_detail(card_id):
    card = LorcanaCard.query.get(card_id)
    if not card:
        return "Card not found", 404

    card_set = card.set if card.set else None
    # mana_icons = fetch_and_cache__mana_icons()  # Fetch mana icons from Scryfall API
    # reprints = fetch_mtg_reprints(card)  # Fetch reprints from Scryfall API
    # logging.info(f"Reprints found: {reprints}")

    return render_template('mtg/card_detail.html', card=card, card_set=card_set, mana_icons="", reprints="null")