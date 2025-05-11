from flask import Flask, render_template, request
import requests
from flask_sqlalchemy import SQLAlchemy
import time
import os
import logging
import re
import json
import ijson


app = Flask(__name__)

# Ensure the directory exists and is writable
db_dir = os.path.abspath('instance')
os.makedirs(db_dir, exist_ok=True)
db_path = os.path.join(db_dir, 'mtg.db')


app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'   # Configure the SQLite database
app.config['UPLOAD_FOLDER'] = 'static/images'  # Configure the folder to store images
db = SQLAlchemy(app)

# Define the association table for the many-to-many relationship between Card and Set
card_sets = db.Table('card_sets',
    db.Column('card_id', db.String, db.ForeignKey('card.id'), primary_key=True),
    db.Column('set_id', db.String, db.ForeignKey('set.id'), primary_key=True)
)

# Association table for the many-to-many relationship between Card and Color
card_colors = db.Table('card_colors',
    db.Column('card_id', db.String, db.ForeignKey('card.id'), primary_key=True),
    db.Column('color_id', db.String, db.ForeignKey('color.id'), primary_key=True)
)

class Color(db.Model):
    id = db.Column(db.String, primary_key=True)
    name = db.Column(db.String, nullable=False)

    def __repr__(self):
        return f"<Color {self.name}>"

class Card(db.Model):
    id = db.Column(db.String, primary_key=True)
    name = db.Column(db.String, nullable=False)
    type_line = db.Column(db.String)
    image_url = db.Column(db.String)
    local_image_path = db.Column(db.String)  # Store the local path to the image
    colors = db.relationship('Color', secondary=card_colors, lazy='subquery',
                            backref=db.backref('cards', lazy=True))
    mana_costs = db.Column(db.String)  # Store mana costs as a comma-separated string
    text = db.Column(db.String)
    power = db.Column(db.String, nullable=True)
    toughness = db.Column(db.String, nullable=True)
    raw = db.Column(db.String)
    rarity = db.Column(db.String)
    sets = db.relationship('Set', secondary=card_sets, backref=db.backref('cards', lazy='dynamic'))
    legalities = db.Column(db.String)

    def __repr__(self):
        return f"<Card {self.name}>"

class Set(db.Model):
    id = db.Column(db.String, primary_key=True)
    name = db.Column(db.String, nullable=False)
    code = db.Column(db.String, nullable=False)
    icon_url = db.Column(db.String)
    released_at = db.Column(db.String)

    def __repr__(self):
        return f"<Set {self.name}>"

class Legality(db.Model):
    __tablename__ = 'legality'  # Specify the table name explicitly
    id = db.Column(db.Integer, primary_key=True)
    format = db.Column(db.String, nullable=False)
    legality = db.Column(db.String, nullable=False)
    card_id = db.Column(db.String, db.ForeignKey('card.id'), nullable=False)

    def __repr__(self):
        return f"<Legality {self.format} - {self.legality}>"


# Custom filter to strip ANSI escape codes
class StripColorFilter(logging.Filter):
    def filter(self, record):
        ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')
        record.msg = ansi_escape.sub('', record.msg)
        return True

# Configure logging
logging.basicConfig(
    #filename='app.log',  # Log file name
    level=logging.DEBUG,  # Log level
    format='%(asctime)s - %(levelname)s - %(message)s',  # Log format
    handlers=[
        logging.StreamHandler()  # Use StreamHandler to output logs to the console
    ]
)

# Add the custom filter to the root logger
logging.getLogger().addFilter(StripColorFilter())

# Ensure the upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Scryfall Cards Search Endpoint
SCRYFALL_API_URL = "https://api.scryfall.com/cards/search?q="

