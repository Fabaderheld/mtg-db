# Standard library imports
import json
import logging
import os
import time
import threading

# Third-party imports
import cv2
import numpy as np
import pytesseract
import requests
from flask import current_app
from rapidfuzz import process, fuzz

# Local application imports
from ..models import (
    LorcanaCard,
    LorcanaSet,
    LorcanaType,
    LorcanaClassification,
    LorcanaIllustrator,
    db
)
from ..utils import shared_state

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
    # Create a copy for debugging visualization
    debug_frame = frame.copy() if debug else None
    debug_images = {}  # Dictionary to store debug images

    # Convert to grayscale
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Apply Gaussian blur to reduce noise
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)

    # Edge detection with adjusted thresholds
    edges = cv2.Canny(blurred, canny_low, canny_high)
    debug_images['edges'] = edges  # Store edges for web display

    # Clean up edges with morphological operations
    kernel = np.ones((5,5), np.uint8)
    dilated = cv2.dilate(edges, kernel, iterations=2)
    eroded = cv2.erode(dilated, kernel, iterations=1)
    debug_images['processed_edges'] = eroded  # Store processed edges

    # Find contours
    contours, _ = cv2.findContours(eroded, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Filter by minimum area
    contours = [c for c in contours if cv2.contourArea(c) > min_area]
    print(f"Found {len(contours)} contours")

    # Draw all contours on debug frame
    if debug:
        contour_frame = frame.copy()
        cv2.drawContours(contour_frame, contours, -1, (0, 255, 0), 2)
        debug_images['all_contours'] = contour_frame  # Store instead of showing

    # Sort contours by area (largest first)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)

    # Find the biggest contour that's likely a card
    for contour in contours[:5]:  # Check the 5 largest contours
        peri = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, epsilon * peri, True)

        if debug:
            for pt in approx:
                cv2.circle(debug_frame, tuple(pt[0]), 5, (0, 255, 255), -1)

        # Check if it's a quadrilateral (4 points)
        if len(approx) == 4:
            # Get the corners
            pts = approx.reshape(4, 2)

            # Reorder points to [top-left, top-right, bottom-right, bottom-left]
            # Sort by y-coordinate (top to bottom)
            pts = pts[np.argsort(pts[:, 1])]
            # Sort top points by x-coordinate (left to right)
            top = pts[:2][np.argsort(pts[:2, 0])]
            # Sort bottom points by x-coordinate (left to right)
            bottom = pts[2:][np.argsort(pts[2:, 0])]
            # Combine points in the correct order
            pts = np.vstack([top, bottom[::-1]])

            # Check aspect ratio
            x, y, w, h = cv2.boundingRect(contour)
            aspect_ratio = float(w) / h
            print(f"Quadrilateral found: aspect_ratio={aspect_ratio}, area={cv2.contourArea(contour)}")

            # Lorcana cards have aspect ratio around 0.71
            if 0.60 <= aspect_ratio <= 0.80:
                if debug:
                    cv2.drawContours(debug_frame, [approx], -1, (0, 0, 255), 3)

                # Perspective transform
                w_card, h_card = 421, 588  # Standard card dimensions
                dst_pts = np.array([[0, 0], [w_card, 0], [w_card, h_card], [0, h_card]], dtype=np.float32)
                M = cv2.getPerspectiveTransform(pts.astype(np.float32), dst_pts)
                warped = cv2.warpPerspective(frame, M, (w_card, h_card))
                debug_images['warped'] = warped  # Store warped image

                return warped, pts, edges, debug_frame, debug_images

    # If no suitable quadrilateral is found, try the bounding rectangle approach
    for contour in contours[:5]:
        x, y, w, h = cv2.boundingRect(contour)
        aspect_ratio = float(w) / h

        # Check if the aspect ratio matches a card
        if 0.60 <= aspect_ratio <= 0.80 and cv2.contourArea(contour) > min_area:
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
            debug_images['warped'] = warped  # Store warped image

            return warped, pts, edges, debug_frame, debug_images

    # If we get here, no card was detected
    print("No card detected")
    return None, None, edges, debug_frame, debug_images

