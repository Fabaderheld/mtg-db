# app/lorcana/routes.py
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

from ...models import LorcanaCard, LorcanaSet, db, LorcanaInventoryEntry
from ...utils.lorcana_helpers import (
    download_lorcana_image,
    fetch_and_cache_lorcana_cards,
    #fetch_and_cache_lorcana_mana_icons,
    #fetch_lorcana_reprints
    find_card_for_import,
    parse_csv_content
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
    # reprints = fetch_and_cache_reprints(card)  # Fetch reprints from Scryfall API
    # logging.info(f"Reprints found: {reprints}")
    rendered_html = render_template('lorcana/card_detail.html', card=card, card_set=card_set)
    logging.debug(rendered_html)
    return rendered_html

@lorcana_bp.route('/sets/<set_code>')
def set_detail(set_code):
    page = request.args.get('page', 1, type=int)
    selected_set = LorcanaSet.query.filter_by(code=set_code).first_or_404()
    cards = fetch_and_cache_lorcana_cards(
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
        'lorcana/set_detail.html',
        cards=cards,
        selected_set=selected_set
    )

@lorcana_bp.route('/inventory')
@login_required
def inventory():
    page = request.args.get('page', 1, type=int)  # Get page number from request
    per_page = 20  # Number of items per page

    # Fetch paginated inventory data for the user
    pagination = LorcanaInventoryEntry.query.filter_by(user_id=current_user.id).paginate(
        page=page,
        per_page=per_page,
        error_out=False  # Return empty list if page is out of range
    )

    inventory_data = pagination.items  # Get the items for the current page

    # Check if it's an AJAX request (for infinite scrolling)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # Render only the inventory items template
        return render_template('lorcana/partials/inventory_items.html', inventory=inventory_data)
    else:
        # Render the full inventory page
        return render_template('lorcana/inventory.html', inventory=inventory_data, pagination=pagination)

@lorcana_bp.route('/decks')
@login_required
def decks():
    # TODO: Fetch MTG deck data for the user
    decks_data = []  # Replace with actual data
    return render_template('lorcana/decks.html', decks=decks_data)

@lorcana_bp.route('/import', methods=['GET', 'POST'])
@login_required
def import_inventory():
    if request.method == 'POST':
        pasted_data = request.form.get('import_inventory')
        uploaded_file = request.files.get('csv_file')

        if pasted_data and uploaded_file and uploaded_file.filename:
            flash("Please provide data either by pasting or uploading a file, not both.", "warning")
            return render_template('lorcana/import.html')

        cards = []
        if pasted_data:
            try:
                cards = parse_csv_content(pasted_data)
            except ValueError as e:
                flash(f"Error parsing pasted data: {e}", "danger")
                return render_template('lorcana/import.html')
        elif uploaded_file and uploaded_file.filename:
            if uploaded_file.filename.endswith('.csv'):
                try:
                    file_content = uploaded_file.read().decode('utf-8')
                    cards = parse_csv_content(file_content)
                except ValueError as e:
                    flash(f"Error parsing uploaded file: {e}", "danger")
                    return render_template('lorcana/import.html')
            else:
                flash("Please upload a valid CSV file.", "danger")
                return render_template('lorcana/import.html')
        else:
            flash("Please provide data either by pasting or uploading a file.", "warning")
            return render_template('lorcana/import.html')

        # Now process the cards: fetch from API if needed, then add to inventory
        added_count = 0
        skipped_count = 0

        for card_data in cards:
            # Use your existing function to search for the card
            mtg_card = find_card_for_import(card_data['name'], card_data['edition'])

            # Check if we found a matching card
            if mtg_card:
                # Add to inventory or update quantity
                entry = LorcanaInventoryEntry.query.filter_by(
                    user_id=current_user.id,
                    card_id=mtg_card.id
                ).first()

                if entry:
                    entry.quantity += card_data['count']
                else:
                    entry = LorcanaInventoryEntry(
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
        return render_template('lorcana/import.html')

    return render_template('lorcana/import.html')

@lorcana_bp.route('/update_quantity/<int:entry_id>', methods=['POST'])
@login_required
def update_quantity(entry_id):
    entry = LorcanaInventoryEntry.query.get_or_404(entry_id)
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

@lorcana_bp.route('/delete_from_inventory/<int:entry_id>', methods=['POST'])
@login_required
def delete_from_inventory(entry_id):
    entry = LorcanaInventoryEntry.query.get_or_404(entry_id)
    if entry.user_id != current_user.id:
        flash("You do not have permission to delete this entry.", "danger")
        return redirect(url_for('mtg.inventory'))

    db.session.delete(entry)
    db.session.commit()
    flash("Card deleted from your inventory.", "success")
    return redirect(url_for('mtg.inventory'))

@lorcana_bp.route('/search')
@login_required
def search():
    # Render a search form or redirect to your existing search route
    return render_template('mtg/search.html')  # Or redirect to your existing search route

@lorcana_bp.route('/add_to_inventory', methods=['POST'])
@login_required
def add_to_inventory():
    card_id = request.form.get('id')
    # You can add more fields if needed, but only card_id is required for inventory
    if not card_id:
        flash("No card ID provided.", "danger")
        return redirect(request.referrer or url_for('mtg.index'))

    # Check if the user already has this card in inventory
    entry = LorcanaInventoryEntry.query.filter_by(user_id=current_user.id, card_id=card_id).first()
    if entry:
        entry.quantity += 1
        flash("Added another copy to your inventory.", "success")
    else:
        entry = LorcanaInventoryEntry(user_id=current_user.id, card_id=card_id, quantity=1)
        db.session.add(entry)
        flash("Card added to your inventory.", "success")
    db.session.commit()
    return redirect(request.referrer or url_for('mtg.index'))

@lorcana_bp.route('/import', methods=['POST'])
def import_invetory():
    return render_template('mtg/import.html')