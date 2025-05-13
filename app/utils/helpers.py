import os
import requests
import time
import json
import logging

from ..models import db, Card, Set, Color, card_colors, card_sets
from flask import current_app

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
                    # Check if the set is already in the database
                    new_set = Set(
                        id=set_data.get("id"),
                        name=set_data.get("name"),
                        code=set_data.get("code"),
                        icon_url=set_data.get("icon_svg_uri"),
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

def fetch_and_cache_cards(card_name=None, card_type=None, selected_colors=None, selected_sets=None, search_string=None):
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

    query = " ".join(query_parts)
    logging.info(f"Search Query: {query}")

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

    existing_cards = db_query.all()
    logging.info(f"Found {len(existing_cards)} matching cards in DB.")

    if existing_cards:

        # filter out cards with the same oracle_id


        return existing_cards

    logging.info("No matching cards in DB. Fetching from Scryfall...")
    fetched_cards = []
    has_more = True
    page = 1

    try:
        while has_more:
            url = f"https://api.scryfall.com/cards/search?q={query}&page={page}"
            logging.info(f"Fetching page {page}: {url}")
            response = requests.get(url)
            time.sleep(0.05)

            if response.status_code != 200:
                logging.warning(f"Scryfall fetch failed: {response.status_code}")
                break

            data = response.json()
            cards_data = data.get("data", [])
            fetched_cards.extend(cards_data)
            has_more = data.get("has_more", False)
            page += 1

        for card_data in fetched_cards:
            logging.debug(f"Processing card: {card_data['name']}")
            existing_card = Card.query.get(card_data["id"])
            if existing_card:
                continue

            image_url = card_data.get("image_uris", {}).get("normal")
            local_image_path = None
            if image_url:
                filename = f"{card_data['id']}.jpg"
                save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)

                if download_image(image_url, save_path):
                    # Store the relative path for HTML rendering
                    local_image_path = os.path.join(current_app.config['IMAGE_PATH'], filename)

            color_names = card_data.get("colors", [])
            colors = []
            for color_name in color_names:
                color = Color.query.filter_by(name=color_name).first()
                if not color:
                    color_id = f"color_{color_name}"
                    color = Color(id=color_id, name=color_name)
                    db.session.add(color)
                    db.session.flush()
                colors.append(color)

            new_set = Set.query.filter_by(code=card_data.get("set")).first()

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
                #raw=json.dumps(card_data),
                image_uri=card_data.get("image_uris", {}).get("normal"),
                local_image_path=local_image_path,
                legalities=json.dumps(card_data.get("legalities", {}))
            )

            new_card.colors = colors
            if new_set:
                new_card.set = new_set

            db.session.add(new_card)

        db.session.commit()

        return db_query.all()
    except Exception as e:
        logging.error(f"Error fetching cards: {e}")
        db.session.rollback()
        return []
