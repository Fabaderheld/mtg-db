import os
import requests
from sqlalchemy.exc import IntegrityError

from ..models import db, Card, Set, Color, card_color, card_set  # Adjust based on your project structure
from flask import current_app


def download_image(url, filename):
    if os.path.exists(filename):
        return True
    try:
        response = requests.get(url)
        response.raise_for_status()
        with open(filename, "wb") as f:
            f.write(response.content)
        return True
    except Exception as e:
        print(f"Failed to download image: {e}")
        return False

def save_card_to_db(card_json):

    card_id = card_json['id']
    image_url = card_json.get('image_uris', {}).get('normal')
    local_path = download_card_image(image_url, card_id)

    card = Card(
        id=card_id,
        name=card_json['name'],
        layout=card_json.get('layout'),
        mana_cost=card_json.get('mana_cost'),
        cmc=card_json.get('cmc'),
        type_line=card_json.get('type_line'),
        oracle_text=card_json.get('oracle_text'),
        power=card_json.get('power'),
        toughness=card_json.get('toughness'),
        loyalty=card_json.get('loyalty'),
        rarity=card_json.get('rarity'),
        collector_number=card_json.get('collector_number'),
        set_code=card_json.get('set'),
        lang=card_json.get('lang'),
        released_at=card_json.get('released_at'),
        scryfall_uri=card_json.get('scryfall_uri'),
        image_uri=local_path  # local image path
    )

    db.session.merge(card)
    db.session.commit()
