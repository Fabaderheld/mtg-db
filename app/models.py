from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class MtgCard(db.Model):
    __tablename__ = 'mtg_card'

    id = db.Column(db.String, primary_key=True)  # Scryfall ID
    oracle_id = db.Column(db.String, index=True)  # Scryfall Oracle ID
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
    set_code = db.Column(db.String, db.ForeignKey('mtg_set.code'))
    lang = db.Column(db.String)
    released_at = db.Column(db.String)
    mana_costs = db.Column(db.String)
    image_uri = db.Column(db.String)
    local_image_path = db.Column(db.String)
    scryfall_uri = db.Column(db.String)
    rulings_uri = db.Column(db.String)
    legalities = db.Column(db.Text)
    prints_search_uri = db.Column(db.String)

    # Relationships
    set = db.relationship("MtgSet", back_populates="cards")
    colors = db.relationship("Color", secondary="card_colors", back_populates="cards")
    types = db.relationship("Type", secondary="card_types", back_populates="cards")

class MtgSet(db.Model):
    __tablename__ = 'mtg_set'

    id = db.Column(db.String, primary_key=True)
    code = db.Column(db.String)
    name = db.Column(db.String)
    icon_url = db.Column(db.String)
    local_icon_path = db.Column(db.String)
    released_at = db.Column(db.String)
    set_type = db.Column(db.String)

    cards = db.relationship("MtgCard", back_populates="set")

class Color(db.Model):
    __tablename__ = 'color'
    id = db.Column(db.String, primary_key=True)
    name = db.Column(db.String)
    cards = db.relationship("MtgCard", secondary="card_colors", back_populates="colors")

class Type(db.Model):
    __tablename__ = 'type'
    id = db.Column(db.String, primary_key=True)
    name = db.Column(db.String)
    cards = db.relationship("MtgCard", secondary="card_types", back_populates="types")

# Association tables for many-to-many relations
card_colors = db.Table('card_colors',
    db.Column('card_id', db.String, db.ForeignKey('mtg_card.id'), primary_key=True),
    db.Column('color_id', db.String, db.ForeignKey('color.id'), primary_key=True)
)

card_types = db.Table('card_types',
    db.Column('card_id', db.String, db.ForeignKey('mtg_card.id'), primary_key=True),
    db.Column('type_id', db.String, db.ForeignKey('type.id'), primary_key=True)
)

# Define the association table for the many-to-many relationship between Card and Set
card_sets = db.Table('card_sets',
    db.Column('card_id', db.String, db.ForeignKey('mtg_card.id'), primary_key=True),
    db.Column('set_code', db.String, db.ForeignKey('mtg_set.code'), primary_key=True)
)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    # Add password hash, email, etc. as needed

class LorcanaCard(db.Model):
    __tablename__ = 'lorcana_card'

    id = db.Column(db.String, primary_key=True)
    name = db.Column(db.String, index=True)
    version = db.Column(db.String)
    layout = db.Column(db.String)
    released_at = db.Column(db.String)
    image_uris_small = db.Column(db.String)  # Flatten image_uris
    image_uris_normal = db.Column(db.String)
    image_uris_large = db.Column(db.String)
    cost = db.Column(db.Integer)
    inkwell = db.Column(db.Boolean)
    ink = db.Column(db.String)
    text = db.Column(db.Text)
    move_cost = db.Column(db.Integer)
    strength = db.Column(db.Integer)
    willpower = db.Column(db.Integer)
    lore = db.Column(db.Integer)
    rarity = db.Column(db.String)
    collector_number = db.Column(db.String)
    lang = db.Column(db.String)
    flavor_text = db.Column(db.Text)
    tcgplayer_id = db.Column(db.Integer)
    legalities_core = db.Column(db.String)  # Flatten legalities
    set_id = db.Column(db.String, db.ForeignKey('lorcana_set.id')) # Use a separate set table
    usd = db.Column(db.String)
    usd_foil = db.Column(db.String)

    # Relationships
    set = db.relationship("LorcanaSet", back_populates="cards")
    types = db.relationship("LorcanaType", secondary="lorcana_card_types", back_populates="cards")
    classifications = db.relationship("LorcanaClassification", secondary="lorcana_card_classifications", back_populates="cards")
    illustrators = db.relationship("LorcanaIllustrator", secondary="lorcana_card_illustrators", back_populates="cards")
    #inventory_entries = db.relationship("CardInventory",back_populates="lorcana_card",overlaps="mtg_card")

class LorcanaSet(db.Model):
    __tablename__ = 'lorcana_set'
    id = db.Column(db.String, primary_key=True)
    code = db.Column(db.String)
    name = db.Column(db.String)

    cards = db.relationship("LorcanaCard", back_populates="set")

class LorcanaType(db.Model):
    __tablename__ = 'lorcana_type'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, unique=True, nullable=False)

    cards = db.relationship("LorcanaCard", secondary="lorcana_card_types", back_populates="types")

class LorcanaClassification(db.Model):
    __tablename__ = 'lorcana_classification'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, unique=True, nullable=False)

    cards = db.relationship("LorcanaCard", secondary="lorcana_card_classifications", back_populates="classifications")

class LorcanaIllustrator(db.Model):
    __tablename__ = 'lorcana_illustrator'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, unique=True, nullable=False)

    cards = db.relationship("LorcanaCard", secondary="lorcana_card_illustrators", back_populates="illustrators")

lorcana_card_types = db.Table('lorcana_card_types',
    db.Column('lorcana_card_id', db.String, db.ForeignKey('lorcana_card.id'), primary_key=True),
    db.Column('lorcana_type_id', db.Integer, db.ForeignKey('lorcana_type.id'), primary_key=True)
)

lorcana_card_classifications = db.Table('lorcana_card_classifications',
    db.Column('lorcana_card_id', db.String, db.ForeignKey('lorcana_card.id'), primary_key=True),
    db.Column('lorcana_classification_id', db.Integer, db.ForeignKey('lorcana_classification.id'), primary_key=True)
)

lorcana_card_illustrators = db.Table('lorcana_card_illustrators',
    db.Column('lorcana_card_id', db.String, db.ForeignKey('lorcana_card.id'), primary_key=True),
    db.Column('lorcana_illustrator_id', db.Integer, db.ForeignKey('lorcana_illustrator.id'), primary_key=True)
)