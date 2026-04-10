from models import db
from datetime import datetime


class DeliveryOrder(db.Model):
    __tablename__ = 'delivery_orders'

    delivery_id   = db.Column(db.Integer, primary_key=True, autoincrement=True)
    customer_id   = db.Column(db.Integer, db.ForeignKey('customers.customer_id'), nullable=False)
    # nullable=True: customer-placed orders have no staff user_id
    user_id       = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    delivery_date = db.Column(db.Date, nullable=False)
    status        = db.Column(
        db.Enum('Pending', 'Confirmed', 'Out for Delivery', 'Delivered', 'Rejected'),
        default='Pending'
    )
    # Extra fields for customer-facing orders
    delivery_address = db.Column(db.Text, nullable=True)   # where to deliver
    preferred_time   = db.Column(db.String(50), nullable=True)  # e.g. "Morning (8AM–12PM)"
    notes            = db.Column(db.Text)
    total_amount     = db.Column(db.Numeric(10, 2), nullable=True)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)

    delivery_items = db.relationship(
        'DeliveryItem', backref='delivery_order', lazy=True, cascade='all, delete-orphan'
    )
