from models import db


class SaleItem(db.Model):
    __tablename__ = 'sale_items'

    sale_item_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    sale_id      = db.Column(db.Integer, db.ForeignKey('sales.sale_id'),       nullable=False)
    product_id   = db.Column(db.Integer, db.ForeignKey('products.product_id'), nullable=False)
    quantity     = db.Column(db.Integer,        nullable=False)
    price        = db.Column(db.Numeric(10, 2), nullable=False)
    subtotal     = db.Column(db.Numeric(10, 2), nullable=False)