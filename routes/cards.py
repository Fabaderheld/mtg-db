from flask import Blueprint, request, jsonify, render_template
from ..models import Card, Set
from ..utils.helpers import download_image
from ..models import db

card_bp = Blueprint("cards", __name__)

@card_bp.route("/", methods=["GET", "POST"])
def index():
    cards = []
    error = None

    if request.method == "POST":
        query = request.form.get("query")
        if query:
            cards = fetch_and_cache_cards(search_string=query)

    return render_template("index.html", cards=cards, error=error)


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

@card_bp.route("/set/<set_code>")
def set_detail(set_code):
    logging.info("⚙️ fetch_and_cache_cards triggered")
    cards = fetch_and_cache_cards(selected_sets=[set_code])
    selected_set = Set.query.filter_by(code=set_code).first()

    return render_template("set_detail.html", selected_set=selected_set, cards=cards)


@card_bp.route('/card/<card_id>')
def card_detail(card_id):
    # Fetch the card details from the database
    card = Card.query.get(card_id)
    if not card:
        return "Card not found", 404

    # Fetch the set details for the card
    card_sets = card.sets
    set_details = [s.code for s in card.sets]

    # Render the card details template
    return render_template('card_detail.html', card=card , set_details=set_details)

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