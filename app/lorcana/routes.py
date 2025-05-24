# Standard library imports
import base64
import csv
import logging
import threading
import time
from io import StringIO

# Third-party imports
import cv2
import numpy as np
from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
    Response
)

# Local application imports
from ..models import LorcanaCard, LorcanaSet, db
from ..utils import shared_state
from ..utils.lorcana_helpers import (
    download_lorcana_image,
    fetch_and_cache_lorcana_cards,
    detect_card,
    process_frame,
    get_card_names_from_db,
    get_frame,
    get_card_info,
    get_extracted_text,
    get_debug_info
)

# Create a blueprint
lorcana_bp = Blueprint('lorcana', __name__, url_prefix='/lorcana')

# Get card names from the database
card_names = []

@lorcana_bp.route('/camera')
def camera_page():
    """Camera page route."""

    return render_template('lorcana/camera_import.html')

def generate():
    """
    Generator function for the video stream.
    """
    while True:
        frame = get_frame()
        if frame is None:
            continue

        yield(b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

def generate_frames():
    """Generate frames from the output frame."""
    global output_frame, lock

    while True:
        # Acquire the lock, copy the output frame, and release the lock
        with lock:
            if output_frame is None:
                continue
            frame = output_frame.copy()

        # Encode the frame as JPEG
        _, jpeg = cv2.imencode('.jpg', frame)

        # Yield the frame in the response
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')


@lorcana_bp.route('/card_info')
def card_info():
    """
    Route for getting the current card info.
    """
    info = get_card_info()
    text = get_extracted_text()
    debug = get_debug_info()

    response = {}
    if info:
        response.update(info)
    if text:
        response['extracted_text'] = text
    if debug:
        response['debug_info'] = debug

    if response:
        return jsonify(response)
    else:
        return jsonify({})

area_threshold = 5000

@lorcana_bp.route('/update_threshold', methods=['POST'])
def update_threshold():
    """
    Route for updating the area threshold.
    """
    global area_threshold

    data = request.json
    if 'threshold' in data:
        area_threshold = int(data['threshold'])
        print(f"Updated area threshold to {area_threshold}")

    return jsonify({'success': True})

@lorcana_bp.route('/toggle_edges', methods=['POST'])
def toggle_edges():
    shared_state.show_edges = not shared_state.show_edges
    print(f"Edge visualization: {shared_state.show_edges}")
    return jsonify({'success': True, 'show_edges': shared_state.show_edges})

@lorcana_bp.route('/process_frame_route', methods=['POST'])
def process_frame_route():
    # Get data from request
    data = request.get_json()
    image_data = data['image'].split(',')[1]
    decoded_data = base64.b64decode(image_data)
    np_data = np.frombuffer(decoded_data, np.uint8)
    frame = cv2.imdecode(np_data, cv2.IMREAD_COLOR)

    # Get parameters from request, with defaults
    min_area = data.get('min_area', 10000)
    canny_low = data.get('canny_low', 50)
    canny_high = data.get('canny_high', 150)
    epsilon = data.get('epsilon', 0.15)

    # Get card names for recognition
    card_names = get_card_names_from_db()

    # Process the frame
    processed_frame, info, text, debug_info = process_frame(frame, card_names)

    # Make sure everything is JSON serializable
    def make_json_safe(obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, dict):
            return {k: make_json_safe(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [make_json_safe(i) for i in obj]
        return obj

    # Apply the fix to all potentially non-serializable objects
    info = make_json_safe(info)
    debug_info = make_json_safe(debug_info)

    # Get the warped card image from the process_frame function
    # This assumes card_img is available in debug_info or can be extracted from info
    warped_image = None
    if 'card_img' in debug_info and debug_info['card_img'] is not None:
        _, buffer = cv2.imencode('.jpg', debug_info['card_img'])
        warped_image = f'data:image/jpeg;base64,{base64.b64encode(buffer).decode("utf-8")}'

    # Encode the OCR input image if available
    ocr_input_image = None
    if 'ocr_input_img' in debug_info and debug_info['ocr_input_img'] is not None:
        img = debug_info['ocr_input_img']
        if isinstance(img, np.ndarray) and img.ndim >= 2:
            try:
                _, buffer = cv2.imencode('.jpg', img)
                ocr_input_image = f'data:image/jpeg;base64,{base64.b64encode(buffer).decode("utf-8")}'
            except Exception as e:
                print(f"Error encoding OCR input image: {e}")
                ocr_input_image = None
        else:
            print(f"Invalid OCR input image type: {type(img)}, shape: {getattr(img, 'shape', None)}")

    # Encode the processed frame
    if processed_frame is not None:
        _, buffer = cv2.imencode('.jpg', processed_frame)
        processed_image_base64 = base64.b64encode(buffer).decode('utf-8')
    else:
        # If no processed frame, use the debug frame
        _, buffer = cv2.imencode('.jpg', debug_info.get('debug_frame', frame))
        processed_image_base64 = base64.b64encode(buffer).decode('utf-8')

    # Return the response
    return jsonify({
        'processed_image': f'data:image/jpeg;base64,{processed_image_base64}',
        'warped_image': warped_image,  # Add the warped image to the response
        'ocr_input_image': ocr_input_image,  # Add this line
        'card_info': info,
        'extracted_text': text,
        'debug_info': debug_info
    })

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
    # reprints = fetch_mtg_reprints(card)  # Fetch reprints from Scryfall API
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
        'mtg/set_detail.html',
        cards=cards,
        selected_set=selected_set
    )
