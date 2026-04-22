from models import db


class Product(db.Model):
    __tablename__ = 'products'

    product_id   = db.Column(db.Integer, primary_key=True, autoincrement=True)
    product_name = db.Column(db.String(100), nullable=False)
    price        = db.Column(db.Numeric(10, 2), nullable=False)
    unit         = db.Column(db.String(20))
    is_active    = db.Column(db.Boolean, default=True)

    # ── product_type ────────────────────────────────────────────────────────
    # 'standard' — physical product; owns an Inventory row for stock tracking
    # 'service'  — no physical stock (e.g. Gallon Refill service)
    # 'linked'   — stock mirrors another product (e.g. New Gallon mirrors
    #              Empty Gallon); no own Inventory row needed
    product_type = db.Column(db.String(20), nullable=False, default='standard')

    # Self-referential FK: only populated when product_type == 'linked'
    linked_product_id = db.Column(
        db.Integer,
        db.ForeignKey('products.product_id', ondelete='SET NULL'),
        nullable=True,
    )
    linked_product = db.relationship(
        'Product',
        foreign_keys=[linked_product_id],
        remote_side='Product.product_id',
        backref=db.backref('dependents', lazy='dynamic'),
    )
    # ────────────────────────────────────────────────────────────────────────

    sale_items     = db.relationship('SaleItem',     backref='product', lazy=True)
    delivery_items = db.relationship('DeliveryItem', backref='product', lazy=True)
    inventory      = db.relationship('Inventory',    backref='product', uselist=False)


def effective_stock(product):
    """
    Return the usable stock count for any product regardless of type.

      standard → product.inventory.quantity  (0 if no inventory row exists)
      service  → None  (stock concept does not apply)
      linked   → effective_stock of the linked product (one level deep)
    """
    if product.product_type == 'service':
        return None
    if product.product_type == 'linked':
        if product.linked_product:
            return effective_stock(product.linked_product)
        return 0
    # standard
    if product.inventory:
        return product.inventory.quantity
    return 0