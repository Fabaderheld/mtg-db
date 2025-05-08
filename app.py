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
            response = requests.get(SCRYFALL_API_URL + query)
            if response.status_code == 200:
                data = response.json()
                cards = data.get("data", [])
            else:
                error = "Error fetching cards from Scryfall."

    return render_template("index.html", cards=cards, error=error)

if __name__ == "__main__":
    app.run(debug=True)