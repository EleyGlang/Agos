from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

from models.user                import User
from models.customer            import Customer
from models.product             import Product
from models.inventory           import Inventory
from models.sale                import Sale
from models.sale_item           import SaleItem
from models.delivery_order      import DeliveryOrder
from models.delivery_item       import DeliveryItem
from models.expense             import Expense
from .loyalty_transaction       import LoyaltyTransaction
from models.activity_log        import ActivityLog
from models.return_model        import Return_Model
from models.return_item         import ReturnItem
from models.water_tank_log      import WaterTankLog
from models.watertank           import WaterTank