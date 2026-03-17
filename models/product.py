from . import db

class Product(db.Model):
    __tablename__ = 'products'

    product_id   = db.Column(db.Integer, primary_key=True, autoincrement=True)
    product_name = db.Column(db.String(100), nullable=False)
    price        = db.Column(db.Numeric(10, 2), nullable=False)
    unit         = db.Column(db.String(20))
    is_active    = db.Column(db.Boolean, default=True)

    sale_items     = db.relationship('SaleItem',     backref='product', lazy=True)
    delivery_items = db.relationship('DeliveryItem', backref='product', lazy=True)
    inventory      = db.relationship('Inventory',    backref='product', uselist=False)