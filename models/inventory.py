from . import db
from datetime import datetime


class Inventory(db.Model):
    __tablename__ = 'inventory'

    inventory_id  = db.Column(db.Integer, primary_key=True, autoincrement=True)
    product_id    = db.Column(db.Integer, db.ForeignKey('products.product_id'), nullable=False)
    quantity      = db.Column(db.Integer, nullable=False, default=0)
    minimum_stock = db.Column(db.Integer, nullable=False)
    last_updated  = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)