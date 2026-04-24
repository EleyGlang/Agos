from models import db
from datetime import datetime

class Service(db.Model):
    __tablename__ = 'services'
 
    service_id   = db.Column(db.Integer, primary_key=True, autoincrement=True)
    service_name = db.Column(db.String(120), nullable=False)
    price        = db.Column(db.Numeric(10, 2), nullable=False, default=0.00)
    unit         = db.Column(db.String(50), nullable=True)   # e.g. "per gallon"
    description  = db.Column(db.Text, nullable=True)
    is_active    = db.Column(db.Boolean, nullable=False, default=True)
    created_at   = db.Column(db.DateTime, default=db.func.now())
 
    def __repr__(self):
        return f'<Service {self.service_name}>'
 