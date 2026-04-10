from models import db
from datetime import datetime

class Customer(db.Model):
    __tablename__ = 'customers'

    customer_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    full_name = db.Column(db.String(200), nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    contact_number = db.Column(db.String(20))
    address = db.Column(db.String(200))

    loyalty_points = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sales = db.relationship('Sale', backref='customer', lazy=True)
    delivery_orders = db.relationship('DeliveryOrder', backref='customer', lazy=True)
    loyalty_transactions = db.relationship('LoyaltyTransaction', backref='customer', lazy=True)
