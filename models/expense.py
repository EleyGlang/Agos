from models import db
from datetime import datetime


class Expense(db.Model):
    __tablename__ = 'expenses'

    expense_id   = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id      = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    category     = db.Column(db.String(100), nullable=False)
    description  = db.Column(db.Text)
    amount       = db.Column(db.Numeric(10, 2), nullable=False)
    expense_date = db.Column(db.Date, nullable=False)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)