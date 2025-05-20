import json
import logging
import os
import time
import requests
from flask import current_app

from ..models import (
    LorcanaCard,
    LorcanaSet,
    LorcanaType,
    LorcanaClassification,
    LorcanaIllustrator,
    db
)

def fetch_and_cache_lorcana_sets():
    try:
        logging.info("Fetching sets from Lorcast...")
        response = requests.get("https://api.lorcast.com/v0/sets")
        if response.status_code == 200:
            data = response.json()
            for set_data in data:
                existing_set = LorcanaSet.query.get(set_data.get("id"))
                if not existing_set:
                    logging.debug(f"Processing set: {set_data['name']}")

                    # Initialize local_icon_path (missing in original)
                    local_icon_path = None

                    new_set = LorcanaSet(
                        id=set_data.get("id"),
                        name=set_data.get("name"),
                        code=set_data.get("code"),
                        released_at=set_data.get("released_at"),
                        local_icon_path=local_icon_path
                    )
                    db.session.add(new_set)
                    db.session.flush()
            db.session.commit()
            logging.info(f"Fetched and cached Lorcana sets.")
        else:
            logging.error(f"Failed to fetch Lorcana sets: {response.status_code}")
    except Exception as e:
        logging.error(f"Error fetching Lorcana sets: {e}")
        db.session.rollback()

def download_lorcana_image(card_id, size='normal'):
    """
    Downloads a Lorcana card image using Lorcast's image URL format
    Sizes: small, normal, large
    """
    logging.debug(f"Downloading Lorcana image for card ID {card_id} with size {size}")
    try:
        # Construct the image URL based on Lorcast's format
        base_url = "https://cards.lorcast.io/card/digital"
        image_url = f"{base_url}/{size}/{card_id}.avif"

        # Create the save path
        filename = f"{card_id}_{size}.avif"
        save_dir = os.path.join(current_app.static_folder, current_app.config['LORCANA_UPLOAD_FOLDER'])
        os.makedirs(save_dir, exist_ok=True)
        save_path = os.path.join(save_dir, filename)

        if os.path.exists(save_path):
            logging.info(f"Lorcana image already exists at {save_path}, skipping download.")
            return f"{current_app.config['LORCANA_UPLOAD_FOLDER']}/{filename}"

        response = requests.get(image_url)
        if response.status_code == 200:
            with open(save_path, 'wb') as f:
                f.write(response.content)
            logging.info(f"Lorcana image downloaded and saved to {save_path}")
            return f"{image_url}"
        else:
            logging.error(f"Failed to download Lorcana image from {image_url}: {response.status_code}")
            return None
    except Exception as e:
        logging.error(f"Error downloading Lorcana image: {e}")
        return None

