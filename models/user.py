from models import db
from datetime import datetime
from sqlalchemy.ext.hybrid import hybrid_property


class User(db.Model):
    __tablename__ = 'users'

    user_id        = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # ── Split name fields ──────────────────────────────────────────────────
    first_name     = db.Column(db.String(100), nullable=False)
    middle_initial = db.Column(db.String(5),   nullable=True)   # e.g. "B" or "B."
    last_name      = db.Column(db.String(100), nullable=False)
    # ──────────────────────────────────────────────────────────────────────

    username   = db.Column(db.String(50),  unique=True, nullable=False)
    password   = db.Column(db.String(255), nullable=False)
    role       = db.Column(db.Enum('Super Admin', 'Admin', 'Operator'), nullable=False)
    status     = db.Column(db.Enum('Active', 'Inactive'), default='Active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sales      = db.relationship('Sale',          backref='operator', lazy=True)
    expenses   = db.relationship('Expense',       backref='operator', lazy=True)
    deliveries = db.relationship('DeliveryOrder', backref='operator', lazy=True)

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
        return f'<User {self.username} ({self.role})>'