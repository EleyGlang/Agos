from models import db
from datetime import datetime

class Sale(db.Model):
    __tablename__ = 'sales'

    sale_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.customer_id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    sale_type = db.Column(db.Enum('Walk-in', 'Delivery'), nullable=False)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    sale_date = db.Column(db.DateTime, default=datetime.utcnow)

    sale_items = db.relationship('SaleItem', backref='sales', lazy=True, cascade='all, delete-orphan')
    loyalty_transactions = db.relationship('LoyaltyTransaction', backref='sales', lazy=True)
    
