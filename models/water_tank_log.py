from models import db
from datetime import datetime


class WaterTankLog(db.Model):
    """
    Records every refill and usage event for the 20-gallon water tank.
    Current level = SUM(refills) − SUM(usage), capped at [0, TANK_CAPACITY].
    """
    __tablename__ = 'water_tank_log'

    id         = db.Column(db.Integer, primary_key=True, autoincrement=True)
    action     = db.Column(db.String(16), nullable=False)        # 'refill' | 'usage'
    gallons    = db.Column(db.Float,      nullable=False)
    note       = db.Column(db.String(255), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id', ondelete='SET NULL'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationship — lets you do log.user.first_name in templates
    user = db.relationship('User', backref=db.backref('tank_logs', lazy='dynamic'))

    def __repr__(self):
        return f'<WaterTankLog {self.action} {self.gallons}gal @ {self.created_at}>'
