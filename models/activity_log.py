from models import db
from datetime import datetime


class ActivityLog(db.Model):
    __tablename__ = 'activity_logs'

    log_id      = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    # Human-readable actor label (kept even if user is deleted)
    actor_name  = db.Column(db.String(200), nullable=False)
    actor_role  = db.Column(db.String(50),  nullable=False)
    # What happened
    action      = db.Column(db.String(100), nullable=False)   # e.g. 'CREATE_SALE'
    module      = db.Column(db.String(50),  nullable=False)   # e.g. 'Sales'
    description = db.Column(db.Text,        nullable=False)   # human sentence
    # Optional reference to the affected record
    target_type = db.Column(db.String(50))   # e.g. 'Customer'
    target_id   = db.Column(db.Integer)      # e.g. 42
    # Request metadata
    ip_address  = db.Column(db.String(45))
    created_at  = db.Column(db.DateTime, default=datetime.utcnow, index=True)
