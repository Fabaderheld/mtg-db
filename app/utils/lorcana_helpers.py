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

from ..utils import shared_state

import cv2
import numpy as np
import pytesseract
from rapidfuzz import process, fuzz
import threading
import logging

# Global variables for thread safety
output_frame = None
card_info = None
lock = threading.Lock()

def get_card_names_from_db():
    """
    Get all card names from the database for fuzzy matching.
    """
    from app.models import LorcanaCard  # Import here to avoid circular imports

    try:
        # Query all card names from the database
        card_names = [card.name for card in LorcanaCard.query.with_entities(LorcanaCard.name).distinct()]
        return card_names
    except Exception as e:
        logging.error(f"Error getting card names from database: {e}")
        return []


def detect_card(frame, debug=True, min_area=10000, canny_low=30, canny_high=100, epsilon=0.15):
    """
    Detects a card in the frame and returns a perspective-corrected image.
    Optimized for cards with rounded corners.
    """
    from app.utils import shared_state

    # Create a copy for debugging visualization
    debug_frame = frame.copy() if debug else None

    # Convert to grayscale
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Apply morphological operations to enhance corners
    kernel = np.ones((5,5), np.uint8)
    dilated = cv2.dilate(gray, kernel, iterations=1)
    eroded = cv2.erode(dilated, kernel, iterations=1)

    # Apply Gaussian blur to reduce noise
    blurred = cv2.GaussianBlur(eroded, (5, 5), 0)

    # Edge detection with adjusted thresholds
    edges = cv2.Canny(blurred, canny_low, canny_high)

    # Find contours
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    min_area = 10000  # Adjust as needed for your image size
    contours = [c for c in contours if cv2.contourArea(c) > min_area]
    print(f"Found {len(contours)} contours")

    # Draw all contours on debug frame
    if debug:
        cv2.drawContours(debug_frame, contours, -1, (0, 255, 0), 1)

    # Sort contours by area (largest first)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)

    # Try both approaches: quadrilateral detection and aspect ratio
    for i, contour in enumerate(contours[:10]):
        peri = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, epsilon * peri, True) # Try 0.15 or higher
        area = cv2.contourArea(approx)
        print(f"Contour {i+1}: vertices={len(approx)}, area={area}")

        if debug:
            for pt in approx:
                cv2.circle(debug_frame, tuple(pt[0]), 5, (0, 255, 255), -1)

        if len(approx) == 4 and area > shared_state.area_threshold:
            # ... (rest unchanged)
            x, y, w, h = cv2.boundingRect(contour)
            aspect_ratio = float(w) / h
            print(f"Bounding rect aspect_ratio={aspect_ratio}, area={cv2.contourArea(contour)}")

            # Process the quadrilateral...
            pts = approx.reshape(4, 2)
            # Sort points...
            pts = pts[np.argsort(pts[:, 1])]
            top = pts[:2][np.argsort(pts[:2, 0])]
            bottom = pts[2:][np.argsort(pts[2:, 0])]
            pts = np.vstack([top, bottom[::-1]])

            # Perspective transform...
            w, h = 421, 588
            dst_pts = np.array([[0, 0], [w, 0], [w, h], [0, h]], dtype=np.float32)
            M = cv2.getPerspectiveTransform(pts.astype(np.float32), dst_pts)
            warped = cv2.warpPerspective(frame, M, (w, h))

            return warped, pts, None, debug_frame

        # APPROACH 2: Check aspect ratio if not a quadrilateral
        x, y, w, h = cv2.boundingRect(contour)
        aspect_ratio = float(w) / h

        # Lorcana cards have aspect ratio around 0.71
        if 0.60 <= aspect_ratio <= 0.80 and cv2.contourArea(contour) > shared_state.area_threshold:
            print(f"Found a card-like contour: aspect_ratio={aspect_ratio}, area={cv2.contourArea(contour)}")

            # Create a rectangle for the card
            rect = np.array([[x, y], [x+w, y], [x+w, y+h], [x, y+h]], dtype=np.int32)

            if debug:
                cv2.drawContours(debug_frame, [rect], -1, (0, 0, 255), 3)

            # Perspective transform using the rectangle
            pts = rect.reshape(4, 2)
            w_card, h_card = 421, 588
            dst_pts = np.array([[0, 0], [w_card, 0], [w_card, h_card], [0, h_card]], dtype=np.float32)
            M = cv2.getPerspectiveTransform(pts.astype(np.float32), dst_pts)
            warped = cv2.warpPerspective(frame, M, (w_card, h_card))

            return warped, pts, None, debug_frame
        else:
            # Draw this contour in blue on debug frame
            if debug:
                cv2.drawContours(debug_frame, [approx], -1, (255, 0, 0), 2)

    # If we get here, no card was detected
    print("No card detected")
    return None, None, None, debug_frame

def extract_name(card_img, card_names):
    """
    Extract the card name using OCR and fuzzy matching.
    """
    # Define the region of interest for the card name
    # These coordinates need to be adjusted for Lorcana cards
    y_start, y_end = 30, 80
    x_start, x_end = 40, 380

    # Crop the name region
    name_region = card_img[y_start:y_end, x_start:x_end]

    # Convert to grayscale
    gray = cv2.cvtColor(name_region, cv2.COLOR_BGR2GRAY)

    # Apply thresholding to improve OCR
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)

    # Use Tesseract to extract text
    text = pytesseract.image_to_string(thresh, config='--psm 7 -l eng')

    # Clean up the text
    text = text.strip()

    # Fuzzy match against known card names
    if text:
        best_match, score, _ = process.extractOne(text, card_names, scorer=fuzz.WRatio)
        if score > 60:  # Adjust threshold as needed
            return best_match

    return None

