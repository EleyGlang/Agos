from models import db
from datetime import datetime

class WaterTank(db.Model):
    """
    Single-row table that stores the current tank state.
    Capacity and level are in gallons.
    last_daily_refill_date tracks whether today's auto top-up
    has already been applied so we never double-count.
    """
    __tablename__ = 'water_tank'
 
    tank_id                = db.Column(db.Integer,  primary_key=True)
    level                  = db.Column(db.Float,    nullable=False, default=20.0)
    capacity               = db.Column(db.Float,    nullable=False, default=20.0)
    last_daily_refill_date = db.Column(db.Date,     nullable=True)
 