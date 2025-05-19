import csv
from ..utils.common import CardInventory, db
from ..utils.helpers import download_image, fetch_and_cache_mtg_cards

def add_card_to_inventory(card_id, set_code, quantity, foil, condition, language):
    card_inventory = CardInventory(
        card_id=card_id,
        set_code=set_code,
        quantity=quantity,
        foil=foil,
        condition=condition,
        language=language
    )
    db.session.add(card_inventory)
    db.session.commit()

def import_cards_from_csv(file_path):
    with open(file_path, 'r') as file:
        reader = csv.reader(file)
        for row in reader:
            db_card = fetch_and_cache_mtg_cards(search_string=row[0], selected_sets=row[1], page=1, per_page=1)
            if db_card:
                card = db_card[0]
                card_inventory = CardInventory(
                    card_id=card.id,
                    set_code=row[1],
                    quantity=row[2],
                    foil=row[3],
                    condition=row[4],
                    language=row[5]
                )
                db.session.add(card_inventory)
