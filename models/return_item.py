from models import db
from datetime import datetime

class ReturnItem(db.Model):
    __tablename__ = 'return_items'

    return_item_id = db.Column(db.Integer, primary_key=True)
    return_id      = db.Column(db.Integer, db.ForeignKey('returns.return_id'), nullable=False)
    product_id     = db.Column(db.Integer, db.ForeignKey('products.product_id'), nullable=False)
    quantity       = db.Column(db.Integer, nullable=False)
    price          = db.Column(db.Numeric(10,2))
    subtotal       = db.Column(db.Numeric(10,2))
    reason         = db.Column(db.String(100))

    product        = db.relationship('Product')

