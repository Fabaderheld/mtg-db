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

from ...models import MtgCard, MtgSet, db, MtgInventoryEntry, MtgDeckCard, MtgDeck
from ...utils.mtg_helpers import (
    download_mtg_image,
    fetch_and_cache_mtg_cards,
    fetch_and_cache_mtg_symbols,
    fetch_and_cache_reprints,
    find_card_for_import,
    parse_csv_content,
    import_moxfield_deck
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
@login_required
def inventory():
    page = request.args.get('page', 1, type=int)  # Get page number from request
    per_page = 20  # Number of items per page

    # Fetch paginated inventory data for the user
    pagination = MtgInventoryEntry.query.filter_by(user_id=current_user.id).paginate(
        page=page,
        per_page=per_page,
        error_out=False  # Return empty list if page is out of range
    )

    inventory_data = pagination.items  # Get the items for the current page

    # Check if it's an AJAX request (for infinite scrolling)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # Render only the inventory items template
        return render_template('mtg/partials/inventory_items.html', inventory=inventory_data)
    else:
        # Render the full inventory page
        return render_template('mtg/inventory.html', inventory=inventory_data, pagination=pagination)

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

@mtg_bp.route('/update_quantity/<int:entry_id>', methods=['POST'])
@login_required
def update_quantity(entry_id):
    entry = MtgInventoryEntry.query.get_or_404(entry_id)
    if entry.user_id != current_user.id:
        flash("You do not have permission to modify this entry.", "danger")
        return redirect(url_for('mtg.inventory'))

    try:
        quantity = int(request.form['quantity'])
        if quantity < 0:
            flash("Quantity must be a non-negative number.", "danger")
            return redirect(request.referrer or url_for('mtg.inventory'))
        entry.quantity = quantity
        db.session.commit()
        flash("Quantity updated successfully.", "success")
    except ValueError:
        flash("Invalid quantity.", "danger")
    return redirect(request.referrer or url_for('mtg.inventory'))

@mtg_bp.route('/delete_from_inventory/<int:entry_id>', methods=['POST'])
@login_required
def delete_from_inventory(entry_id):
    entry = MtgInventoryEntry.query.get_or_404(entry_id)
    if entry.user_id != current_user.id:
        flash("You do not have permission to delete this entry.", "danger")
        return redirect(url_for('mtg.inventory'))

    db.session.delete(entry)
    db.session.commit()
    flash("Card deleted from your inventory.", "success")
    return redirect(url_for('mtg.inventory'))

@mtg_bp.route('/search')
@login_required
def search():
    # Render a search form or redirect to your existing search route
    return render_template('mtg/search.html')  # Or redirect to your existing search route

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

@mtg_bp.route('/import', methods=['POST'])
def import_invetory():
    return render_template('mtg/import.html')

from ...models import MtgDeck  # Assuming you have a deck model

@mtg_bp.route('/decks/new', methods=['GET', 'POST'])
@login_required
def create_deck():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        # Add more fields as needed
        # Example: cards = request.form.getlist('cards')
        if not name:
            flash("Deck name is required.", "danger")
            return render_template('mtg/deck_form.html', mode='create')
        deck = MtgDeck(name=name, description=description, user_id=current_user.id)
        db.session.add(deck)
        db.session.commit()
        flash("Deck created successfully.", "success")
        return redirect(url_for('mtg.decks'))
    return render_template('mtg/deck_form.html', mode='create')

@mtg_bp.route('/decks/<int:deck_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_deck(deck_id):
    deck = MtgDeck.query.get_or_404(deck_id)
    if deck.user_id != current_user.id:
        flash("You do not have permission to edit this deck.", "danger")
        return redirect(url_for('mtg.decks'))
    if request.method == 'POST':
        deck.name = request.form.get('name')
        deck.description = request.form.get('description')
        # Update cards or other fields as needed
        db.session.commit()
        flash("Deck updated successfully.", "success")
        return redirect(url_for('mtg.decks'))
    return render_template('mtg/deck_form.html', deck=deck, mode='edit')

@mtg_bp.route('/decks/<int:deck_id>')
@login_required
def deck_detail(deck_id):
    deck = MtgDeck.query.get_or_404(deck_id)
    # Optionally, fetch cards in the deck, etc.
    return render_template('mtg/deck_detail.html', deck=deck)


@mtg_bp.route('/decks/import', methods=['GET', 'POST'])
@login_required
def import_deck():
    if request.method == 'POST':
        logging.info(f"User {current_user.id} started deck import process")

        pasted_data = request.form.get('import_deck')
        deck_name = request.form.get('deck_name', 'Imported Deck')
        deck_description = request.form.get('deck_description', '')
        uploaded_file = request.files.get('csv_file')

        logging.debug(f"Import parameters - Deck name: '{deck_name}', Description length: {len(deck_description)}")

        if not pasted_data and not uploaded_file:
            # If no data provided, log and flash a warning
            logging.warning(f"User {current_user.id} attempted deck import without providing deck data")
            flash("Please provide deck data.", "warning")
            return render_template('mtg/import_deck.html')

        try:
            logging.info(f"Parsing Moxfield deck data for user {current_user.id}")
            if pasted_data:
                # If pasted data is provided, parse it
                logging.debug("Parsing pasted deck data")
                result = import_moxfield_deck(pasted_data)

            if uploaded_file:
                # If a file is uploaded, read and parse it
                logging.debug(f"Reading uploaded file: {uploaded_file.filename}")
                deck_text = uploaded_file.read().decode('utf-8')
                result = import_moxfield_deck(deck_text)


            logging.info(f"Successfully parsed {result['unique_cards']} unique cards ({result['total_cards']} total)")

            # 1. Create the new deck
            logging.debug(f"Creating new deck '{deck_name}' for user {current_user.id}")
            new_deck = MtgDeck(
                user_id=current_user.id,
                name=deck_name,
                description=deck_description
            )
            db.session.add(new_deck)
            db.session.flush()  # Get new_deck.id
            logging.info(f"Created new deck with ID {new_deck.id}")

            # 2. Add cards to the deck
            added_count = 0
            skipped_count = 0

            logging.info(f"Processing {len(result['cards'])} card entries for deck {new_deck.id}")

            for card_data in result['cards']:
                logging.debug(f"Processing card: {card_data['name']} ({card_data['set_code']}) x{card_data['quantity']}")

                mtg_card = find_card_for_import(card_data['name'], card_data['set_code'])
                if mtg_card:
                    logging.debug(f"Found card {mtg_card.id} for '{card_data['name']}'")
                    deck_entry = MtgDeckCard(
                        deck_id=new_deck.id,
                        card_id=mtg_card.id,
                        quantity=card_data['quantity']
                    )
                    db.session.add(deck_entry)
                    added_count += card_data['quantity']
                else:
                    logging.warning(f"Card not found: '{card_data['name']}' from set '{card_data['set_code']}'")
                    flash(f"Card '{card_data['name']}' from set '{card_data['set_code']}' not found.", "warning")
                    skipped_count += 1

            # 3. Commit and redirect
            logging.info(f"Committing deck import - Added {added_count} cards, skipped {skipped_count} cards")
            db.session.commit()

            logging.info(f"Successfully imported deck '{new_deck.name}' (ID: {new_deck.id}) for user {current_user.id}")
            flash(f"Successfully imported deck '{new_deck.name}' with {added_count} cards.", "success")
            return redirect(url_for('mtg.deck_detail', deck_id=new_deck.id))

        except Exception as e:
            logging.error(f"Error importing deck for user {current_user.id}: {str(e)}", exc_info=True)
            db.session.rollback()
            flash(f"Error importing deck: {str(e)}", "danger")
            return render_template('mtg/import_deck.html')

    logging.debug(f"User {current_user.id} accessed deck import page (GET request)")
    return render_template('mtg/import_deck.html')