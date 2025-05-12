from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Card(db.Model):
    __tablename__ = 'card'

    id = db.Column(db.String, primary_key=True)  # Scryfall ID
    name = db.Column(db.String, index=True)
    layout = db.Column(db.String)
    mana_cost = db.Column(db.String)
    cmc = db.Column(db.Float)
    type_line = db.Column(db.String)
    oracle_text = db.Column(db.Text)
    power = db.Column(db.String)
    toughness = db.Column(db.String)
    loyalty = db.Column(db.String)
    rarity = db.Column(db.String)
    collector_number = db.Column(db.String)
    set_code = db.Column(db.String, db.ForeignKey('set.code'))
    lang = db.Column(db.String)
    released_at = db.Column(db.String)

    image_uri = db.Column(db.String)
    scryfall_uri = db.Column(db.String)
    rulings_uri = db.Column(db.String)
    prints_search_uri = db.Column(db.String)

    # Relationships
    set = db.relationship("Set", back_populates="cards")
    colors = db.relationship("Color", secondary="card_colors", back_populates="cards")
    types = db.relationship("Type", secondary="card_types", back_populates="cards")

class Set(db.Model):
    __tablename__ = 'set'

    code = db.Column(db.String, primary_key=True)
    name = db.Column(db.String)
    released_at = db.Column(db.String)
    set_type = db.Column(db.String)

    cards = db.relationship("Card", back_populates="set")

class Color(db.Model):
    __tablename__ = 'color'

    id = db.Column(db.String, primary_key=True)  # e.g. 'color_W', 'color_U'
    name = db.Column(db.String)  # e.g. 'W'

    cards = db.relationship("Card", secondary="card_colors", back_populates="colors")

class Type(db.Model):
    __tablename__ = 'type'

    id = db.Column(db.String, primary_key=True)
    name = db.Column(db.String)

    cards = db.relationship("Card", secondary="card_types", back_populates="types")

# Association tables for many-to-many relations
card_colors = db.Table('card_colors',
    db.Column('card_id', db.String, db.ForeignKey('card.id'), primary_key=True),
    db.Column('color_id', db.String, db.ForeignKey('color.id'), primary_key=True)
)

card_types = db.Table('card_types',
    db.Column('card_id', db.String, db.ForeignKey('card.id'), primary_key=True),
    db.Column('type_id', db.String, db.ForeignKey('type.id'), primary_key=True)
)
