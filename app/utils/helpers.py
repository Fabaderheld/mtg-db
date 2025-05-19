import json
import logging
import os
import time

import requests
from flask import current_app

from ..models import (
    Card,
    Color,
    Set,
    card_colors,
    card_sets,
    db
)

def fetch_and_cache_sets():
    try:
        logging.info("Fetching sets from Scryfall...")
        response = requests.get("https://api.scryfall.com/sets")
        if response.status_code == 200:
            data = response.json()
            sets = data.get("data", [])
            for set_data in sets:
                existing_set = Set.query.get(set_data.get("id"))
                if not existing_set:
                    logging.debug(f"Processing set: {set_data['name']}")
                    icon_url = set_data.get("icon_svg_uri")
                    local_icon_path = None
                    if icon_url:
                        # Save to static/sets_icons/{set_code}.svg
                        filename = f"{set_data.get('code')}.svg"
                        save_dir = os.path.join(current_app.static_folder, "sets_icons")
                        os.makedirs(save_dir, exist_ok=True)
                        save_path = os.path.join(save_dir, filename)
                        # Download the image
                        try:
                            img_response = requests.get(icon_url)
                            if img_response.status_code == 200:
                                with open(save_path, "wb") as f:
                                    f.write(img_response.content)
                                # Store the relative path for HTML rendering
                                local_icon_path = f"sets_icons/{filename}"
                                time.sleep(0.05)  # 50ms delay
                        except Exception as img_e:
                            logging.error(f"Failed to download icon for set {set_data.get('code')}: {img_e}")

                    new_set = Set(
                        id=set_data.get("id"),
                        name=set_data.get("name"),
                        code=set_data.get("code"),
                        icon_url=icon_url,
                        local_icon_path=local_icon_path,  # <-- Add this field to your model!
                        released_at=set_data.get("released_at")
                    )
                    db.session.add(new_set)
                    db.session.flush()
            db.session.commit()
            logging.info(f"Fetched and cached {len(sets)} sets.")
        else:
            logging.error(f"Failed to fetch sets: {response.status_code}")
    except Exception as e:
        logging.error(f"Error fetching sets: {e}")
        db.session.rollback()

def download_image(url, filename):
    logging.debug(f"Downloading image from {url} to {filename}")
    if os.path.exists(filename):
        logging.info(f"Image already exists at {filename}, skipping download.")
        return True

    try:
        response = requests.get(url)
        if response.status_code == 200:
            with open(filename, 'wb') as f:
                f.write(response.content)
            logging.info(f"Image downloaded and saved to {filename}")
            return True
        else:
            logging.error(f"Failed to download image from {url}")
            return False
    except Exception as e:
        logging.error(f"Error downloading image: {e}")
        return False

def fetch_and_cache_cards(
    card_name=None,
    card_type=None,
    selected_colors=None,
    selected_sets=None,
    search_string=None,
    unique_cards=False,
    page=1,          # Add page parameter
    per_page=20      # Add per_page parameter
):
    try:
        # Build query parts (same as before)
        query_parts = []
        if card_name:
            query_parts.append(f'!"{card_name}"')
        if card_type:
            query_parts.append(f't:{card_type}')
        if selected_colors:
            query_parts.append(" ".join([f'c:{color}' for color in selected_colors]))
        if selected_sets:
            query_parts.append(" ".join([f's:{set_code}' for set_code in selected_sets]))
        if search_string:
            query_parts.append(f'"{search_string}"')
        if unique_cards:
            query_parts.append("unique:prints")

        query = " ".join(query_parts)
        logging.info(f"Search Query: {query}, Page: {page}")

        # Build the base database query
        db_query = Card.query
        if card_name:
            db_query = db_query.filter(Card.name == card_name)
        if card_type:
            db_query = db_query.filter(Card.type_line.ilike(f"%{card_type}%"))
        if selected_colors:
            db_query = db_query.join(card_colors).join(Color).filter(Color.name.in_(selected_colors))
        if selected_sets:
            db_query = db_query.filter(Card.set.has(Set.code.in_(selected_sets)))
        if search_string:
            db_query = db_query.filter(Card.name.ilike(f"%{search_string}%"))

        # Handle unique cards
        if unique_cards:
            subquery = db_query.with_entities(
                Card.oracle_id,
                db.func.min(Card.id).label('min_id')
            ).group_by(Card.oracle_id).subquery()
            db_query = Card.query.join(subquery, Card.id == subquery.c.min_id)

        # Apply pagination to database query
        paginated_cards = db_query.order_by(Card.name).offset((page - 1) * per_page).limit(per_page).all()

        # If we have enough cards for this page, return them
        if len(paginated_cards) == per_page:
            return paginated_cards

        # If we need to fetch from Scryfall
        url = f"https://api.scryfall.com/cards/search"
        params = {
            'q': query or 'set:default',
            'page': page
        }

        response = requests.get(url, params=params)
        if response.status_code != 200:
            logging.warning(f"Scryfall fetch failed: {response.status_code}")
            return paginated_cards

        data = response.json()
        new_cards = []

        for card_data in data.get("data", []):
            # Skip if card exists
            if Card.query.get(card_data["id"]):
                continue

            # Process image
            image_url = card_data.get("image_uris", {}).get("normal")
            local_image_path = None
            if image_url:
                filename = f"{card_data['id']}.jpg"
                save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)

                if download_image(image_url, save_path):
                    local_image_path = os.path.join(
                        current_app.config['IMAGE_PATH'],
                        filename
                    )

            # Process colors
            colors = []
            for color_name in card_data.get("colors", []):
                color = Color.query.filter_by(name=color_name).first()
                if not color:
                    color_id = f"color_{color_name}"
                    color = Color(id=color_id, name=color_name)
                    db.session.add(color)
                colors.append(color)

            # Get or create set
            card_set = None
            if 'set' in card_data:
                card_set = Set.query.filter_by(code=card_data['set']).first()

            # Create new card
            new_card = Card(
                id=card_data["id"],
                oracle_id=card_data.get("oracle_id"),
                name=card_data["name"],
                type_line=card_data.get("type_line"),
                mana_costs=card_data.get("mana_cost"),
                oracle_text=card_data.get("oracle_text"),
                power=card_data.get("power"),
                toughness=card_data.get("toughness"),
                rarity=card_data.get("rarity"),
                image_uri=image_url,
                local_image_path=local_image_path,
                legalities=json.dumps(card_data.get("legalities", {}))
            )

            new_card.colors = colors
            if card_set:
                new_card.set = card_set

            db.session.add(new_card)
            new_cards.append(new_card)

        if new_cards:
            try:
                db.session.commit()
            except Exception as e:
                logging.error(f"Error committing to database: {e}")
                db.session.rollback()
                return paginated_cards

        # Query again with pagination to get the complete set
        final_cards = db_query.order_by(Card.name).offset((page - 1) * per_page).limit(per_page).all()

        # If no cards found for this page, return empty list to signal end of results
        if not final_cards:
            return []

        return final_cards

    except Exception as e:
        logging.error(f"Error in fetch_and_cache_cards: {e}")
        db.session.rollback()
        return []