def extract_card_text(warped_card, debug=True):
    """
    Extract text from a warped card image using OCR.

    Args:
        warped_card: The perspective-corrected card image
        debug: Whether to show debug information

    Returns:
        text: The extracted text
        debug_info: Dictionary containing debug information and images
    """
    if warped_card is None:
        return None, {"error": "No card image provided"}

    debug_info = {}

    # Define the region of interest for the card name
    y_start, y_end = 30, 80
    x_start, x_end = 40, 380

    # Crop the name region
    try:
        name_region = warped_card[y_start:y_end, x_start:x_end]
        debug_info["card_img"] = warped_card
    except:
        return None, {"error": "Failed to crop name region"}

    # Convert to grayscale
    gray = cv2.cvtColor(name_region, cv2.COLOR_BGR2GRAY)

    # Apply thresholding to improve OCR
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)

    # Store debug images in the debug_info dictionary instead of showing them
    debug_info["name_region_img"] = name_region
    debug_info["threshold_img"] = thresh
    debug_info["ocr_input_img"] = thresh

    # Use Tesseract to extract text
    try:
        import pytesseract
        text = pytesseract.image_to_string(thresh, config='--psm 7 -l eng')
        text = text.strip()
        debug_info["raw_text"] = text
        return text, debug_info
    except Exception as e:
        print(f"OCR error: {e}")
        debug_info["error"] = f"OCR error: {e}"
        return None, debug_info


def match_card(warped_card, reference_cards, debug=True):
    """
    Match a warped card image against a set of reference card images.

    Args:
        warped_card: The perspective-corrected card image
        reference_cards: Dictionary of {card_name: card_image}
        debug: Whether to show debug information

    Returns:
        best_match: Name of the best matching card
        score: Similarity score of the best match
        debug_info: Dictionary containing debug information
    """
    if warped_card is None:
        return None, 0, {"error": "No card image provided"}

    debug_info = {}

    # Convert the warped card to grayscale
    gray_card = cv2.cvtColor(warped_card, cv2.COLOR_BGR2GRAY)

    best_match = None
    best_score = 0

    # Compare with each reference card
    for card_name, ref_img in reference_cards.items():
        # Resize reference image to match warped card
        ref_img = cv2.resize(ref_img, (warped_card.shape[1], warped_card.shape[0]))

        # Convert reference image to grayscale
        gray_ref = cv2.cvtColor(ref_img, cv2.COLOR_BGR2GRAY)

        # Calculate structural similarity
        from skimage.metrics import structural_similarity as ssim
        score, _ = ssim(gray_card, gray_ref, full=True)

        if score > best_score:
            best_score = score
            best_match = card_name

    debug_info["best_match"] = best_match
    debug_info["match_score"] = best_score

    if debug:
        print(f"Best match: {best_match} with score {best_score}")

    return best_match, best_score, debug_info

def lookup_card_in_db(name):
    """
    Look up a card by name in the database.
    """
    from app.models import LorcanaCard  # Import here to avoid circular imports

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

def process_frame(frame, card_names=None, debug=True):
    """
    Process a frame to detect a card, extract text, and optionally match against reference cards.

    Args:
        frame: The input frame/image
        card_names: List of card names for fuzzy matching (optional)
        debug: Whether to show debug information

    Returns:
        processed_frame: The processed frame with annotations
        card_info: Dictionary containing card information
        extracted_text: The extracted text
        debug_info: Dictionary containing debug information
    """
    debug_info = {}

    # Step 1: Detect and warp the card
    warped_card, card_corners, edges, debug_frame, debug_images = detect_card(frame, debug=debug)
    debug_info["debug_frame"] = debug_frame
    debug_info["edges"] = edges

    if warped_card is None:
        return frame, {}, None, debug_info

    # Step 2: Extract text from the card
    extracted_text, text_debug_info = extract_card_text(warped_card, debug=debug)
    debug_info.update(text_debug_info)

    # Step 3: Match the card against reference cards (if available)
    card_info = {}
    if extracted_text and card_names:
        from fuzzywuzzy import process, fuzz
        match, score, _ = process.extractOne(extracted_text, card_names, scorer=fuzz.WRatio)
        if score > 60:  # Adjust threshold as needed
            card_info["name"] = match
            card_info["match_score"] = score

    # Annotate the processed frame
    processed_frame = frame.copy()
    if card_corners is not None:
        cv2.drawContours(processed_frame, [card_corners.reshape(-1, 1, 2)], -1, (0, 255, 0), 3)
        if extracted_text:
            cv2.putText(processed_frame, extracted_text, (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

    return processed_frame, card_info, extracted_text, debug_info

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