from models import db
from datetime import datetime


class WaterTankLog(db.Model):
    __tablename__ = 'water_tank_log'

    id           = db.Column(db.Integer, primary_key=True)
    action       = db.Column(db.String(20), nullable=False)
    gallons      = db.Column(db.Float, nullable=False)
    level_after  = db.Column(db.Float, nullable=True)  # ✅ keep ONLY ONE
    note         = db.Column(db.String(255), nullable=True)
    source       = db.Column(db.String(20), nullable=False, default='manual')
    reference_id = db.Column(db.Integer, nullable=True)
    user_id      = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    created_at   = db.Column(db.DateTime, default=datetime.now)

    user = db.relationship('User', backref=db.backref('water_tank_logs', lazy=True))

    def __repr__(self):
        return f'<WaterTankLog {self.action} {self.gallons}gal @ {self.created_at}>'