def lookup_card_in_db(name):
    """
    Look up a card by name in the database.
    """
    from app.models import LorcanaCard  # Import here to avoid circular imports
    from app.routes.lorcana import fetch_and_cache_lorcana_cards  # Import your existing function

    try:
        # Try to find the card in the database first
        card = LorcanaCard.query.filter(LorcanaCard.name == name).first()

        # If not found, try to fetch it from the API
        if not card:
            cards = fetch_and_cache_lorcana_cards(card_name=name, per_page=1)
            if cards:
                card = cards[0]

        if card:
            # Convert the card object to a dictionary
            return {
                'id': card.id,
                'name': card.name,
                'set': card.set_id,
                'type': ', '.join([t.name for t in card.types]) if hasattr(card, 'types') else None,
                'rarity': card.rarity,
                'text': card.text,
                'ink': card.ink,
                'cost': card.cost,
                'strength': card.strength,
                'willpower': card.willpower,
                'image_url': card.image_uris_normal or card.local_image_path
            }
    except Exception as e:
        logging.error(f"Error looking up card in database: {e}")

    return None

def get_debug_info():
    """
    Returns the current debug info.
    """
    global debug_info, lock

    with lock:
        return debug_info

def process_frame(frame, card_names):
    """
    Process a frame to detect and recognize a Lorcana card.
    Returns the processed frame, card info, extracted text, and debug info.
    """
    # Import shared state
    from app.utils import shared_state

    # Check if edge visualization is enabled
    if shared_state.show_edges:
        display_frame = visualize_edges(frame)
        return display_frame, None, None, {'card_detected': False}

    # Make a copy of the frame for drawing
    display_frame = frame.copy()

    # Detect card in the frame
    card_img, corners, _, debug_frame = detect_card(frame)

    debug_info = {
        'card_detected': False,
        'extracted_text': None,
        'card_found_in_db': False
    }

    # Use the debug frame as the display frame
    display_frame = debug_frame

    if card_img is not None:
        debug_info['card_detected'] = True
        # Draw the contour of the detected card
        if corners is not None:
            cv2.drawContours(display_frame, [corners.astype(np.int32)], -1, (0, 255, 0), 2)

        # Extract the card name
        extracted_text = extract_name(card_img, card_names)

        if extracted_text:
            debug_info['extracted_text'] = extracted_text
            # Look up the card in the database
            card_info = lookup_card_in_db(extracted_text)

            if card_info:
                debug_info['card_found_in_db'] = True
                # Display the card name on the frame
                cv2.putText(display_frame, f"Card: {extracted_text}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

                # Display a small version of the warped card
                h, w = display_frame.shape[:2]
                small_card = cv2.resize(card_img, (w//4, h//4))
                display_frame[0:small_card.shape[0], 0:small_card.shape[1]] = small_card

                return display_frame, card_info, extracted_text, debug_info
            else:
                debug_info['card_found_in_db'] = False
                # Display the extracted text on the frame
                cv2.putText(display_frame, f"Text: {extracted_text} (Not found in DB)", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                return display_frame, None, extracted_text, debug_info
        else:
            # Display a message on the frame
            cv2.putText(display_frame, "Card detected, but text extraction failed", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            return display_frame, None, None, debug_info
    else:
        # Display a message on the frame
        cv2.putText(display_frame, "No card detected", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        return display_frame, None, None, debug_info

# Global variables for thread safety
output_frame = None
card_info = None
extracted_text = None
debug_info = None
lock = threading.Lock()

def get_extracted_text():
    """
    Returns the current extracted text.
    """
    global extracted_text, lock

    with lock:
        return extracted_text

def get_frame():
    """
    Returns the current processed frame as a JPEG byte array.
    """
    global output_frame, lock

    with lock:
        if output_frame is None:
            return None

        # Encode the frame as JPEG
        (flag, encodedImage) = cv2.imencode(".jpg", output_frame)

        if not flag:
            return None

        return bytearray(encodedImage)

def get_card_info():
    """
    Returns the current card info.
    """
    global card_info, lock

    with lock:
        return card_info

def visualize_edges(frame):
    """
    Visualizes the edge detection process.
    Returns a frame with the edges highlighted.
    """
    # Convert to grayscale
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Apply Gaussian blur to reduce noise
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)

    # Edge detection
    edges = cv2.Canny(blurred, 30, 100)

    # Convert edges to BGR for visualization
    edges_bgr = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)

    # Create a side-by-side visualization
    h, w = frame.shape[:2]
    vis_frame = np.zeros((h, w*2, 3), dtype=np.uint8)
    vis_frame[:, :w] = frame
    vis_frame[:, w:] = edges_bgr

    # Add labels
    cv2.putText(vis_frame, "Original", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    cv2.putText(vis_frame, "Edges", (w+10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

    return vis_frame

def fetch_and_cache_lorcana_sets():
    try:
        logging.info("Fetching sets from Lorcast...")
        response = requests.get("https://api.lorcast.com/v0/sets")
        if response.status_code == 200:
            # Process the response
            data = response.json()
            sets = data.get("results", [])
            logging.info(f"Retrieved {len(sets)} sets from Lorcast")
            new_sets = []
            for set_data in sets:
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