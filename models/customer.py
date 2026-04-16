from models import db
from datetime import datetime
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy import case, literal


class Customer(db.Model):
    __tablename__ = 'customers'

    customer_id    = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # ── Name stored as separate columns ──────────────────────────────
    first_name     = db.Column(db.String(100), nullable=False, default='')
    middle_initial = db.Column(db.String(10),  nullable=True)
    last_name      = db.Column(db.String(100), nullable=False, default='')

    username       = db.Column(db.String(50),  unique=True, nullable=True)
    password       = db.Column(db.String(255), nullable=True)
    contact_number = db.Column(db.String(20))
    address        = db.Column(db.String(200))

    loyalty_points = db.Column(db.Integer, default=0)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

    # ── Relationships ─────────────────────────────────────────────────
    sales                = db.relationship('Sale',               backref='customer', lazy=True)
    delivery_orders      = db.relationship('DeliveryOrder',      backref='customer', lazy=True)
    loyalty_transactions = db.relationship('LoyaltyTransaction', backref='customer', lazy=True)

    # ── full_name hybrid property ─────────────────────────────────────
    @hybrid_property
    def full_name(self):
        """Instance level: assemble display name from the three columns."""
        parts = [self.first_name or '']
        if self.middle_initial:
            mi = self.middle_initial.strip('.').strip()
            if mi:
                parts.append(mi + '.')
        parts.append(self.last_name or '')
        return ' '.join(p for p in parts if p).strip()

    @full_name.setter
    def full_name(self, value):
        """
        Backward-compat setter: accept a plain 'First [M.] Last' string
        and split it into the three columns automatically.
        """
        if not value:
            self.first_name = ''
            self.last_name  = ''
            self.middle_initial = None
            return
        parts = value.strip().split()
        if len(parts) == 1:
            self.first_name     = parts[0]
            self.middle_initial = None
            self.last_name      = ''
        elif len(parts) == 2:
            self.first_name     = parts[0]
            self.middle_initial = None
            self.last_name      = parts[1]
        else:
            self.first_name     = parts[0]
            self.middle_initial = parts[1]          # e.g. "D" or "D."
            self.last_name      = ' '.join(parts[2:])

    @full_name.expression
    def full_name(cls):
        """
        SQL / class level: used by ORDER BY and filter().
        MariaDB-compatible — avoids TRIM(str, chars) which MariaDB rejects.

        Produces:
          CONCAT(
              first_name,
              CASE WHEN middle_initial IS NOT NULL AND middle_initial != ''
                   THEN CONCAT(' ', middle_initial, '.')
                   ELSE ' '
              END,
              last_name
          )

        middle_initial is stored raw (e.g. 'D' or 'D.') — the dot is always
        appended in SQL so display is consistent regardless of how it was saved.
        If you need to strip a trailing dot that was already stored, use
        REPLACE(middle_initial, '.', '') before the CONCAT — but keeping it
        simple is fine for ordering purposes.
        """
        mi_part = case(
            (
                (cls.middle_initial.isnot(None)) & (cls.middle_initial != ''),
                db.func.concat(
                    literal(' '),
                    # Use REPLACE to strip any existing dot before re-adding it,
                    # so 'D' and 'D.' both sort identically.
                    db.func.replace(cls.middle_initial, '.', ''),
                    literal('.')
                )
            ),
            else_=literal(' ')
        )

        return db.func.concat(
            db.func.coalesce(cls.first_name, literal('')),
            mi_part,
            db.func.coalesce(cls.last_name,  literal(''))
        )

    def __repr__(self):
        return f'<Customer {self.customer_id}: {self.full_name}>'