def fetch_adn_cache_legalities():
    response = requests.get("https://api.scryfall.com/sets")
    if response.status_code == 200:
        data = response.json()
        sets = data.get("data", [])
        for set_data in sets:
            existing_set = Set.query.get(set_data.get("id"))
            if not existing_set:
                new_set = Set(
                    id=set_data.get("id"),
                    name=set_data.get("name"),
                    code=set_data.get("code"),
                    icon_url=set_data.get("icon_svg_uri"),  # Cache the set icon URL
                    released_at=set_data.get("released_at")  # Cache the set release date
                )
                db.session.add(new_set)
                db.session.flush()

            # Add a 50ms delay between each API call
            time.sleep(0.05)  # 50ms delay
        db.session.commit()

def fetch_and_cache_sets():
    response = requests.get("https://api.scryfall.com/sets")
    if response.status_code == 200:
        data = response.json()
        sets = data.get("data", [])
        for set_data in sets:
            existing_set = Set.query.get(set_data.get("id"))
            if not existing_set:
                new_set = Set(
                    id=set_data.get("id"),
                    name=set_data.get("name"),
                    code=set_data.get("code"),
                    icon_url=set_data.get("icon_svg_uri"),  # Cache the set icon URL
                    released_at=set_data.get("released_at")  # Cache the set release date
                )
                db.session.add(new_set)
                db.session.flush()
        db.session.commit()

def download_image(url, filename):
    logging.debug(f"Downloading image from {url} to {filename}")
    # Check if the file already exists
    if os.path.exists(filename):
        logging.info(f"Image already exists at {filename}, skipping download.")
        return True

    # If the file does not exist, proceed with downloading
    response = requests.get(url)
    if response.status_code == 200:
        with open(filename, 'wb') as f:
            f.write(response.content)
        logging.info(f"Image downloaded and saved to {filename}")
        return True
    else:
        logging.error(f"Failed to download image from {url}")
        return False


def fetch_and_cache_cards(card_name=None, card_type=None, selected_colors=None, selected_sets=None, search_string=None):
    # Validate inputs
    query_parts = []
    if card_name:
        query_parts.append(f'!"{card_name}"')
    if card_type:
        query_parts.append(f't:{card_type}')
    if selected_colors:
        db_query = db_query.join(card_colors).join(Color).filter(Color.name.in_(selected_colors))
    if selected_sets:
        query_parts.append(" ".join([f's:{set_code}' for set_code in selected_sets]))
    if search_string:
        query_parts.append(f'"{search_string}"')

    query = " ".join(query_parts)
    logging.info(f"Search Query: {query}")

    # Build cumulative database query
    db_query = Card.query
    if card_name:
        db_query = db_query.filter(Card.name == card_name)
    if card_type:
        db_query = db_query.filter(Card.type_line.ilike(f"%{card_type}%"))
    if selected_colors:
        db_query = db_query.join(card_colors).join(Color).filter(Color.name.in_(selected_colors))
    if selected_sets:
        db_query = db_query.filter(Card.sets.any(Set.code.in_(selected_sets)))
    if search_string:
        db_query = db_query.filter(Card.name.ilike(f"%{search_string}%"))


    existing_cards = db_query.all()
    logging.info(f"Found {len(existing_cards)} matching cards in DB.")

    if existing_cards:
        return existing_cards

    # Fetch from Scryfall if not in database
    logging.info("No matching cards in DB. Fetching from Scryfall...")
    fetched_cards = []
    has_more = True
    page = 1

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
        # Check if the card already exists in the database
        existing_card = Card.query.get(card_data["id"])
        if existing_card:
            continue

        # Local image download
        image_url = card_data.get("image_uris", {}).get("normal")
        local_image_path = None
        if image_url:
            filename = os.path.join(app.config['UPLOAD_FOLDER'], f"{card_data['id']}.jpg")
            if download_image(image_url, filename):
                local_image_path = filename

        # Create card
        # Assuming you have a Color model with an id field of type String
        color_names = card_data.get("colors", [])

        # Fetch or create Color objects
        colors = []
        for color_name in color_names:
            # Check if the color already exists
            color = Color.query.filter_by(name=color_name).first()
            if not color:
                # Create a new color with a unique id
                color_id = f"color_{color_name}"  # You can use any logic to generate a unique ID
                color = Color(id=color_id, name=color_name)
                db.session.add(color)
                db.session.flush()
            colors.append(color)

        # Check if the set already exists in the database
        existing_set = Set.query.get(card_data["set"])
        if not existing_set:
            # If the set doesn't exist, you might need to fetch its details from an external API or have a predefined list
            # For now, let's assume you have a predefined list or fetch details from an API
            # Here, we'll create a placeholder set with minimal information
            new_set = Set(
                id=card_data["set"],
                name=f"Set {card_data['set']}",  # Placeholder name
                code=card_data["set"],
                icon_url="",  # Placeholder icon URL
                released_at=""  # Placeholder release date
            )
            db.session.add(new_set)
        else:
            # Use the existing set
            new_set = existing_set

        # Assign the list of Color objects to the colors attribute
        new_card = Card(
            id=card_data["id"],
            name=card_data["name"],
            type_line=card_data.get("type_line"),
            mana_costs=card_data.get("mana_cost"),
            text=card_data.get("oracle_text"),
            power=card_data.get("power"),
            toughness=card_data.get("toughness"),
            rarity=card_data.get("rarity"),
            raw=json.dumps(card_data),
            image_url=image_url,
            local_image_path=local_image_path,
            legalities=json.dumps(card_data.get("legalities", {}))
        )

        # Assign colors to the card
        new_card.colors = colors

        # Associate the card with the set
        new_card.sets.append(new_set)

        db.session.add(new_card)

    db.session.commit()

    # Rerun query to return cards
    return db_query.all()

