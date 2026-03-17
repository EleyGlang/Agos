from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

from .user                import User
from .customer            import Customer
from .product             import Product       # ← must be before Inventory
from .inventory           import Inventory     # ← depends on Product
from .sale                import Sale
from .sale_item           import SaleItem
from .delivery_order      import DeliveryOrder
from .delivery_item       import DeliveryItem
from .expense             import Expense
from .loyalty_transaction import LoyaltyTransaction