def fetch_and_cache_lorcana_cards(
    card_name=None,
    card_type=None,
    selected_ink=None,
    selected_sets=None,
    search_string=None,
    page=1,
    per_page=20
):
    try:
        # Build query parameters for Lorcast API
        params = {
            'page': page,
            'limit': per_page
        }

        if card_name:
            params['name'] = card_name
        if search_string:
            params['q'] = search_string
        if selected_ink:
            params['ink'] = selected_ink
        if selected_sets:
            params['set'] = selected_sets[0] if isinstance(selected_sets, list) else selected_sets
        logging.info(f"Lorcana Search Query: {params}, Page: {page}")

        # Query local database first
        db_query = LorcanaCard.query
        if card_name:
            db_query = db_query.filter(LorcanaCard.name.ilike(f"%{card_name}%"))
        if card_type:
            db_query = db_query.join(LorcanaCard.types).filter(LorcanaType.name == card_type)
        if selected_ink:
            db_query = db_query.filter(LorcanaCard.ink == selected_ink)
        if selected_sets:
            db_query = db_query.filter(LorcanaCard.set_id.in_(selected_sets))
        if search_string:
            db_query = db_query.filter(LorcanaCard.name.ilike(f"%{search_string}%"))

        # Apply pagination to database query
        paginated_cards = db_query.order_by(LorcanaCard.name).offset((page - 1) * per_page).limit(per_page).all()

        # If we have enough cards for this page, return them
        if len(paginated_cards) == per_page:
            return paginated_cards

        # If we need to fetch from Lorcast
        response = requests.get("https://api.lorcast.com/v0/cards/search", params=params)
        if response.status_code != 200:
            logging.warning(f"Lorcast fetch failed: {response.status_code}")
            return paginated_cards
        else:
            logging.info(f"Lorcast fetch successful: {response.status_code}")

        # Process the response
        data = response.json()
        cards = data.get("results", [])
        logging.info(f"Retrieved {len(cards)} cards from Lorcast")
        new_cards = []

        for card_data in cards:
            # Skip if card exists
            if LorcanaCard.query.get(card_data["id"]):
                logging.debug(f"Card {card_data['id']} already exists in the database, skipping.")
                continue
            else:
                logging.debug(f"Processing new card: {card_data['name']}")

            # Download images for different sizes
            image_paths = {
                'small': download_lorcana_image(card_data['id'], 'small'),
                'normal': download_lorcana_image(card_data['id'], 'normal'),
                'large': download_lorcana_image(card_data['id'], 'large')
            }

            # Process types
            types = []
            type_data = card_data.get("type", [])
            if isinstance(type_data, str):
                type_data = [type_data]
            for type_name in type_data:
                type_obj = LorcanaType.query.filter_by(name=type_name).first()
                if not type_obj:
                    type_obj = LorcanaType(name=type_name)
                    db.session.add(type_obj)
                types.append(type_obj)

            # Process classifications
            classifications = []
            class_data = card_data.get("classifications", []) or []
            if isinstance(class_data, str):
                class_data = [class_data]
            for class_name in class_data:
                class_obj = LorcanaClassification.query.filter_by(name=class_name).first()
                if not class_obj:
                    class_obj = LorcanaClassification(name=class_name)
                    db.session.add(class_obj)
                classifications.append(class_obj)

            # Process illustrators
            illustrators = []
            illust_data = card_data.get("illustrators", [])
            if isinstance(illust_data, str):
                illust_data = [illust_data]
            for illust_name in illust_data:
                illust_obj = LorcanaIllustrator.query.filter_by(name=illust_name).first()
                if not illust_obj:
                    illust_obj = LorcanaIllustrator(name=illust_name)
                    db.session.add(illust_obj)
                illustrators.append(illust_obj)

            # Create new card
            new_card = LorcanaCard(
                id=card_data["id"],
                name=card_data["name"],
                version=card_data.get("version"),
                layout=card_data.get("layout", "normal"),
                released_at=card_data.get("released_at"),
                cost=card_data.get("cost"),
                inkwell=card_data.get("inkwell", False),
                ink=card_data.get("ink"),
                text=card_data.get("text"),
                move_cost=card_data.get("move_cost"),
                strength=card_data.get("strength"),
                willpower=card_data.get("willpower"),
                lore=card_data.get("lore"),
                rarity=card_data.get("rarity"),
                collector_number=card_data.get("collector_number"),
                lang=card_data.get("lang"),
                flavor_text=card_data.get("flavor_text"),
                tcgplayer_id=card_data.get("tcgplayer_id"),
                set_id=card_data.get("set", {}).get("id"),
                image_uris_small=image_paths.get('small'),
                image_uris_normal=image_paths.get('normal'),
                image_uris_large=image_paths.get('large'),
                local_image_path=f"{current_app.config['LORCANA_IMAGE_PATH']}/{card_data['id']}_large.avif"
            )

            new_card.types = types
            new_card.classifications = classifications
            new_card.illustrators = illustrators

            db.session.add(new_card)
            new_cards.append(new_card)

        if new_cards:
            try:
                db.session.commit()
                logging.info(f"Added {len(new_cards)} new Lorcana cards to database")
            except Exception as e:
                logging.error(f"Error committing Lorcana cards to database: {e}")
                db.session.rollback()
                return paginated_cards

        # Query again with pagination to get the complete set
        final_cards = db_query.order_by(LorcanaCard.name).offset((page - 1) * per_page).limit(per_page).all()

        return final_cards or []

    except Exception as e:
        logging.error(f"Error in fetch_and_cache_lorcana_cards: {e}")
        db.session.rollback()
        return []

def lorcana_card_to_dict(card):
    """Convert a single Lorcana card to dictionary"""
    return {
        'id': card.id,
        'name': card.name,
        'version': card.version,
        'layout': card.layout,
        'released_at': card.released_at,
        'cost': card.cost,
        'inkwell': card.inkwell,
        'ink': card.ink,
        'text': card.text,
        'move_cost': card.move_cost,
        'strength': card.strength,
        'willpower': card.willpower,
        'lore': card.lore,
        'rarity': card.rarity,
        'collector_number': card.collector_number,
        'lang': card.lang,
        'flavor_text': card.flavor_text,
        'tcgplayer_id': card.tcgplayer_id,

        'image_uris': {
            'small': card.image_uris_small,
            'normal': card.image_uris_normal,
            'large': card.image_uris_large
        },

        'types': [type.name for type in card.types] if card.types else [],
        'classifications': [c.name for c in card.classifications] if card.classifications else [],
        'illustrators': [i.name for i in card.illustrators] if card.illustrators else [],

        'set': {
            'id': card.set.id,
            'code': card.set.code,
            'name': card.set.name,
            'released_at': card.set.released_at
        } if card.set else None
    }

def fetch_lorcana_versions(card):
    """Fetch other versions of a Lorcana card"""
    if not card.name:
        return []

    versions = fetch_and_cache_lorcana_cards(card_name=card.name)
    return [lorcana_card_to_dict(version) for version in versions if version.id != card.id]