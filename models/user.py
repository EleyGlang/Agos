from models import db
from datetime import datetime

class User(db.Model):
    __tablename__ = 'users'

    user_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    full_name = db.Column(db.String(200), nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)  # Changed from 50 to 255
    role = db.Column(db.Enum('Admin', 'Operator'), nullable=False)  # Changed 'Active' to 'Admin'
    status = db.Column(db.Enum('Active', 'Inactive'), default='Active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sales = db.relationship('Sale', backref='operator', lazy=True)
    expenses = db.relationship('Expense', backref='operator', lazy=True)
    deliveries = db.relationship('DeliveryOrder', backref='operator', lazy=True)