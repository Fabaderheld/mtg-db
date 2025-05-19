from flask import Blueprint
from sqlalchemy import and_

from ..utils.common import (
    MtgCard,
    CardInventory,
    Inventory,
    current_user,
    db,
    flash,
    login_required,
    redirect,
    render_template,
    request,
    url_for
)

inventory_bp = Blueprint('inventory', __name__, url_prefix='/inventory')

@inventory_bp.route('/')
@login_required
def list_inventories():
    """List all inventories for the current user"""
    inventories = Inventory.query.filter_by(user_id=current_user.id).all()
    return render_template('inventory/list_inventories.html', inventories=inventories)

@inventory_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_inventory():
    """Create a new inventory"""
    if request.method == 'POST':
        name = request.form.get('name')
        if not name:
            flash('Inventory name is required', 'error')
            return redirect(url_for('inventory.create_inventory'))

        inventory = Inventory(
            name=name,
            user_id=current_user.id
        )
        db.session.add(inventory)
        db.session.commit()
        flash(f'Inventory "{name}" created successfully', 'success')
        return redirect(url_for('inventory.list_inventories'))

    return render_template('inventory/create_inventory.html')

@inventory_bp.route('/<int:inventory_id>')
@login_required
def view_inventory(inventory_id):
    """View cards in a specific inventory"""
    inventory = Inventory.query.filter_by(
        id=inventory_id,
        user_id=current_user.id
    ).first_or_404()

    cards = CardInventory.query.filter_by(inventory_id=inventory_id).all()
    return render_template(
        'inventory/view_inventory.html',
        inventory=inventory,
        cards=cards
    )