@app.route("/", methods=["GET", "POST"])
def index():
    cards = []
    error = None

    if request.method == "POST":
        query = request.form.get("query")
        if query:
            cards = fetch_and_cache_cards(search_string=query)

    return render_template("index.html", cards=cards, error=error)


@app.route("/sets", methods=["GET"])
def sets():
    sort = request.args.get('sort', 'name')  # Default sort by name
    direction = request.args.get('direction', 'asc')  # Default sort direction

    if sort == 'name':
        if direction == 'asc':
            sets = Set.query.order_by(Set.name.asc()).all()
        else:
            sets = Set.query.order_by(Set.name.desc()).all()
    elif sort == 'date':
        if direction == 'asc':
            sets = Set.query.order_by(Set.released_at.asc()).all()
        else:
            sets = Set.query.order_by(Set.released_at.desc()).all()
    else:
        sets = Set.query.all()

    return render_template("sets.html", sets=sets)

@app.route("/set/<set_code>")
def set_detail(set_code):
    logging.info("⚙️ fetch_and_cache_cards triggered")
    cards = fetch_and_cache_cards(selected_sets=[set_code])
    selected_set = Set.query.filter_by(code=set_code).first()

    return render_template("set_detail.html", selected_set=selected_set, cards=cards)


@app.route('/card/<card_id>')
def card_detail(card_id):
    # Fetch the card details from the database
    card = Card.query.get(card_id)
    if not card:
        return "Card not found", 404

    # Fetch the set details for the card
    card_sets = card.sets
    set_details = []
    for card_set in card_sets:
        set_detail = {
            'name': card_set.name,
            'code': card_set.code,
            'icon_url': card_set.icon_url,
            'released_at': card_set.released_at
        }
        set_details.append(set_detail)

    # Render the card details template
    return render_template('card_detail.html', card=card , set_details=set_details)

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        fetch_and_cache_sets()

        # Check if the import file exists at startup
        import_file_path = "import/import.json"  # Update this path to the location of your bulk data file
        if os.path.exists(import_file_path):
            logging.info("Found import.json file, staring import")
            # import_bulk_data_from_file(import_file_path)

    app.run(debug=True)