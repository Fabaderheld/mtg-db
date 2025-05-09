from flask import Flask, render_template, request
import requests
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mtg.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Card(db.Model):
    id = db.Column(db.String, primary_key=True)
    name = db.Column(db.String, nullable=False)
    image_url = db.Column(db.String)
    type_line = db.Column(db.String)

    def __repr__(self):
        return f"<Card {self.name}>"

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
    cards = []
    error = None

    # Fetch and cache sets if not already cached
    if not Set.query.first():
        fetch_and_cache_sets()

    sets = Set.query.all()

    if request.method == "POST":
        card_name = request.form.get("cardName")
        card_type = request.form.get("cardType")
        card_set = request.form.get("cardSet")
        # Build your advanced search query here
        query = f"name:{card_name} type:{card_type} set:{card_set}"
        response = requests.get(SCRYFALL_API_URL + query)
        if response.status_code == 200:
            data = response.json()
            cards = data.get("data", [])
        else:
            error = "Error fetching cards from Scryfall."

    return render_template("advanced_search.html", cards=cards, error=error, sets=sets)

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
