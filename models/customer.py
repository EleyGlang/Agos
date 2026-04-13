from models import db
from datetime import datetime
from sqlalchemy.ext.hybrid import hybrid_property


class Customer(db.Model):
    __tablename__ = 'customers'

    customer_id    = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # ── Split name fields ──────────────────────────────────────────────────
    first_name     = db.Column(db.String(100), nullable=False)
    middle_initial = db.Column(db.String(5),   nullable=True)   # e.g. "B" or "B."
    last_name      = db.Column(db.String(100), nullable=False)
    # ──────────────────────────────────────────────────────────────────────

    username        = db.Column(db.String(50),  unique=True, nullable=True)
    password        = db.Column(db.String(255), nullable=True)
    contact_number  = db.Column(db.String(20))
    address         = db.Column(db.String(200))

    loyalty_points  = db.Column(db.Integer, default=0)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    sales               = db.relationship('Sale',              backref='customer',  lazy=True)
    delivery_orders     = db.relationship('DeliveryOrder',     backref='customer',  lazy=True)
    loyalty_transactions = db.relationship('LoyaltyTransaction', backref='customer', lazy=True)

    # ── Computed full name (backward-compatible) ──────────────────────────
    @hybrid_property
    def full_name(self):
        """Returns 'First M. Last' or 'First Last' if no middle initial."""
        mi = self.middle_initial.strip('.').strip() if self.middle_initial else ''
        parts = [self.first_name]
        if mi:
            parts.append(mi.upper() + '.')
        parts.append(self.last_name)
        return ' '.join(parts)

    def __repr__(self):
        return f'<Customer {self.customer_id}: {self.first_name} {self.last_name}>'