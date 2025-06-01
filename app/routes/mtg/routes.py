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
    fetch_and_cache_mtg_symbols,
    fetch_and_cache_reprints,
    find_card_for_import,
    parse_csv_content
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
    cards = fetch_and_cache_mtg_cards(card_id=card_id)
    if not cards:
        # Redirect to a custom "Card Not Found" page
        return redirect(url_for('mtg.card_not_found', card_id=card_id))
    card = cards[0]  # Extract the card from the list

    card_set = card.set if card.set else None
    mana_icons = fetch_and_cache_mtg_symbols()  # Fetch mana icons from Scryfall API
    reprints = fetch_and_cache_reprints(card)  # Fetch reprints from Scryfall API
    logging.info(f"Reprints found: {reprints}")

    return render_template('mtg/card_detail.html', card=card, card_set=card_set, mana_icons=mana_icons, reprints=reprints)

@mtg_bp.route('/card_not_found/<card_id>')
def card_not_found(card_id):
    # Render a custom "Card Not Found" template
    return render_template('mtg/card_not_found.html', card_id=card_id)

@mtg_bp.route("/advanced_search", methods=["GET", "POST"])
def advanced_search():
    # Now this runs inside the app/request context
    sets = MtgSet.query.all()
    card_types = ["Creature", "Enchantment", "Instant", "Sorcery", "Artifact", "Land", "Planeswalker"]
    colors = ["White", "Blue", "Black", "Red", "Green"]
    mana_icons = fetch_and_cache_mtg_symbols()  # Fetch mana icons from Scryfall API


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

@mtg_bp.route('/import', methods=['GET', 'POST'])
@login_required
def import_inventory():
    if request.method == 'POST':
        pasted_data = request.form.get('import_inventory')
        uploaded_file = request.files.get('csv_file')

        if pasted_data and uploaded_file and uploaded_file.filename:
            flash("Please provide data either by pasting or uploading a file, not both.", "warning")
            return render_template('mtg/import.html')

        cards = []
        if pasted_data:
            try:
                cards = parse_csv_content(pasted_data)
            except ValueError as e:
                flash(f"Error parsing pasted data: {e}", "danger")
                return render_template('mtg/import.html')
        elif uploaded_file and uploaded_file.filename:
            if uploaded_file.filename.endswith('.csv'):
                try:
                    file_content = uploaded_file.read().decode('utf-8')
                    cards = parse_csv_content(file_content)
                except ValueError as e:
                    flash(f"Error parsing uploaded file: {e}", "danger")
                    return render_template('mtg/import.html')
            else:
                flash("Please upload a valid CSV file.", "danger")
                return render_template('mtg/import.html')
        else:
            flash("Please provide data either by pasting or uploading a file.", "warning")
            return render_template('mtg/import.html')

        # Now process the cards: fetch from API if needed, then add to inventory
        added_count = 0
        skipped_count = 0

        for card_data in cards:
            # Use your existing function to search for the card
            mtg_card = find_card_for_import(card_data['name'], card_data['edition'])

            # Check if we found a matching card
            if mtg_card:
                # Add to inventory or update quantity
                entry = MtgInventoryEntry.query.filter_by(
                    user_id=current_user.id,
                    card_id=mtg_card.id
                ).first()

                if entry:
                    entry.quantity += card_data['count']
                else:
                    entry = MtgInventoryEntry(
                        user_id=current_user.id,
                        card_id=mtg_card.id,
                        quantity=card_data['count']
                    )
                    db.session.add(entry)

                added_count += card_data['count']
            else:
                flash(f"Card '{card_data['name']}' from edition '{card_data['edition']}' not found.", "warning")
                skipped_count += 1

        db.session.commit()
        flash(f"Successfully imported {added_count} cards into your inventory. {skipped_count} cards were skipped.", "success")
        return render_template('mtg/import.html')

    return render_template('mtg/import.html')