def fetch_and_cache_mana_icons():
    response = requests.get("https://api.scryfall.com/symbology")
    mana_icons = {}
    if response.status_code == 200:
        data = response.json()
        os.makedirs("static/mana", exist_ok=True)
        for symbol in data.get("data", []):
            symbol_code = symbol["symbol"]  # e.g. "{R}", "{2}"
            svg_url = symbol["svg_uri"]
            # Clean the symbol for filename, e.g. {R} -> R, {2} -> 2, {W/U} -> WU, etc.
            filename = symbol_code.replace("{", "").replace("}", "").replace("/", "").replace(" ", "") + ".svg"
            local_path = os.path.join("static", "mana", filename)
            # Download and cache if not already present
            if not os.path.exists(local_path):
                img_response = requests.get(svg_url)
                if img_response.status_code == 200:
                    with open(local_path, "wb") as f:
                        f.write(img_response.content)
                    time.sleep(0.05)  # 50ms delay
            # Store the relative path for use in templates
            mana_icons[symbol_code] = f"mana/{filename}"
    return mana_icons

def card_to_dict(card):
    """Convert a single card to dictionary"""
    return {
        # Basic attributes
        'id': card.id,
        'oracle_id': card.oracle_id,
        'name': card.name,
        'layout': card.layout,
        'mana_cost': card.mana_cost,
        'cmc': card.cmc,
        'type_line': card.type_line,
        'oracle_text': card.oracle_text,
        'power': card.power,
        'toughness': card.toughness,
        'loyalty': card.loyalty,
        'rarity': card.rarity,
        'collector_number': card.collector_number,
        'set_code': card.set_code,
        'lang': card.lang,
        'released_at': card.released_at,
        'mana_costs': card.mana_costs,
        'image_uri': card.image_uri,
        'local_image_path': card.local_image_path,
        'scryfall_uri': card.scryfall_uri,
        'rulings_uri': card.rulings_uri,
        'legalities': card.legalities,
        'prints_search_uri': card.prints_search_uri,

        # Relationships
        'colors': [color.name for color in card.colors] if card.colors else [],
        'types': [type.name for type in card.types] if card.types else [],

        # Set relationship
        'set': {
            'id': card.set.id,
            'code': card.set.code,
            'name': card.set.name,
            'icon_url': card.set.icon_url,
            'local_icon_path': card.set.local_icon_path,
            'released_at': card.set.released_at,
            'set_type': card.set.set_type
        } if card.set else None
    }

def fetch_reprints(card):
    """Fetch reprints and convert them to dictionaries"""
    if not card.oracle_id:
        return []

    reprints = fetch_and_cache_cards(card_name=card.name, unique_cards=False)
    # Convert each reprint to a dictionary
    return [card_to_dict(reprint) for reprint in reprints]