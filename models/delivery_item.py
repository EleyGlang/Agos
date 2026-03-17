from models import db


class DeliveryItem(db.Model):
    __tablename__ = 'delivery_items'

    delivery_item_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    delivery_id      = db.Column(db.Integer, db.ForeignKey('delivery_orders.delivery_id'), nullable=False)
    product_id       = db.Column(db.Integer, db.ForeignKey('products.product_id'),         nullable=False)
    quantity         = db.Column(db.Integer,        nullable=False)
    price            = db.Column(db.Numeric(10, 2), nullable=False)
    subtotal         = db.Column(db.Numeric(10, 2), nullable=False)