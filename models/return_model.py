from models import db
from datetime import datetime

class Return_Model(db.Model):
    __tablename__ = 'returns'

    return_id    = db.Column(db.Integer, primary_key=True)
    sale_id      = db.Column(db.Integer, db.ForeignKey('sales.sale_id'), nullable=False)
    user_id      = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    status       = db.Column(db.String(20), default='Pending')   # Pending / Approved / Rejected
    refund_amount= db.Column(db.Numeric(10,2), default=0)
    reason       = db.Column(db.String(100))
    notes        = db.Column(db.Text)
    reviewed_by  = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    reviewed_at  = db.Column(db.DateTime, nullable=True)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)

    sale         = db.relationship('Sale',   foreign_keys=[sale_id],    backref='returns')
    creator      = db.relationship('User',   foreign_keys=[user_id])
    reviewer     = db.relationship('User',   foreign_keys=[reviewed_by])
    return_items = db.relationship('ReturnItem', backref='return_order', cascade='all, delete-orphan')
