from models import db
from datetime import datetime


class DeliveryOrder(db.Model):
    __tablename__ = 'delivery_orders'

    delivery_id   = db.Column(db.Integer, primary_key=True, autoincrement=True)
    customer_id   = db.Column(db.Integer, db.ForeignKey('customers.customer_id'), nullable=False)
    user_id       = db.Column(db.Integer, db.ForeignKey('users.user_id'),         nullable=False)
    delivery_date = db.Column(db.Date, nullable=False)
    status        = db.Column(db.Enum('Pending', 'Confirmed', 'Out for Delivery', 'Delivered', 'Rejected'), default='Pending' )
    notes      = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    delivery_items = db.relationship('DeliveryItem', backref='delivery_order', lazy=True, cascade='all, delete-orphan')