@inventory_bp.route('/<int:inventory_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_inventory(inventory_id):
    """Edit inventory details"""
    inventory = Inventory.query.filter_by(
        id=inventory_id,
        user_id=current_user.id
    ).first_or_404()

    if request.method == 'POST':
        name = request.form.get('name')
        if name:
            inventory.name = name
            db.session.commit()
            flash('Inventory updated successfully', 'success')
            return redirect(url_for('inventory.view_inventory', inventory_id=inventory_id))

    return render_template('inventory/edit_inventory.html', inventory=inventory)

@inventory_bp.route('/<int:inventory_id>/delete', methods=['POST'])
@login_required
def delete_inventory(inventory_id):
    """Delete an inventory and all its cards"""
    inventory = Inventory.query.filter_by(
        id=inventory_id,
        user_id=current_user.id
    ).first_or_404()

    db.session.delete(inventory)  # This will cascade delete all CardInventory entries
    db.session.commit()
    flash('Inventory deleted successfully', 'success')
    return redirect(url_for('inventory.list_inventories'))

@inventory_bp.route('/<int:inventory_id>/add_card', methods=['GET', 'POST'])
@login_required
def add_card(inventory_id):
    """Add a card to an inventory"""
    inventory = Inventory.query.filter_by(
        id=inventory_id,
        user_id=current_user.id
    ).first_or_404()

    if request.method == 'POST':
        card_name = request.form.get('card_name')
        set_name = request.form.get('set_name')
        quantity = int(request.form.get('quantity', 1))
        condition = request.form.get('condition', 'NM')
        is_foil = bool(request.form.get('is_foil'))
        purchase_price = float(request.form.get('purchase_price', 0))

        # Find the card in the database
        card = Card.query.join(Card.set).filter(
            and_(
                Card.name == card_name,
                Set.name == set_name
            )
        ).first()

        if card:
            # Check if card already exists in inventory
            existing_entry = CardInventory.query.filter_by(
                inventory_id=inventory_id,
                card_id=card.id,
                condition=condition,
                is_foil=is_foil
            ).first()

            if existing_entry:
                existing_entry.quantity += quantity
            else:
                new_entry = CardInventory(
                    inventory_id=inventory_id,
                    card_id=card.id,
                    quantity=quantity,
                    condition=condition,
                    is_foil=is_foil,
                    purchase_price=purchase_price
                )
                db.session.add(new_entry)

            db.session.commit()
            flash(f'Added {quantity}x {card_name} to inventory', 'success')
            return redirect(url_for('inventory.view_inventory', inventory_id=inventory_id))
        else:
            flash(f'Card not found: {card_name}', 'error')

    return render_template('inventory/add_card.html', inventory=inventory)

@inventory_bp.route('/<int:inventory_id>/card/<int:card_inventory_id>/edit',
                   methods=['GET', 'POST'])
@login_required
def edit_card(inventory_id, card_inventory_id):
    """Edit a card entry in an inventory"""
    inventory = Inventory.query.filter_by(
        id=inventory_id,
        user_id=current_user.id
    ).first_or_404()

    card_entry = CardInventory.query.filter_by(
        id=card_inventory_id,
        inventory_id=inventory_id
    ).first_or_404()

    if request.method == 'POST':
        card_entry.quantity = int(request.form.get('quantity', 1))
        card_entry.condition = request.form.get('condition')
        card_entry.is_foil = bool(request.form.get('is_foil'))
        card_entry.purchase_price = float(request.form.get('purchase_price', 0))

        db.session.commit()
        flash('Card updated successfully', 'success')
        return redirect(url_for('inventory.view_inventory', inventory_id=inventory_id))

    return render_template(
        'inventory/edit_card.html',
        inventory=inventory,
        card_entry=card_entry
    )

@inventory_bp.route('/<int:inventory_id>/card/<int:card_inventory_id>/delete',
                   methods=['POST'])
@login_required
def delete_card(inventory_id, card_inventory_id):
    """Remove a card from an inventory"""
    inventory = Inventory.query.filter_by(
        id=inventory_id,
        user_id=current_user.id
    ).first_or_404()

    card_entry = CardInventory.query.filter_by(
        id=card_inventory_id,
        inventory_id=inventory_id
    ).first_or_404()

    db.session.delete(card_entry)
    db.session.commit()
    flash('Card removed from inventory', 'success')
    return redirect(url_for('inventory.view_inventory', inventory_id=inventory_id))

@inventory_bp.route('/<int:inventory_id>/import_csv', methods=['GET', 'POST'])
@login_required
def import_csv(inventory_id):
    """Import cards from CSV into a specific inventory"""
    inventory = Inventory.query.filter_by(
        id=inventory_id,
        user_id=current_user.id
    ).first_or_404()

    if request.method == 'POST':
        if 'csv_file' not in request.files:
            flash('No file uploaded', 'error')
            return redirect(request.url)

        file = request.files['csv_file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(request.url)

        try:
            stream = StringIO(file.stream.read().decode('utf-8'))
            reader = csv.DictReader(stream)

            cards_added = 0
            cards_failed = 0

            for row in reader:
                try:
                    # Process each row and add to inventory
                    card_name = row['Name']
                    set_name = row['Edition']
                    quantity = int(row['Count'])
                    condition = row['Condition']
                    is_foil = row['Foil'].lower() == 'true'
                    purchase_price = float(row['Purchase Price']) if row['Purchase Price'] else 0

                    card = Card.query.join(Card.set).filter(
                        and_(
                            Card.name == card_name,
                            Set.name == set_name
                        )
                    ).first()

                    if card:
                        existing_entry = CardInventory.query.filter_by(
                            inventory_id=inventory_id,
                            card_id=card.id,
                            condition=condition,
                            is_foil=is_foil
                        ).first()

                        if existing_entry:
                            existing_entry.quantity += quantity
                        else:
                            new_entry = CardInventory(
                                inventory_id=inventory_id,
                                card_id=card.id,
                                quantity=quantity,
                                condition=condition,
                                is_foil=is_foil,
                                purchase_price=purchase_price
                            )
                            db.session.add(new_entry)

                        cards_added += 1
                    else:
                        cards_failed += 1
                        flash(f"Card not found: {card_name} ({set_name})", "warning")

                except Exception as e:
                    cards_failed += 1
                    flash(f"Error processing {card_name}: {str(e)}", "error")

            db.session.commit()
            flash(f"Import complete: {cards_added} cards added, {cards_failed} failed", "info")
            return redirect(url_for('inventory.view_inventory', inventory_id=inventory_id))

        except Exception as e:
            flash(f"Error processing CSV file: {str(e)}", "error")
            return redirect(request.url)

    return render_template('inventory/import_csv.html', inventory=inventory)