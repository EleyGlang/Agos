from models import db
from datetime import datetime


class WaterTankLog(db.Model):
    """
    Audit trail for every tank change.
 
    action       : 'refill' | 'usage'
    source       : 'manual' | 'sale' | 'delivery' | 'daily'
    reference_id : sale_id or delivery_id when source is 'sale'/'delivery'
    level_after  : tank level (gallons) immediately after this entry — stored
                   so the table can display it accurately without re-computing
                   from the full log history.
    """
    __tablename__ = 'water_tank_log'
 
    log_id       = db.Column(db.Integer,     primary_key=True)
    action       = db.Column(db.String(20),  nullable=False)          # 'refill' | 'usage'
    gallons      = db.Column(db.Float,       nullable=False)
    level_after  = db.Column(db.Float,       nullable=True)
    note         = db.Column(db.String(255), nullable=True)
    source       = db.Column(db.String(20),  nullable=False, default='manual')
    reference_id = db.Column(db.Integer,     nullable=True)
    user_id      = db.Column(db.Integer,     db.ForeignKey('user.user_id'), nullable=True)
    created_at   = db.Column(db.DateTime,    default=datetime.now)
 
    user = db.relationship('User', backref=db.backref('water_tank_logs', lazy=True))


    def __repr__(self):
        return f'<WaterTankLog {self.action} {self.gallons}gal @ {self.created_at}>'
