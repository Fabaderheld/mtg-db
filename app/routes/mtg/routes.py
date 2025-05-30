# app/mtg/routes.py
import csv
import logging
from io import StringIO
from flask_login import login_required, current_user

from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for
)

from ...models import MtgCard, MtgSet, db, MtgInventoryEntry
from ...utils.mtg_helpers import (
    download_mtg_image,
    fetch_and_cache_mtg_cards,
    fetch_and_cache_mtg_mana_icons,
    fetch_mtg_reprints
)

mtg_bp = Blueprint("mtg", __name__, url_prefix="/mtg")

@mtg_bp.route("/", methods=["GET", "POST"])
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
        cards = fetch_and_cache_mtg_cards(search_string=query, page=page, per_page=per_page)

    # AJAX: return only the cards grid partial
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        if not cards:
            return '', 204
        return render_template("mtg/partials/card_grid.html", cards=cards)

    return render_template("mtg/index.html", cards=cards, error=error, query=query)


@mtg_bp.route("/sets", methods=["GET"])
def sets():
    sort = request.args.get('sort', 'name')  # Default sort by name
    direction = request.args.get('direction', 'asc')  # Default sort direction

    if sort == 'name':
        if direction == 'asc':
            sets = MtgSet.query.order_by(MtgSet.name.asc()).all()
        else:
            sets = MtgSet.query.order_by(MtgSet.name.desc()).all()
    elif sort == 'date':
        if direction == 'asc':
            sets = MtgSet.query.order_by(MtgSet.released_at.asc()).all()
        else:
            sets = MtgSet.query.order_by(MtgSet.released_at.desc()).all()
    else:
        sets = MtgSet.query.all()

    return render_template("mtg/sets.html", sets=sets)

@mtg_bp.route('/sets/<set_code>')
def set_detail(set_code):
    page = request.args.get('page', 1, type=int)
    selected_set = MtgSet.query.filter_by(code=set_code).first_or_404()
    cards = fetch_and_cache_mtg_cards(
        selected_sets=[set_code],
        page=page,
        per_page=20
    )

    logging.info(f"Cards found: {len(cards)}")

    # If AJAX, return only the cards grid partial
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        if not cards:
            return '', 204  # No Content
        return render_template('partials/card_grid.html', cards=cards)

    # Otherwise, render the full page
    return render_template(
        'mtg/set_detail.html',
        cards=cards,
        selected_set=selected_set
    )


@mtg_bp.route('/card/<card_id>')
def card_detail(card_id):
    card = MtgCard.query.get(card_id)
    if not card:
        return "Card not found", 404

    card_set = card.set if card.set else None
    mana_icons = fetch_and_cache_mtg_mana_icons()  # Fetch mana icons from Scryfall API
    reprints = fetch_mtg_reprints(card)  # Fetch reprints from Scryfall API
    logging.info(f"Reprints found: {reprints}")

    return render_template('mtg/card_detail.html', card=card, card_set=card_set, mana_icons=mana_icons, reprints=reprints)

@mtg_bp.route("/advanced_search", methods=["GET", "POST"])
def advanced_search():
    # Now this runs inside the app/request context
    sets = MtgSet.query.all()
    card_types = ["Creature", "Enchantment", "Instant", "Sorcery", "Artifact", "Land", "Planeswalker"]
    colors = ["White", "Blue", "Black", "Red", "Green"]
    mana_icons = fetch_and_cache_mtg_mana_icons()  # Fetch mana icons from Scryfall API


    error = None
    cards = []
    total_items = 0

    if request.method == "POST":
        card_name = request.form.get("cardName")
        card_type = request.form.get("cardType")
        selected_colors = request.form.getlist("colors")
        selected_sets = request.form.getlist("sets")
        unique_oracle_id = request.form.get("unique_oracle_id") == "1"

        try:
            cards = fetch_and_cache_mtg_cards(
                card_name=card_name,
                card_type=card_type,
                selected_colors=selected_colors,
                selected_sets=selected_sets,
                unique_oracle_id=unique_oracle_id
            )
            total_items = len(cards)
        except Exception as e:
            error = str(e)

    return render_template(
        "mtg/advanced_search.html",
        cards=cards,
        total_items=total_items,
        card_types=card_types,
        colors=colors,
        sets=sets,
        mana_icons=mana_icons,
        error=error
    )

@mtg_bp.route('/inventory')
def inventory():
    # TODO: Fetch MTG inventory data for the user
    inventory_data = MtgInventoryEntry.query.filter_by(user_id=current_user.id).all()
    return render_template('mtg/inventory.html', inventory=inventory_data)

@mtg_bp.route('/decks')
def decks():
    # TODO: Fetch MTG deck data for the user
    decks_data = []  # Replace with actual data
    return render_template('mtg/decks.html', decks=decks_data)

@mtg_bp.route('/add_to_inventory', methods=['POST'])
@login_required
def add_to_inventory():
    card_id = request.form.get('id')
    # You can add more fields if needed, but only card_id is required for inventory
    if not card_id:
        flash("No card ID provided.", "danger")
        return redirect(request.referrer or url_for('mtg.index'))

    # Check if the user already has this card in inventory
    entry = MtgInventoryEntry.query.filter_by(user_id=current_user.id, card_id=card_id).first()
    if entry:
        entry.quantity += 1
        flash("Added another copy to your inventory.", "success")
    else:
        entry = MtgInventoryEntry(user_id=current_user.id, card_id=card_id, quantity=1)
        db.session.add(entry)
        flash("Card added to your inventory.", "success")
    db.session.commit()
    return redirect(request.referrer or url_for('mtg.index'))