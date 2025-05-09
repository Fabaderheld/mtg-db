from flask import Flask, render_template, request
import requests
from flask_sqlalchemy import SQLAlchemy
import time
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cards.db'  # Configure the SQLite database
app.config['UPLOAD_FOLDER'] = 'static/images'  # Configure the folder to store images
db = SQLAlchemy(app)

# Ensure the upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


def download_image(url, filename):
    response = requests.get(url)
    if response.status_code == 200:
        with open(filename, 'wb') as f:
            f.write(response.content)

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

    def __repr__(self):
        return f"<Card {self.name}>"

class Set(db.Model):
    id = db.Column(db.String, primary_key=True)
    name = db.Column(db.String, nullable=False)
    code = db.Column(db.String, nullable=False)
    icon_url = db.Column(db.String)  # Add a field for the set icon URL
    released_at = db.Column(db.String)  # Add a field for the set icon URL

    def __repr__(self):
        return f"<Set {self.name}>"


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
        db.session.commit()



SCRYFALL_API_URL = "https://api.scryfall.com/cards/search?q="

@app.route("/", methods=["GET", "POST"])
def index():
    cards = []
    error = None

    if request.method == "POST":
        query = request.form.get("query")
        if query:
            # Check the database for existing results
            cached_cards = Card.query.filter_by(name=query).all()
            if cached_cards:
                cards = cached_cards
            else:
                # Make the API call if results are not found in the database
                response = requests.get(SCRYFALL_API_URL + query)
                if response.status_code == 200:
                    data = response.json()
                    cards = data.get("data", [])
                    # Cache the results in the database
                    for card in cards:
                        card_id = card.get("id")
                        existing_card = db.session.get(Card, card_id)
                        if not existing_card:
                            # Handle missing or null image_uris
                            image_uris = card.get("image_uris", {})
                            image_url = image_uris.get("normal") if image_uris else None

                            new_card = Card(
                                id=card_id,
                                name=card.get("name"),
                                image_url=image_url,
                                type_line=card.get("type_line")
                            )
                            db.session.add(new_card)
                    db.session.commit()
                else:
                    error = "Error fetching cards from Scryfall."

    return render_template("index.html", cards=cards, error=error)


@app.route("/advanced_search", methods=["GET", "POST"])
def advanced_search():
    card_types = ["Creature", "Instant", "Sorcery", "Artifact", "Enchantment", "Planeswalker", "Land"]  # Example card types
    colors = ["White", "Blue", "Black", "Red", "Green"]  # Example colors
    mana_icons = fetch_mana_icons()  # Fetch mana icons from Scryfall API

    # Fetch sets from the database
    sets = Set.query.all()

    if request.method == "POST":
        # Extract search parameters from the form
        card_name = request.form.get("cardName")
        card_type = request.form.get("cardType")
        selected_colors = request.form.getlist("colors")
        selected_sets = request.form.getlist("sets")

        # Construct the search query according to Scryfall API documentation
        query_parts = []
        if card_name:
            query_parts.append(f'!"{card_name}"')  # Exact match for card name
        if card_type:
            query_parts.append(f't:{card_type}')  # Card type
        if selected_colors:
            query_parts.append(" ".join([f'c:{color[0].upper()}' for color in selected_colors]))  # Colors
        if selected_sets:
            query_parts.append(" ".join([f's:{set_code}' for set_code in selected_sets]))  # Sets

        query = " ".join(query_parts)
        print(f"Search Query: {query}")  # Debug: Print the search query

        # Query the local database for existing cards
        all_cards = []
        if card_name:
            all_cards = Card.query.filter_by(name=card_name).all()
        if card_type:
            all_cards = Card.query.filter_by(type_line=card_type).all()
        if selected_colors:
            all_cards = Card.query.join(card_colors).join(Color).filter(Color.name.in_(selected_colors)).all()
        if selected_sets:
            all_cards = Card.query.filter(Card.sets.any(Set.code.in_(selected_sets))).all()

        # If no cards are found in the local database, fetch from the Scryfall API
        if not all_cards:
            all_cards = []
            has_more = True
            page = 1

            while has_more:
                response = requests.get(f"https://api.scryfall.com/cards/search?q={query}&page={page}")
                print(f"API Response Status Code: {response.status_code}")  # Debug: Print the response status code
                time.sleep(0.05)  # Add a 50ms delay between API calls

                if response.status_code == 200:
                    data = response.json()
                    print(f"API Response Data: {data}")  # Debug: Print the response data
                    all_cards.extend(data.get("data", []))
                    has_more = data.get("has_more", False)
                    page += 1
                else:
                    has_more = False

            # Store the fetched cards in the local database
            for card_data in all_cards:
                existing_card = Card.query.get(card_data.get("id"))
                if not existing_card:
                    image_url = card_data.get("image_uris", {}).get("normal")
                    local_image_path = None
                    if image_url:
                        filename = os.path.join(app.config['UPLOAD_FOLDER'], f"{card_data.get('id')}.jpg")
                        download_image(image_url, filename)
                        local_image_path = filename

                    new_card = Card(
                        id=card_data.get("id"),
                        name=card_data.get("name"),
                        type_line=card_data.get("type_line"),
                        image_url=image_url,
                        local_image_path=local_image_path
                        # Add other fields as needed
                    )

                    db.session.add(new_card)
            db.session.commit()

        total_items = len(all_cards)
        print(f"Total Items Found: {total_items}")  # Debug: Print the total number of items found
        return render_template("advanced_search.html", card_types=card_types, colors=colors, mana_icons=mana_icons, sets=sets, cards=all_cards, total_items=total_items)

    # For GET requests, just render the template with the sets
    return render_template("advanced_search.html", card_types=card_types, colors=colors, mana_icons=mana_icons, sets=sets)

def fetch_mana_icons():
    response = requests.get("https://api.scryfall.com/symbology")
    mana_icons = {
        "White": None,
        "Blue": None,
        "Black": None,
        "Red": None,
        "Green": None
    }

    if response.status_code == 200:
        data = response.json()
        for symbol in data.get("data", []):
            if symbol.get("symbol") in ["{W}", "{U}", "{B}", "{R}", "{G}"]:
                color = symbol.get("symbol")[1:-1].capitalize()  # Extract the color from the symbol
                mana_icons[color] = symbol.get("svg_uri")
                time.sleep(0.05)  # Add a 50ms delay between API calls

    return mana_icons

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

@app.route("/search", methods=["GET"])
def search():
    set_code = request.args.get('set')
    if set_code:
        # Perform a search for all cards in the specified set
        response = requests.get(f"https://api.scryfall.com/cards/search?q=set:{set_code}")
        if response.status_code == 200:
            data = response.json()
            cards = data.get("data", [])
            return render_template("search_results.html", cards=cards)
            time.sleep(0.05)  # Add a 50ms delay between API calls
        else:
            error = "Error fetching cards from Scryfall."
            return render_template("search_results.html", error=error)
    else:
        error = "No set specified."
        return render_template("search_results.html", error=error)


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
