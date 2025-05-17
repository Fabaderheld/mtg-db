from flask import Blueprint, request, jsonify, render_template
from ..models import Card, Set
from ..utils.helpers import download_image,fetch_and_cache_cards, fetch_and_cache_mana_icons, fetch_reprints
from ..models import db
import logging



card_bp = Blueprint("cards", __name__)

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
        cards = fetch_and_cache_cards(search_string=query, page=page, per_page=per_page)

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
            sets = Set.query.order_by(Set.name.asc()).all()
        else:
            sets = Set.query.order_by(Set.name.desc()).all()
    elif sort == 'date':
        if direction == 'asc':
            sets = Set.query.order_by(Set.released_at.asc()).all()
        else:
            sets = Set.query.order_by(Set.released_at.desc()).all()
    else:
        sets = Set.query.all()

    return render_template("sets.html", sets=sets)

@card_bp.route('/sets/<set_code>')
def set_detail(set_code):
    page = request.args.get('page', 1, type=int)
    selected_set = Set.query.filter_by(code=set_code).first_or_404()
    cards = fetch_and_cache_cards(
        selected_sets=[set_code],
        page=page,
        per_page=20
    )

    # If AJAX, return only the cards grid partial
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        if not cards:
            return '', 204  # No Content
        return render_template('partials/card_grid.html', cards=cards)

    # Otherwise, render the full page
    return render_template(
        'set_detail.html',
        cards=cards,
        selected_set=selected_set
    )


@card_bp.route('/card/<card_id>')
def card_detail(card_id):
    card = Card.query.get(card_id)
    if not card:
        return "Card not found", 404

    card_set = card.set if card.set else None
    mana_icons = fetch_and_cache_mana_icons()  # Fetch mana icons from Scryfall API
    reprints = fetch_reprints(card)  # Fetch reprints from Scryfall API
    logging.info(f"Reprints found: {reprints}")

    return render_template('card_detail.html', card=card, card_set=card_set, mana_icons=mana_icons, reprints=reprints)

@card_bp.route("/advanced_search", methods=["GET", "POST"])
def advanced_search():
    # Now this runs inside the app/request context
    sets = Set.query.all()
    card_types = ["Creature", "Enchantment", "Instant", "Sorcery", "Artifact", "Land", "Planeswalker"]
    colors = ["White", "Blue", "Black", "Red", "Green"]
    mana_icons = fetch_and_cache_mana_icons()  # Fetch mana icons from Scryfall API


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
            cards = fetch_and_cache_cards(
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
        "advanced_search.html",
        cards=cards,
        total_items=total_items,
        card_types=card_types,
        colors=colors,
        sets=sets,
        mana_icons=mana_icons,
        error=error
    )

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        fetch_and_cache_sets()

        # Check if the import file exists at startup
        import_file_path = "import/import.json"  # Update this path to the location of your bulk data file
        if os.path.exists(import_file_path):
            logging.info("Found import.json file, staring import")
            # import_bulk_data_from_file(import_file_path)

    app.run(debug=True)