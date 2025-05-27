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

from ..models import MtgCard, MtgSet, db #, CardInventory
from ..utils.mtg_helpers import (
    download_mtg_image,
    fetch_and_cache_mtg_cards,
    fetch_and_cache_mtg_mana_icons,
    fetch_mtg_reprints
)

card_bp = Blueprint("cards", __name__)

card_bp = Blueprint("cards", __name__)
@card_bp.route("/landing", methods=["GET"])
def landing():
    return render_template("landing.html")

@card_bp.route("/", methods=["GET", "POST"])
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
        return render_template("partials/card_grid.html", cards=cards)

    return render_template("index.html", cards=cards, error=error, query=query)


@card_bp.route("/sets", methods=["GET"])
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

    return render_template("sets.html", sets=sets)

# @card_bp.route('/sets/<set_code>')
# def set_detail(set_code):
#     page = request.args.get('page', 1, type=int)
#     selected_set = MtgSet.query.filter_by(code=set_code).first_or_404()
#     cards = fetch_and_cache_mtg_cards(
#         selected_sets=[set_code],
#         page=page,
#         per_page=20
#     )

#     # If AJAX, return only the cards grid partial
#     if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
#         if not cards:
#             return '', 204  # No Content
#         return render_template('partials/card_grid.html', cards=cards)

#     # Otherwise, render the full page
#     return render_template(
#         'set_detail.html',
#         cards=cards,
#         selected_set=selected_set
#     )


@card_bp.route('/card/<card_id>')
def card_detail(card_id):
    card = MtgCard.query.get(card_id)
    if not card:
        return "Card not found", 404

    card_set = card.set if card.set else None
    mana_icons = fetch_and_cache_mtg_mana_icons()  # Fetch mana icons from Scryfall API
    reprints = fetch_mtg_reprints(card)  # Fetch reprints from Scryfall API
    logging.info(f"Reprints found: {reprints}")

    return render_template('card_detail.html', card=card, card_set=card_set, mana_icons=mana_icons, reprints=reprints)

# @card_bp.route("/advanced_search", methods=["GET", "POST"])
# def advanced_search():
#     # Now this runs inside the app/request context
#     sets = MtgSet.query.all()
#     card_types = ["Creature", "Enchantment", "Instant", "Sorcery", "Artifact", "Land", "Planeswalker"]
#     colors = ["White", "Blue", "Black", "Red", "Green"]
#     mana_icons = fetch_and_cache_mtg_mana_icons()  # Fetch mana icons from Scryfall API


#     error = None
#     cards = []
#     total_items = 0

#     if request.method == "POST":
#         card_name = request.form.get("cardName")
#         card_type = request.form.get("cardType")
#         selected_colors = request.form.getlist("colors")
#         selected_sets = request.form.getlist("sets")
#         unique_oracle_id = request.form.get("unique_oracle_id") == "1"

#         try:
#             cards = fetch_and_cache_mtg_cards(
#                 card_name=card_name,
#                 card_type=card_type,
#                 selected_colors=selected_colors,
#                 selected_sets=selected_sets,
#                 unique_oracle_id=unique_oracle_id
#             )
#             total_items = len(cards)
#         except Exception as e:
#             error = str(e)

#     return render_template(
#         "advanced_search.html",
#         cards=cards,
#         total_items=total_items,
#         card_types=card_types,
#         colors=colors,
#         sets=sets,
#         mana_icons=mana_icons,
#         error=error
#     )

# @card_bp.route('/inventory/import_csv', methods=['GET', 'POST'])
# def import_csv():
#     if request.method == 'POST':
#         file = request.files.get('csv_file')
#         if not file:
#             flash('No file uploaded', 'danger')
#             return redirect(request.url)
#         try:
#             stream = StringIO(file.stream.read().decode('utf-8'))
#             reader = csv.DictReader(stream)
#             imported = 0
#             for row in reader:
#                 name = row['Name']
#                 edition = row['Edition']
#                 condition = row['Condition']
#                 language = row['Language']
#                 foil = row['Foil'].strip().lower() in ['yes', 'true', '1']
#                 count = int(row['Count'])
#                 purchase_price = float(row['Purchase Price']) if row['Purchase Price'] else 0.0
#                 collector_number = row['Collector Number']

#                 # Find the card by name, set, and collector number
#                 card = MtgCard.query.filter_by(
#                     name=name,
#                     collector_number=collector_number
#                 ).join(Card.set).filter(MtgSet.name == edition).first()

#                 if card:
#                     inv = CardInventory.query.filter_by(
#                         card_id=card.id,
#                         condition=condition,
#                         is_foil=foil
#                     ).first()
#                     if inv:
#                         inv.quantity += count
#                         inv.purchase_price = purchase_price
#                     else:
#                         inv = CardInventory(
#                             card_id=card.id,
#                             quantity=count,
#                             condition=condition,
#                             is_foil=foil,
#                             purchase_price=purchase_price,
#                             # add other fields as needed
#                         )
#                         db.session.add(inv)
#                     imported += count
#                 else:
#                     flash(f'Card not found: {name} ({edition}) #{collector_number}', 'warning')
#             db.session.commit()
#             flash(f'Imported {imported} cards.', 'success')
#             return redirect(url_for('cards.index'))
#         except Exception as e:
#             flash(f'Error: {e}', 'danger')
#             return redirect(request.url)
#     return render_template('inventory/import-csv.html')