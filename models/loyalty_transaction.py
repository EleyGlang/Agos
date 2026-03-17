from models import db
from datetime import datetime


class LoyaltyTransaction(db.Model):
    __tablename__ = 'loyalty_transactions'

    loyalty_id       = db.Column(db.Integer, primary_key=True, autoincrement=True)
    customer_id      = db.Column(db.Integer, db.ForeignKey('customers.customer_id'), nullable=False)
    sale_id          = db.Column(db.Integer, db.ForeignKey('sales.sale_id'),         nullable=False)
    points_earned    = db.Column(db.Integer, nullable=False)
    transaction_date = db.Column(db.DateTime, default=datetime.utcnow)