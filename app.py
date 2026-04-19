import os
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from functools import wraps
from datetime import datetime, timedelta
from flask_migrate import Migrate

from models import (
         db, User, Customer, Product, Inventory,
         Sale, SaleItem, DeliveryOrder, DeliveryItem,
         Expense, LoyaltyTransaction, ActivityLog,
         Return_Model as Return, ReturnItem, WaterTankLog     )

from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__, static_folder='static')
app.secret_key = os.environ.get('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
db.init_app(app)
migrate = Migrate(app, db)


# ══════════════════════════════════════════════════════
#  ROLE HELPERS
# ══════════════════════════════════════════════════════

def is_super_admin():
    return session.get('role') == 'Super Admin'

def is_admin_or_above():
    return session.get("role") in ("Super Admin", "Admin")

def user_full_name(user):
    parts = [user.first_name or ""]
    if user.middle_initial:
        mi = user.middle_initial.rstrip(".")
        if mi:
            parts.append(mi + ".")
    parts.append(user.last_name or "")
    return " ".join(p for p in parts if p)


# ══════════════════════════════════════════════════════
#  AUDIT LOG HELPER
# ══════════════════════════════════════════════════════

def log_activity(action, module, description, target_type=None, target_id=None):
    try:
        entry = ActivityLog(
            user_id=session.get('user_id'),
            actor_name=session.get('full_name') or session.get('customer_name') or 'System',
            actor_role=session.get('role') or 'Customer',
            action=action, module=module, description=description,
            target_type=target_type, target_id=target_id,
            ip_address=request.remote_addr,
        )
        db.session.add(entry)
    except Exception:
        pass


# ══════════════════════════════════════════════════════
#  DECORATORS
# ══════════════════════════════════════════════════════

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to continue.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to continue.', 'error')
            return redirect(url_for('login'))
        if not is_admin_or_above():
            flash('Admin access required.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated

def super_admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to continue.', 'error')
            return redirect(url_for('login'))
        if not is_super_admin():
            flash('Super Admin access required.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated


# ══════════════════════════════════════════════════════
#  CLI SEED
# ══════════════════════════════════════════════════════

@app.cli.command('seed-super-admin')
def seed_super_admin():
    if User.query.filter_by(role='Super Admin').first():
        print('Super Admin already exists.')
        return
    db.session.add(User(
        first_name='Super', last_name='Administrator', username='superadmin',
        password=generate_password_hash('superadmin123'),
        role='Super Admin', status='Active',
    ))
    db.session.commit()
    print('Done. username=superadmin  password=superadmin123  — change it immediately!')


# ══════════════════════════════════════════════════════
#  AUTH
# ══════════════════════════════════════════════════════

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    if 'customer_id' in session:
        return redirect(url_for('customer_dashboard'))
    return redirect(url_for('landing'))

def _landing_content_path():
    return os.path.join(app.root_path, 'landing_content.json')

def _load_landing_content():
    path = _landing_content_path()
    if os.path.exists(path):
        import json
        with open(path) as f:
            return json.load(f)
    return {}

@app.route('/landing')
def landing():
    if 'customer_id' in session:
        return redirect(url_for('customer_dashboard'))
    if 'user_id' in session and not is_admin_or_above():
        return redirect(url_for('dashboard'))
    content  = _load_landing_content()
    can_edit = 'user_id' in session and is_admin_or_above()
    return render_template('landing.html', content=content, can_edit=can_edit)

@app.route('/landing/save', methods=['POST'])
@login_required
@admin_required
def landing_save():
    import json
    fields = {
        'hero_tagline':    request.form.get('hero_tagline', '').strip(),
        'hero_headline':   request.form.get('hero_headline', '').strip(),
        'hero_subheadline':request.form.get('hero_subheadline', '').strip(),
        'hero_desc':       request.form.get('hero_desc', '').strip(),
        'hero_cta_text':   request.form.get('hero_cta_text', '').strip(),
        'features_title':  request.form.get('features_title', '').strip(),
        'features_desc':   request.form.get('features_desc', '').strip(),
        'about_title':     request.form.get('about_title', '').strip(),
        'about_body':      request.form.get('about_body', '').strip(),
        'contact_email':   request.form.get('contact_email', '').strip(),
        'contact_phone':   request.form.get('contact_phone', '').strip(),
        'contact_address': request.form.get('contact_address', '').strip(),
        'footer_tagline':  request.form.get('footer_tagline', '').strip(),
        'features': [
            {'emoji': request.form.get(f'feature_emoji_{i}','').strip(),
             'title': request.form.get(f'feature_title_{i}','').strip(),
             'desc':  request.form.get(f'feature_desc_{i}','').strip()}
            for i in range(int(request.form.get('feature_count', 0)))
            if request.form.get(f'feature_title_{i}','').strip()
        ],
        'stats': [
            {'num':   request.form.get(f'stat_num_{i}','').strip(),
             'label': request.form.get(f'stat_label_{i}','').strip()}
            for i in range(3)
        ],
    }
    path = _landing_content_path()
    with open(path, 'w') as f:
        json.dump(fields, f, indent=2)
    log_activity('EDIT_LANDING', 'Landing', 'Landing page content updated')
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
    flash('Landing page updated successfully!', 'success')
    return redirect(url_for('landing'))

@app.route('/landing/editor')
@login_required
@admin_required
def landing_editor():
    content = _load_landing_content()
    return render_template('landing_editor.html', content=content)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    if 'customer_id' in session:
        return redirect(url_for('customer_dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        user = User.query.filter_by(username=username).first()
        if user and user.password and check_password_hash(user.password, password):
            session['user_id'] = user.user_id
            session['full_name'] = user.full_name
            session['role'] = user.role
            return redirect(url_for('dashboard'))

        customer = Customer.query.filter_by(username=username).first()
        if customer and customer.password and check_password_hash(customer.password, password):
            session['customer_id'] = customer.customer_id
            session['customer_name'] = customer.full_name
            return redirect(url_for('customer_dashboard'))

        flash('Invalid username or password.', 'error')

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    log_activity('LOGOUT', 'Auth', f"{session.get('full_name')} logged out")
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))


# ══════════════════════════════════════════════════════
#  DASHBOARD
# ══════════════════════════════════════════════════════

@app.route('/dashboard')
@login_required
def dashboard():
    from sqlalchemy import func
    today = datetime.now().date()
    month = datetime.now().strftime('%Y-%m')

    today_sales = db.session.query(
        func.coalesce(func.sum(Sale.total_amount), 0)
    ).filter(func.date(Sale.sale_date) == today).scalar()

    pending_deliveries = DeliveryOrder.query.filter_by(status='Pending').count()
    total_customers    = Customer.query.count()
    recent_sales       = Sale.query.order_by(Sale.sale_date.desc()).limit(8).all()
    inventory_items    = Inventory.query.all()
    low_stock_items    = sum(1 for i in inventory_items if i.quantity <= (i.minimum_stock or 10))

    sales_trend_labels, sales_trend_values = [], []
    for i in range(6, -1, -1):
        day = (datetime.now() - timedelta(days=i)).date()
        total = db.session.query(
            func.coalesce(func.sum(Sale.total_amount), 0)
        ).filter(func.date(Sale.sale_date) == day).scalar()
        sales_trend_labels.append(day.strftime('%b %d'))
        sales_trend_values.append(float(total))

    if is_admin_or_above():
        monthly_revenue = db.session.query(
            func.coalesce(func.sum(Sale.total_amount), 0)
        ).filter(func.date_format(Sale.sale_date, '%Y-%m') == month).scalar()
        monthly_expenses = db.session.query(
            func.coalesce(func.sum(Expense.amount), 0)
        ).filter(func.date_format(Expense.expense_date, '%Y-%m') == month).scalar()
        net_profit  = monthly_revenue - monthly_expenses
        total_staff = User.query.filter(User.role.in_(['Admin', 'Operator'])).count()
        walkin_count = Sale.query.filter(
            Sale.sale_type == 'Walk-in',
            func.date_format(Sale.sale_date, '%Y-%m') == month
        ).count()
        delivery_count = Sale.query.filter(
            Sale.sale_type == 'Delivery',
            func.date_format(Sale.sale_date, '%Y-%m') == month
        ).count()
        top_products_q = db.session.query(
            Product.product_name, func.sum(SaleItem.quantity).label('qty'),
        ).join(SaleItem, SaleItem.product_id == Product.product_id)\
         .join(Sale, Sale.sale_id == SaleItem.sale_id)\
         .filter(func.date_format(Sale.sale_date, '%Y-%m') == month)\
         .group_by(Product.product_id)\
         .order_by(func.sum(SaleItem.quantity).desc()).limit(5).all()
        top_product_names = [r[0] for r in top_products_q]
        top_product_qtys  = [int(r[1]) for r in top_products_q]
        expense_by_category = db.session.query(
            Expense.category, func.sum(Expense.amount)
        ).filter(func.date_format(Expense.expense_date, '%Y-%m') == month)\
         .group_by(Expense.category).all()

        user_role_counts = user_role_labels = user_role_values = []
        total_users = 0
        recent_activity = []
        if is_super_admin():
            role_counts = db.session.query(
                User.role, func.count(User.user_id)
            ).group_by(User.role).all()
            user_role_counts = role_counts
            user_role_labels = [r[0] for r in role_counts]
            user_role_values = [r[1] for r in role_counts]
            total_users      = sum(r[1] for r in role_counts)
            recent_activity  = ActivityLog.query.order_by(
                ActivityLog.created_at.desc()).limit(8).all()

        return render_template('dashboard_admin.html',
            today_sales=today_sales, monthly_revenue=monthly_revenue,
            monthly_expenses=monthly_expenses, net_profit=net_profit,
            pending_deliveries=pending_deliveries, total_customers=total_customers,
            low_stock_items=low_stock_items, recent_sales=recent_sales,
            total_staff=total_staff, inventory_items=inventory_items,
            sales_trend_labels=sales_trend_labels, sales_trend_values=sales_trend_values,
            walkin_count=walkin_count, delivery_count=delivery_count,
            top_product_names=top_product_names, top_product_qtys=top_product_qtys,
            expense_by_category=expense_by_category,
            user_role_counts=user_role_counts, user_role_labels=user_role_labels,
            user_role_values=user_role_values, total_users=total_users,
            recent_activity=recent_activity, active_page='dashboard')

    delivered_today = DeliveryOrder.query.filter(
        DeliveryOrder.status == 'Delivered',
        func.date(DeliveryOrder.created_at) == today
    ).count()
    pending_delivery_list = DeliveryOrder.query.filter_by(status='Pending')\
        .order_by(DeliveryOrder.delivery_date).limit(6).all()
    walkin_today   = Sale.query.filter(Sale.sale_type == 'Walk-in',   func.date(Sale.sale_date) == today).count()
    delivery_today = Sale.query.filter(Sale.sale_type == 'Delivery',  func.date(Sale.sale_date) == today).count()

    return render_template('dashboard_operator.html',
        today_sales=today_sales, pending_deliveries=pending_deliveries,
        total_customers=total_customers, recent_sales=recent_sales,
        pending_delivery_list=pending_delivery_list, delivered_today=delivered_today,
        low_stock_items=low_stock_items, inventory_items=inventory_items,
        sales_trend_labels=sales_trend_labels, sales_trend_values=sales_trend_values,
        walkin_today=walkin_today, delivery_today=delivery_today, active_page='dashboard')


# ══════════════════════════════════════════════════════
#  API: chart data
# ══════════════════════════════════════════════════════

@app.route('/api/dashboard-stats')
@login_required
def api_dashboard_stats():
    from sqlalchemy import func
    daily = []
    for i in range(6, -1, -1):
        day   = (datetime.now() - timedelta(days=i)).date()
        total = db.session.query(func.coalesce(func.sum(Sale.total_amount), 0)).filter(func.date(Sale.sale_date) == day).scalar()
        daily.append({'date': day.strftime('%b %d'), 'amount': float(total)})
    monthly = []
    for i in range(5, -1, -1):
        ref   = (datetime.now().replace(day=1) - timedelta(days=i * 28)).replace(day=1)
        month = ref.strftime('%Y-%m')
        rev   = db.session.query(func.coalesce(func.sum(Sale.total_amount), 0)).filter(func.date_format(Sale.sale_date, '%Y-%m') == month).scalar()
        exp   = db.session.query(func.coalesce(func.sum(Expense.amount), 0)).filter(func.date_format(Expense.expense_date, '%Y-%m') == month).scalar()
        monthly.append({'month': ref.strftime('%b %Y'), 'revenue': float(rev), 'expenses': float(exp)})
    cur      = datetime.now().strftime('%Y-%m')
    walkin   = db.session.query(func.coalesce(func.sum(Sale.total_amount), 0)).filter(Sale.sale_type == 'Walk-in',  func.date_format(Sale.sale_date, '%Y-%m') == cur).scalar()
    delivery = db.session.query(func.coalesce(func.sum(Sale.total_amount), 0)).filter(Sale.sale_type == 'Delivery', func.date_format(Sale.sale_date, '%Y-%m') == cur).scalar()
    return jsonify({'daily': daily, 'monthly': monthly,
                    'sale_type': {'walkin': float(walkin), 'delivery': float(delivery)}})


# ══════════════════════════════════════════════════════
#  PRODUCT MANAGEMENT
# ══════════════════════════════════════════════════════

@app.route('/products')
@login_required
def products():
    return render_template('products.html',
        products=Product.query.order_by(Product.product_name).all(),
        active_page='products')

@app.route('/products/new', methods=['POST'])
@login_required
@admin_required
def new_product():
    name = request.form.get('product_name', '').strip()
    unit = request.form.get('unit', '').strip()
    try:
        price     = float(request.form.get('price', 0))
        min_stock = int(request.form.get('minimum_stock', 10))
        assert price > 0
    except (ValueError, AssertionError):
        flash('Valid product name and positive price are required.', 'error')
        return redirect(url_for('products'))
    product = Product(product_name=name, price=price, unit=unit, is_active=True)
    db.session.add(product)
    db.session.flush()
    db.session.add(Inventory(product_id=product.product_id, quantity=0, minimum_stock=min_stock))
    log_activity('CREATE_PRODUCT', 'Products', f'"{name}" created at ₱{price:.2f}', 'Product', product.product_id)
    try:
        db.session.commit()
        flash(f'Product "{name}" added!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')
    return redirect(url_for('products'))

@app.route('/products/<int:product_id>/edit', methods=['POST'])
@login_required
@admin_required
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)
    product.product_name = request.form.get('product_name', product.product_name).strip()
    product.unit         = request.form.get('unit', product.unit or '').strip()
    try:
        new_price = float(request.form.get('price', product.price))
        assert new_price > 0
        product.price = new_price
        inv = Inventory.query.filter_by(product_id=product_id).first()
        if inv:
            inv.minimum_stock = int(request.form.get('minimum_stock', inv.minimum_stock))
    except (ValueError, AssertionError):
        flash('Price must be a positive number.', 'error')
        return redirect(url_for('products'))
    log_activity('EDIT_PRODUCT', 'Products', f'"{product.product_name}" updated', 'Product', product_id)
    try:
        db.session.commit()
        flash('Product updated!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')
    return redirect(url_for('products'))

@app.route('/products/<int:product_id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_product(product_id):
    product           = Product.query.get_or_404(product_id)
    product.is_active = not product.is_active
    label             = 'activated' if product.is_active else 'deactivated'
    log_activity('TOGGLE_PRODUCT', 'Products', f'"{product.product_name}" {label}', 'Product', product_id)
    try:
        db.session.commit()
        flash(f'"{product.product_name}" {label}.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')
    return redirect(url_for('products'))

@app.route('/products/<int:product_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    name    = product.product_name

    sale_uses     = SaleItem.query.filter_by(product_id=product_id).count()
    delivery_uses = DeliveryItem.query.filter_by(product_id=product_id).count()
    has_history   = (sale_uses + delivery_uses) > 0

    if has_history and not is_super_admin():
        flash(
            f'"{name}" has existing transaction records. '
            f'Admins can only deactivate it. Ask a Super Admin to force-delete.',
            'error'
        )
        return redirect(url_for('products'))

    log_activity('DELETE_PRODUCT', 'Products',
                 f'"{name}" permanently deleted (sale refs: {sale_uses}, delivery refs: {delivery_uses})',
                 'Product', product_id)
    try:
        inv = Inventory.query.filter_by(product_id=product_id).first()
        if inv:
            db.session.delete(inv)
        db.session.flush()
        db.session.delete(product)
        db.session.commit()
        flash(f'Product "{name}" permanently deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting product: {str(e)}', 'error')
    return redirect(url_for('products'))


# ══════════════════════════════════════════════════════
#  SALES
# ══════════════════════════════════════════════════════

@app.route('/sales')
@login_required
def sales():
    return render_template('sales.html',
        sales=Sale.query.order_by(Sale.sale_date.desc()).all(),
        customers=Customer.query.order_by(Customer.full_name).all(),
        products=Product.query.filter_by(is_active=True).order_by(Product.product_name).all(),
        active_page='sales')

@app.route('/sales/new', methods=['POST'])
@login_required
def new_sale():
    customer_id = request.form.get('customer_id') or None
    sale_type   = request.form.get('sale_type', 'Walk-in')
    if sale_type == 'Delivery' and not customer_id:
        flash('Delivery sales require a customer.', 'error')
        return redirect(url_for('sales'))
    product_ids = request.form.getlist('product_id[]')
    quantities  = request.form.getlist('quantity[]')
    if customer_id == 'new':
        new_name    = request.form.get('new_customer_name', '').strip()
        new_number  = request.form.get('new_customer_number', '').strip()
        new_address = request.form.get('new_customer_address', '').strip()
        if not new_name:
            flash('Customer name is required.', 'error')
            return redirect(url_for('sales'))
        if new_number and (not new_number.isdigit() or len(new_number) != 11):
            flash('Contact number must be exactly 11 digits.', 'error')
            return redirect(url_for('sales'))
        nc = Customer(full_name=new_name, contact_number=new_number, address=new_address)
        db.session.add(nc)
        db.session.flush()
        customer_id = nc.customer_id
    total_amount        = 0.0
    items_with_products = []
    for pid, qty_str in zip(product_ids, quantities):
        product  = Product.query.get(int(pid))
        quantity = int(qty_str)
        if not product:
            continue
        subtotal = float(product.price) * quantity
        total_amount += subtotal
        items_with_products.append((
            SaleItem(product_id=int(pid), quantity=quantity, price=product.price, subtotal=subtotal),
            product
        ))
    if customer_id:
        customer = Customer.query.get(customer_id)
        if customer:
            total_refills = sum(i.quantity for i, p in items_with_products if 'refill' in p.product_name.lower())
            if customer.loyalty_points > 0 and total_refills > 0:
                refill_total      = sum(i.subtotal for i, p in items_with_products if 'refill' in p.product_name.lower())
                free_used         = min(customer.loyalty_points, total_refills)
                total_amount     -= (refill_total / total_refills) * free_used
                customer.loyalty_points -= free_used
                remaining_refills = total_refills - free_used
            else:
                remaining_refills = total_refills
            if remaining_refills > 0:
                new_pts = remaining_refills // 10
                if new_pts > 0:
                    customer.loyalty_points += new_pts
    sale = Sale(user_id=session['user_id'], customer_id=customer_id,
                sale_type=sale_type, total_amount=total_amount, sale_date=datetime.now())
    db.session.add(sale)
    db.session.flush()
    for sale_item, product in items_with_products:
        sale_item.sale_id = sale.sale_id
        db.session.add(sale_item)
        inv = Inventory.query.filter_by(product_id=product.product_id).first()
        if inv:
            inv.quantity = max(0, inv.quantity - sale_item.quantity)
    log_activity('CREATE_SALE', 'Sales', f'{sale_type} sale — ₱{total_amount:.2f}', 'Sale', sale.sale_id)
    try:
        db.session.commit()
        flash('Sale recorded!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')
    return redirect(url_for('sales'))


# ══════════════════════════════════════════════════════
#  USER MANAGEMENT
# ══════════════════════════════════════════════════════

@app.route('/user_management')
@login_required
@admin_required
def user_management():
    users = User.query.order_by(User.created_at.desc()).all() if is_super_admin() \
            else User.query.filter_by(role='Operator').order_by(User.created_at.desc()).all()
    customers = Customer.query.order_by(Customer.full_name).all()
    return render_template('users.html',
        users=users, customers=customers,
        is_super_admin=is_super_admin(),
        active_page='user_management')

@app.route('/admin/users', methods=['POST'])
@login_required
@admin_required
def create_user():
    first_name     = request.form.get('first_name', '').strip()
    middle_initial = request.form.get('middle_initial', '').strip()
    last_name      = request.form.get('last_name', '').strip()
    if first_name and last_name:
        parts = [first_name]
        if middle_initial:
            parts.append(middle_initial.rstrip('.') + '.')
        parts.append(last_name)
        full_name = ' '.join(parts)
    else:
        full_name = request.form.get('full_name', '').strip()
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    role     = request.form.get('role', 'Operator')
    if role == 'Customer':
        flash('Use the Customer Account form to create customer accounts.', 'error')
        return redirect(url_for('user_management'))
    if role == 'Admin' and not is_super_admin():
        flash('Only Super Admin can create Admin accounts.', 'error')
        return redirect(url_for('user_management'))
    if role == 'Super Admin':
        flash('Super Admin accounts cannot be created here.', 'error')
        return redirect(url_for('user_management'))
    if not full_name:
        flash('Full name is required.', 'error')
        return redirect(url_for('user_management'))
    if User.query.filter_by(username=username).first():
        flash('Username already exists.', 'error')
        return redirect(url_for('user_management'))
    if len(password) < 8:
        flash('Password must be at least 8 characters.', 'error')
        return redirect(url_for('user_management'))
    new_user = User(
        first_name=first_name, middle_initial=middle_initial, last_name=last_name,
        username=username, password=generate_password_hash(password),
        role=role, status='Active'
    )
    db.session.add(new_user)
    db.session.flush()
    log_activity('CREATE_USER', 'Users',
                 f'Account created for {full_name} (@{username}) as {role}', 'User', new_user.user_id)
    try:
        db.session.commit()
        flash(f'Account for {full_name} created!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')
    return redirect(url_for('user_management'))

@app.route('/admin/users/<int:user_id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_user_status(user_id):
    user = User.query.get_or_404(user_id)
    if user_id == session['user_id']:
        flash('You cannot deactivate your own account.', 'error')
        return redirect(url_for('user_management'))
    if user.role == 'Super Admin':
        flash('Super Admin accounts cannot be deactivated.', 'error')
        return redirect(url_for('user_management'))
    if not is_super_admin() and user.role == 'Admin':
        flash('Only Super Admin can deactivate Admin accounts.', 'error')
        return redirect(url_for('user_management'))
    user.status = 'Inactive' if user.status == 'Active' else 'Active'
    log_activity('TOGGLE_USER', 'Users', f'@{user.username} set to {user.status}', 'User', user_id)
    try:
        db.session.commit()
        flash(f'@{user.username} is now {user.status}.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')
    # Return to profile if request came from there
    referrer = request.referrer or ''
    if 'profile' in referrer:
        return redirect(url_for('profile'))
    return redirect(url_for('user_management'))

@app.route('/admin/users/<int:user_id>/reset-password', methods=['POST'])
@login_required
@super_admin_required
def reset_user_password(user_id):
    user         = User.query.get_or_404(user_id)
    new_password = request.form.get('new_password', '').strip()
    if len(new_password) < 8:
        flash('Password must be at least 8 characters.', 'error')
        return redirect(url_for('profile'))
    user.password = generate_password_hash(new_password)
    log_activity('RESET_PASSWORD', 'Users', f'Password reset for @{user.username}', 'User', user_id)
    try:
        db.session.commit()
        flash(f'Password for @{user.username} reset.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')
    referrer = request.referrer or ''
    if 'profile' in referrer:
        return redirect(url_for('profile'))
    return redirect(url_for('user_management'))

@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@login_required
@super_admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.user_id == session['user_id'] or user.role == 'Super Admin':
        flash('Cannot delete this account.', 'error')
        return redirect(url_for('user_management'))
    log_activity('DELETE_USER', 'Users',
                 f'{user_full_name(user)} (@{user.username}) deleted', 'User', user_id)
    try:
        db.session.delete(user)
        db.session.commit()
        flash(f'Account for {user_full_name(user)} deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')
    return redirect(url_for('user_management'))

@app.route('/change-password', methods=['POST'])
@login_required
def change_password():
    user       = User.query.get(session['user_id'])
    current_pw = request.form.get('current_password', '').strip()
    new_pw     = request.form.get('new_password', '').strip()
    confirm_pw = request.form.get('confirm_password', '').strip()
    if not check_password_hash(user.password, current_pw):
        flash('Current password is incorrect.', 'error')
        return redirect(url_for('user_management'))
    if len(new_pw) < 8:
        flash('New password must be at least 8 characters.', 'error')
        return redirect(url_for('user_management'))
    if new_pw != confirm_pw:
        flash('Passwords do not match.', 'error')
        return redirect(url_for('user_management'))
    user.password = generate_password_hash(new_pw)
    log_activity('CHANGE_PASSWORD', 'Users', 'User changed own password')
    try:
        db.session.commit()
        flash('Password changed!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')
    return redirect(url_for('user_management'))


# ══════════════════════════════════════════════════════
#  STAFF PROFILE  (Admin / Super Admin / Operator)
# ══════════════════════════════════════════════════════

@app.route('/profile')
@login_required
def profile():
    """
    Unified profile page for all staff roles.
    Super Admin → sees Admins + Operators + Customers in management section.
    Admin       → sees Operators + Customers.
    Operator    → sees only own profile (no management section).
    """
    user = User.query.get_or_404(session['user_id'])

    # Own stats
    sales_count     = Sale.query.filter_by(user_id=user.user_id).count()
    recent_activity = ActivityLog.query.filter_by(
        user_id=user.user_id
    ).order_by(ActivityLog.created_at.desc()).limit(8).all()

    # Management data (Admin / Super Admin)
    admin_users      = []
    operator_users   = []
    managed_customers = []
    managed_users_count = 0

    if is_super_admin():
        admin_users    = User.query.filter_by(role='Admin').order_by(User.created_at.desc()).all()
        operator_users = User.query.filter_by(role='Operator').order_by(User.created_at.desc()).all()
        managed_customers = Customer.query.order_by(Customer.full_name).all()
        managed_users_count = len(admin_users) + len(operator_users)
    elif is_admin_or_above():
        operator_users = User.query.filter_by(role='Operator').order_by(User.created_at.desc()).all()
        managed_customers = Customer.query.order_by(Customer.full_name).all()
        managed_users_count = len(operator_users)

    return render_template('profile.html',
        user=user,
        sales_count=sales_count,
        recent_activity=recent_activity,
        admin_users=admin_users,
        operator_users=operator_users,
        managed_customers=managed_customers,
        managed_users_count=managed_users_count,
        active_page='profile'
    )


@app.route('/profile/update', methods=['POST'])
@login_required
def profile_update():
    """Update own profile info or password."""
    user      = User.query.get_or_404(session['user_id'])
    form_type = request.form.get('form_type')

    if form_type == 'info':
        import re
        first_name     = request.form.get('first_name', '').strip()
        middle_initial = request.form.get('middle_initial', '').strip()
        last_name      = request.form.get('last_name', '').strip()

        if not first_name or not re.match(r'^[A-Za-z\s]+$', first_name):
            flash('First name is required (letters only).', 'error')
            return redirect(url_for('profile'))
        if not last_name or not re.match(r'^[A-Za-z\s]+$', last_name):
            flash('Last name is required (letters only).', 'error')
            return redirect(url_for('profile'))
        if middle_initial and not re.match(r'^[A-Za-z]\.?$', middle_initial):
            flash('Middle initial must be a single letter.', 'error')
            return redirect(url_for('profile'))

        parts = [first_name]
        if middle_initial:
            parts.append(middle_initial.rstrip('.') + '.')
        parts.append(last_name)
        full_name = ' '.join(parts)

        user.first_name     = first_name
        user.middle_initial = middle_initial.rstrip('.') if middle_initial else None
        user.last_name      = last_name
        # Update full_name if it's a stored column; harmless if it's a property
        try:
            user.full_name = full_name
        except AttributeError:
            pass
        session['full_name'] = full_name

        log_activity('EDIT_PROFILE', 'Profile',
                     f'{full_name} updated their profile info', 'User', user.user_id)
        try:
            db.session.commit()
            flash('Profile updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'error')

    elif form_type == 'password':
        current_password = request.form.get('current_password', '')
        new_password     = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not check_password_hash(user.password, current_password):
            flash('Current password is incorrect.', 'error')
            return redirect(url_for('profile'))
        if len(new_password) < 8:
            flash('New password must be at least 8 characters.', 'error')
            return redirect(url_for('profile'))
        if new_password != confirm_password:
            flash('New passwords do not match.', 'error')
            return redirect(url_for('profile'))

        user.password = generate_password_hash(new_password)
        log_activity('CHANGE_PASSWORD', 'Profile',
                     f'{user.full_name} changed their own password', 'User', user.user_id)
        try:
            db.session.commit()
            flash('Password updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating password: {str(e)}', 'error')
    else:
        flash('Invalid request.', 'error')

    return redirect(url_for('profile'))


@app.route('/admin/users/<int:user_id>/update-info', methods=['POST'])
@login_required
@admin_required
def admin_update_user_info(user_id):
    """
    Admin / Super Admin can update name fields for staff below them.
    Super Admin → can edit Admins and Operators.
    Admin       → can only edit Operators.
    """
    import re
    target = User.query.get_or_404(user_id)

    # Protect Super Admin accounts from any modification
    if target.role == 'Super Admin':
        flash('Super Admin accounts cannot be modified.', 'error')
        return redirect(url_for('profile'))
    # Admin cannot touch other Admins
    if target.role == 'Admin' and not is_super_admin():
        flash('Only Super Admin can modify Admin accounts.', 'error')
        return redirect(url_for('profile'))
    # Nobody can self-edit via this endpoint (use /profile/update instead)
    if target.user_id == session['user_id']:
        flash('Use the profile form to update your own information.', 'error')
        return redirect(url_for('profile'))

    first_name     = request.form.get('first_name', '').strip()
    middle_initial = request.form.get('middle_initial', '').strip()
    last_name      = request.form.get('last_name', '').strip()

    if not first_name or not re.match(r'^[A-Za-z\s]+$', first_name):
        flash('First name is required (letters only).', 'error')
        return redirect(url_for('profile'))
    if not last_name or not re.match(r'^[A-Za-z\s]+$', last_name):
        flash('Last name is required (letters only).', 'error')
        return redirect(url_for('profile'))
    if middle_initial and not re.match(r'^[A-Za-z]\.?$', middle_initial):
        flash('Middle initial must be a single letter.', 'error')
        return redirect(url_for('profile'))

    parts = [first_name]
    if middle_initial:
        parts.append(middle_initial.rstrip('.') + '.')
    parts.append(last_name)
    full_name = ' '.join(parts)

    target.first_name     = first_name
    target.middle_initial = middle_initial.rstrip('.') if middle_initial else None
    target.last_name      = last_name
    try:
        target.full_name = full_name
    except AttributeError:
        pass

    log_activity('EDIT_USER_INFO', 'Profile',
                 f'Updated name for {full_name} (@{target.username}) [{target.role}]',
                 'User', user_id)
    try:
        db.session.commit()
        flash(f'Profile for {full_name} updated successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')

    return redirect(url_for('profile'))


@app.route('/admin/customers/<int:customer_id>/update-info', methods=['POST'])
@login_required
@admin_required
def admin_update_customer_info(customer_id):
    """Admin / Super Admin can update a customer's name, phone, and address."""
    import re
    customer = Customer.query.get_or_404(customer_id)

    first_name     = request.form.get('first_name', '').strip()
    middle_initial = request.form.get('middle_initial', '').strip()
    last_name      = request.form.get('last_name', '').strip()
    contact        = request.form.get('contact_number', '').strip()
    address        = request.form.get('address', '').strip()

    if not first_name:
        flash('First name is required.', 'error')
        return redirect(url_for('profile'))
    if not last_name:
        flash('Last name is required.', 'error')
        return redirect(url_for('profile'))
    if contact and (not contact.isdigit() or len(contact) != 11):
        flash('Phone number must be exactly 11 digits.', 'error')
        return redirect(url_for('profile'))

    parts = [first_name]
    if middle_initial:
        parts.append(middle_initial.rstrip('.') + '.')
    parts.append(last_name)
    full_name = ' '.join(parts)

    customer.first_name     = first_name
    customer.middle_initial = middle_initial.rstrip('.') if middle_initial else None
    customer.last_name      = last_name
    customer.full_name      = full_name
    if contact:
        customer.contact_number = contact
    if address:
        customer.address = address

    log_activity('EDIT_CUSTOMER_INFO', 'Profile',
                 f'Updated customer info for {full_name} (ID:{customer_id})',
                 'Customer', customer_id)
    try:
        db.session.commit()
        flash(f'Customer {full_name} updated successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')

    return redirect(url_for('profile'))


@app.route('/admin/customers/<int:customer_id>/reset-password', methods=['POST'])
@login_required
@admin_required
def admin_reset_customer_password(customer_id):
    """Admin / Super Admin can reset a customer's portal password."""
    customer     = Customer.query.get_or_404(customer_id)
    new_password = request.form.get('new_password', '').strip()

    if not customer.username:
        flash('This customer does not have a portal account.', 'error')
        return redirect(url_for('profile'))
    if len(new_password) < 8:
        flash('Password must be at least 8 characters.', 'error')
        return redirect(url_for('profile'))

    customer.password = generate_password_hash(new_password)
    log_activity('RESET_CUSTOMER_PASSWORD', 'Profile',
                 f'Password reset for customer {customer.full_name} (@{customer.username})',
                 'Customer', customer_id)
    try:
        db.session.commit()
        flash(f'Password for {customer.full_name} has been reset.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')

    return redirect(url_for('profile'))


# ══════════════════════════════════════════════════════
#  ACTIVITY LOG
# ══════════════════════════════════════════════════════

@app.route('/activity-log')
@login_required
@admin_required
def activity_log():
    page     = request.args.get('page', 1, type=int)
    module   = request.args.get('module', '')
    per_page = 50
    query    = ActivityLog.query.order_by(ActivityLog.created_at.desc())
    if module:
        query = query.filter(ActivityLog.module == module)
    total   = query.count()
    logs    = query.offset((page - 1) * per_page).limit(per_page).all()
    modules = [r[0] for r in db.session.query(ActivityLog.module).distinct().all()]
    return render_template('activity_log.html',
        logs=logs, total=total, page=page, per_page=per_page,
        modules=modules, selected_module=module, active_page='activity_log')


# ══════════════════════════════════════════════════════
#  CUSTOMERS
# ══════════════════════════════════════════════════════

@app.route('/customers', methods=['GET', 'POST'])
@login_required
def customers():
    if request.method == 'POST':
        full_name      = request.form.get('full_name', '').strip()
        contact_number = request.form.get('contact_number', '').strip()
        address        = request.form.get('address', '').strip()
        if not full_name or not all(c.isalpha() or c.isspace() for c in full_name):
            flash('Customer name must contain only letters and spaces.', 'error')
            return redirect(url_for('customers'))
        if contact_number and (not contact_number.isdigit() or len(contact_number) != 11):
            flash('Contact number must be exactly 11 digits.', 'error')
            return redirect(url_for('customers'))
        nc = Customer(full_name=full_name, contact_number=contact_number, address=address)
        db.session.add(nc)
        db.session.flush()
        log_activity('CREATE_CUSTOMER', 'Customers', f'Customer "{full_name}" added', 'Customer', nc.customer_id)
        try:
            db.session.commit()
            flash(f'Customer {full_name} added!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('customers'))
    return render_template('customers.html',
        customers=Customer.query.order_by(Customer.full_name).all(),
        active_page='customers')

@app.route('/customers/<int:customer_id>/edit', methods=['POST'])
@login_required
def edit_customer(customer_id):
    c = Customer.query.get_or_404(customer_id)
    c.full_name      = request.form.get('full_name', c.full_name).strip()
    c.contact_number = request.form.get('contact_number', '').strip()
    c.address        = request.form.get('address', '').strip()
    log_activity('EDIT_CUSTOMER', 'Customers', f'Customer "{c.full_name}" updated', 'Customer', customer_id)
    try:
        db.session.commit()
        flash('Customer updated!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')
    return redirect(url_for('customers'))

@app.route('/customers/<int:customer_id>/delete', methods=['POST'])
@login_required
def delete_customer(customer_id):
    c = Customer.query.get_or_404(customer_id)
    log_activity('DELETE_CUSTOMER', 'Customers', f'Customer "{c.full_name}" deleted', 'Customer', customer_id)
    try:
        db.session.delete(c)
        db.session.commit()
        flash('Customer deleted!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')
    return redirect(url_for('customers'))

@app.route('/admin/customers/<int:customer_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_customer_account(customer_id):
    c    = Customer.query.get_or_404(customer_id)
    name = c.full_name
    orders = DeliveryOrder.query.filter_by(customer_id=customer_id).count()
    sales  = Sale.query.filter_by(customer_id=customer_id).count()
    if (orders + sales) > 0 and not is_super_admin():
        flash(
            f'"{name}" has order/sale history. '
            f'Only a Super Admin can force-delete this account.',
            'error'
        )
        return redirect(url_for('user_management'))
    log_activity('DELETE_CUSTOMER_ACCOUNT', 'Users',
                 f'Customer account "{name}" deleted', 'Customer', customer_id)
    try:
        db.session.delete(c)
        db.session.commit()
        flash(f'Customer account "{name}" has been deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')
    return redirect(url_for('user_management'))

@app.route('/customers/create', methods=['POST'])
@login_required
@admin_required
def create_customer():
    first_name     = request.form.get('first_name', '').strip()
    middle_initial = request.form.get('middle_initial', '').strip()
    last_name      = request.form.get('last_name', '').strip()
    if first_name and last_name:
        parts = [first_name]
        if middle_initial:
            parts.append(middle_initial.rstrip('.') + '.')
        parts.append(last_name)
        full_name = ' '.join(parts)
    else:
        full_name = request.form.get('full_name', '').strip()
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    contact  = request.form.get('contact_number', '').strip()
    address  = request.form.get('address', '').strip()
    if not full_name:
        flash('Full name is required.', 'error')
        return redirect(url_for('user_management'))
    if not username:
        flash('Username is required.', 'error')
        return redirect(url_for('user_management'))
    if Customer.query.filter_by(username=username).first():
        flash('Username already exists.', 'error')
        return redirect(url_for('user_management'))
    if len(password) < 8:
        flash('Password must be at least 8 characters.', 'error')
        return redirect(url_for('user_management'))
    if contact and (not contact.isdigit() or len(contact) != 11):
        flash('Contact number must be exactly 11 digits.', 'error')
        return redirect(url_for('user_management'))
    nc = Customer(
        full_name=full_name, username=username,
        password=generate_password_hash(password),
        contact_number=contact, address=address
    )
    db.session.add(nc)
    db.session.flush()
    log_activity('CREATE_CUSTOMER', 'Customers',
                 f'Customer account created for {full_name} (@{username})', 'Customer', nc.customer_id)
    try:
        db.session.commit()
        flash(f'Customer account for {full_name} created!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')
    return redirect(url_for('user_management'))


# ══════════════════════════════════════════════════════
#  INVENTORY
# ══════════════════════════════════════════════════════

@app.route('/inventory', methods=['GET', 'POST'])
@login_required
def inventory():
    if request.method == 'POST':
        product_id = int(request.form.get('product_id'))
        action     = request.form.get('action')
        qty_change = int(request.form.get('quantity'))
        item       = Inventory.query.filter_by(product_id=product_id).first()
        if not item:
            flash('Inventory item not found.', 'error')
            return redirect(url_for('inventory'))
        if action == 'add':
            item.quantity += qty_change
            log_activity('INVENTORY_ADD', 'Inventory', f'Added {qty_change} units to "{item.product.product_name}"', 'Inventory', item.inventory_id)
            flash(f'Added {qty_change} units to {item.product.product_name}.', 'success')
        elif action == 'deduct':
            if item.quantity < qty_change:
                flash('Not enough stock!', 'error')
                return redirect(url_for('inventory'))
            item.quantity -= qty_change
            log_activity('INVENTORY_DEDUCT', 'Inventory', f'Deducted {qty_change} units from "{item.product.product_name}"', 'Inventory', item.inventory_id)
            flash(f'Deducted {qty_change} from {item.product.product_name}.', 'success')
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('inventory'))
    return render_template('inventory.html',
        inventory_items=Inventory.query.all(),
        products=Product.query.all(),
        active_page='inventory')


# ══════════════════════════════════════════════════════
#  DELIVERIES
# ══════════════════════════════════════════════════════

@app.route('/deliveries', methods=['GET', 'POST'])
@login_required
def deliveries():
    if request.method == 'POST':
        customer_id   = int(request.form.get('customer_id'))
        delivery_date = request.form.get('delivery_date')
        notes         = request.form.get('notes', '').strip()
        product_ids   = request.form.getlist('product_id[]')
        quantities    = request.form.getlist('quantity[]')
        delivery = DeliveryOrder(customer_id=customer_id, delivery_date=delivery_date,
                                 notes=notes, status='Pending')
        db.session.add(delivery)
        db.session.flush()
        total_amount = 0.0
        for pid, qty_str in zip(product_ids, quantities):
            product  = Product.query.get(int(pid))
            if not product: continue
            qty      = int(qty_str)
            subtotal = float(product.price) * qty
            total_amount += subtotal
            db.session.add(DeliveryItem(delivery_id=delivery.delivery_id,
                product_id=int(pid), quantity=qty, price=product.price, subtotal=subtotal))
        delivery.total_amount = total_amount
        customer = Customer.query.get(customer_id)
        log_activity('CREATE_DELIVERY', 'Deliveries',
                     f'Delivery #{delivery.delivery_id} for {customer.full_name} — ₱{total_amount:.2f}',
                     'DeliveryOrder', delivery.delivery_id)
        try:
            db.session.commit()
            flash('Delivery order created!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('deliveries'))
    return render_template('deliveries.html',
        deliveries_list=DeliveryOrder.query.order_by(DeliveryOrder.delivery_date.desc()).all(),
        customers=Customer.query.order_by(Customer.full_name).all(),
        products=Product.query.filter_by(is_active=True).all(),
        active_page='deliveries')

@app.route('/deliveries/<int:delivery_id>/status', methods=['POST'])
@login_required
def update_delivery_status(delivery_id):
    delivery   = DeliveryOrder.query.get_or_404(delivery_id)
    new_status = request.form.get('status')
    if new_status == 'Cancelled':
        flash('Use the cancel endpoint to cancel a delivery.', 'error')
        return redirect(url_for('deliveries'))
    if new_status == 'Confirmed' and delivery.status not in ('Pending', 'Confirmed'):
        flash('Only Pending deliveries can be confirmed.', 'error')
        return redirect(url_for('deliveries'))
    if new_status == 'Delivered' and delivery.status not in ('Pending', 'Confirmed'):
        flash('Only Pending or Confirmed deliveries can be marked as delivered.', 'error')
        return redirect(url_for('deliveries'))
    if new_status == 'Delivered' and delivery.status != 'Delivered':
        sale = Sale(user_id=session['user_id'], customer_id=delivery.customer_id,
                    sale_type='Delivery', total_amount=delivery.total_amount, sale_date=datetime.now())
        db.session.add(sale)
        db.session.flush()
        for di in delivery.delivery_items:
            db.session.add(SaleItem(sale_id=sale.sale_id, product_id=di.product_id,
                                    quantity=di.quantity, price=di.price, subtotal=di.subtotal))
            inv = Inventory.query.filter_by(product_id=di.product_id).first()
            if inv:
                inv.quantity = max(0, inv.quantity - di.quantity)
    delivery.status = new_status
    log_activity('UPDATE_DELIVERY', 'Deliveries', f'Delivery #{delivery_id} → {new_status}', 'DeliveryOrder', delivery_id)
    try:
        db.session.commit()
        flash(f'Delivery #{delivery_id} updated to {new_status}.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')
    return redirect(url_for('deliveries'))


@app.route('/deliveries/<int:delivery_id>/cancel', methods=['POST'])
@login_required
def cancel_delivery(delivery_id):
    delivery = DeliveryOrder.query.get_or_404(delivery_id)
    if delivery.status in ('Delivered', 'Cancelled'):
        flash(f'Delivery #{delivery_id} cannot be cancelled — it is already {delivery.status}.', 'error')
        return redirect(url_for('deliveries'))
    reason = request.form.get('cancel_reason', '').strip()
    delivery.status = 'Cancelled'
    log_activity(
        'CANCEL_DELIVERY', 'Deliveries',
        f'Delivery #{delivery_id} cancelled' + (f' — Reason: {reason}' if reason else ''),
        'DeliveryOrder', delivery_id
    )
    try:
        db.session.commit()
        flash(f'Delivery #{delivery_id} has been cancelled.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')
    return redirect(url_for('deliveries'))


# ══════════════════════════════════════════════════════
#  EXPENSES
# ══════════════════════════════════════════════════════

@app.route('/expense_management')
@login_required
def expense_management():
    return render_template('expenses.html',
        expenses=Expense.query.order_by(Expense.expense_date.desc()).all(),
        can_edit=is_admin_or_above(), active_page='expenses')

@app.route('/expenses', methods=['GET', 'POST'])
@login_required
def expenses():
    if request.method == 'POST':
        if not is_admin_or_above():
            flash('Admin access required to record expenses.', 'error')
            return redirect(url_for('expenses'))
        category     = request.form.get('category', '').strip()
        description  = request.form.get('description', '').strip()
        amount       = float(request.form.get('amount'))
        expense_date = request.form.get('expense_date')
        exp = Expense(user_id=session['user_id'], category=category,
                      description=description, amount=amount, expense_date=expense_date)
        db.session.add(exp)
        db.session.flush()
        log_activity('CREATE_EXPENSE', 'Expenses', f'"{description}" — ₱{amount:.2f}', 'Expense', exp.expense_id)
        try:
            db.session.commit()
            flash('Expense recorded!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('expenses'))
    return render_template('expenses.html',
        expenses=Expense.query.order_by(Expense.expense_date.desc()).all(),
        can_edit=is_admin_or_above(), active_page='expenses')

@app.route('/expenses/<int:expense_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    log_activity('DELETE_EXPENSE', 'Expenses', f'"{expense.description}" deleted', 'Expense', expense_id)
    try:
        db.session.delete(expense)
        db.session.commit()
        flash('Expense deleted!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')
    return redirect(url_for('expenses'))


# ══════════════════════════════════════════════════════
#  RETURNS
# ══════════════════════════════════════════════════════

@app.route('/returns')
@login_required
def returns():
    status    = request.args.get('status', '')
    date_from = request.args.get('date_from', '')
    date_to   = request.args.get('date_to', '')
    search    = request.args.get('search', '').strip().lower()
    query = Return.query.order_by(Return.created_at.desc())
    if status:
        query = query.filter(Return.status == status)
    if date_from:
        query = query.filter(Return.created_at >= date_from)
    if date_to:
        query = query.filter(Return.created_at <= date_to + ' 23:59:59')
    returns_list = query.all()
    if search:
        returns_list = [
            r for r in returns_list
            if search in (r.sale.customer.full_name.lower() if r.sale and r.sale.customer else '')
            or search in str(r.sale_id)
            or search in (r.reason or '').lower()
        ]
    sales = Sale.query.order_by(Sale.sale_date.desc()).all()
    return render_template('returns.html',
        returns_list=returns_list, sales=sales,
        status_filter=status, date_from=date_from, date_to=date_to,
        search=search, active_page='returns')

@app.route('/returns/new', methods=['POST'])
@login_required
def new_return():
    sale_id      = request.form.get('sale_id', type=int)
    reason       = request.form.get('reason', '').strip()
    notes        = request.form.get('notes', '').strip()
    sale         = Sale.query.get_or_404(sale_id)
    product_ids  = request.form.getlist('product_id[]')
    quantities   = request.form.getlist('quantity[]')
    item_reasons = request.form.getlist('item_reason[]')
    if not product_ids:
        flash('Please select at least one item to return.', 'error')
        return redirect(url_for('returns'))
    ret = Return(sale_id=sale_id, user_id=session['user_id'],
                 reason=reason, notes=notes, status='Pending', refund_amount=0)
    db.session.add(ret)
    db.session.flush()
    total_refund = 0.0
    for pid, qty_str, item_rsn in zip(product_ids, quantities, item_reasons):
        if not pid: continue
        product  = Product.query.get(int(pid))
        qty      = max(1, int(qty_str or 1))
        if not product: continue
        subtotal      = float(product.price) * qty
        total_refund += subtotal
        db.session.add(ReturnItem(return_id=ret.return_id, product_id=product.product_id,
                                  quantity=qty, price=product.price, subtotal=subtotal, reason=item_rsn))
    ret.refund_amount = total_refund
    log_activity('CREATE_RETURN', 'Returns',
                 f'Return #{ret.return_id} for Sale #{sale_id} — ₱{total_refund:.2f}', 'Return', ret.return_id)
    try:
        db.session.commit()
        flash(f'Return request #{ret.return_id} submitted for review.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')
    return redirect(url_for('returns'))

@app.route('/returns/<int:return_id>/review', methods=['POST'])
@login_required
@admin_required
def review_return(return_id):
    ret        = Return.query.get_or_404(return_id)
    action     = request.form.get('action')
    admin_note = request.form.get('admin_note', '').strip()

    if ret.status != 'Pending':
        flash('This return has already been reviewed.', 'error')
        return redirect(url_for('returns'))

    if action == 'approve':
        ret.status = 'Approved'

        # ── Restock inventory ──────────────────────────────────
        for item in ret.return_items:
            inv = Inventory.query.filter_by(product_id=item.product_id).first()
            if inv:
                inv.quantity += item.quantity

        # ── Loyalty points rollback ────────────────────────────
        # For every 10 refill gallons returned the customer originally
        # earned 1 point; we take those points back (floor division).
        if ret.sale and ret.sale.customer:
            customer = ret.sale.customer
            total_returned_refills = sum(
                item.quantity for item in ret.return_items
                if 'refill' in item.product.product_name.lower()
            )
            if total_returned_refills > 0:
                pts_to_deduct = total_returned_refills // 10
                if pts_to_deduct > 0:
                    customer.loyalty_points = max(0, customer.loyalty_points - pts_to_deduct)
                    # Optional: log the deduction as a LoyaltyTransaction if your
                    # model supports it.  The fields below are a common schema;
                    # adjust column names if yours differ.
                    try:
                        lt = LoyaltyTransaction(
                            customer_id=customer.customer_id,
                            points=-pts_to_deduct,
                            transaction_type='Deduction',
                            description=f'Loyalty rollback — Return #{return_id} approved',
                            created_at=datetime.now(),
                        )
                        db.session.add(lt)
                    except Exception:
                        # If LoyaltyTransaction schema differs just skip the log;
                        # the points adjustment above already happened.
                        pass

        if admin_note:
            ret.notes = (ret.notes or '') + f'\n[Admin] {admin_note}'

        log_activity('APPROVE_RETURN', 'Returns',
                     f'Return #{return_id} approved — ₱{ret.refund_amount:.2f}',
                     'Return', return_id)
        flash(f'Return #{return_id} approved. ₱{float(ret.refund_amount):.2f} refund issued.', 'success')

    elif action == 'reject':
        ret.status = 'Rejected'
        if admin_note:
            ret.notes = (ret.notes or '') + f'\n[Admin] {admin_note}'
        log_activity('REJECT_RETURN', 'Returns',
                     f'Return #{return_id} rejected', 'Return', return_id)
        flash(f'Return #{return_id} rejected.', 'success')

    ret.reviewed_by = session['user_id']
    ret.reviewed_at = datetime.now()

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')

    return redirect(url_for('returns'))

@app.route('/returns/<int:return_id>/delete', methods=['POST'])
@login_required
@super_admin_required
def delete_return(return_id):
    ret = Return.query.get_or_404(return_id)
    log_activity('DELETE_RETURN', 'Returns', f'Return #{return_id} deleted', 'Return', return_id)
    try:
        db.session.delete(ret)
        db.session.commit()
        flash('Return record deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')
    return redirect(url_for('returns'))


# ══════════════════════════════════════════════════════
#  WATER TANK
# ══════════════════════════════════════════════════════

TANK_CAPACITY = 20.0   # gallons


def _get_tank_level():
    """Compute current water level from the log table."""
    from sqlalchemy import func
    refills = db.session.query(
        func.coalesce(func.sum(WaterTankLog.gallons), 0)
    ).filter(WaterTankLog.action == 'refill').scalar()
    usage = db.session.query(
        func.coalesce(func.sum(WaterTankLog.gallons), 0)
    ).filter(WaterTankLog.action == 'usage').scalar()
    return max(0.0, min(TANK_CAPACITY, float(refills) - float(usage)))


@app.route('/water-tank')
@login_required
def water_tank():
    level = _get_tank_level()
    logs  = WaterTankLog.query.order_by(WaterTankLog.created_at.desc()).limit(50).all()
    return render_template(
        'water_tank.html',
        level=level,
        capacity=TANK_CAPACITY,
        logs=logs,
        active_page='water_tank',
    )


@app.route('/water-tank/refill', methods=['POST'])
@login_required
def water_tank_refill():
    try:
        gallons = float(request.form.get('gallons', 0))
    except (ValueError, TypeError):
        flash('Please enter a valid number.', 'error')
        return redirect(url_for('water_tank'))

    note  = request.form.get('note', '').strip()
    level = _get_tank_level()
    max_add = round(TANK_CAPACITY - level, 4)

    if gallons <= 0:
        flash('Amount must be greater than 0.', 'error')
        return redirect(url_for('water_tank'))
    if max_add <= 0:
        flash('The tank is already full (20 gallons).', 'error')
        return redirect(url_for('water_tank'))

    # Clamp to available space
    gallons = min(gallons, max_add)

    entry = WaterTankLog(
        action='refill',
        gallons=round(gallons, 2),
        note=note or 'Tank refilled',
        user_id=session.get('user_id'),
    )
    db.session.add(entry)
    log_activity('TANK_REFILL', 'Water Tank',
                 f'+{gallons:.2f} gal added — level now {level + gallons:.2f}/{TANK_CAPACITY:.0f} gal')
    try:
        db.session.commit()
        flash(f'✓ Added {gallons:.1f} gallons. Tank is now at {level + gallons:.1f} gal.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')

    return redirect(url_for('water_tank'))


@app.route('/water-tank/use', methods=['POST'])
@login_required
def water_tank_use():
    try:
        gallons = float(request.form.get('gallons', 0))
    except (ValueError, TypeError):
        flash('Please enter a valid number.', 'error')
        return redirect(url_for('water_tank'))

    note  = request.form.get('note', '').strip()
    level = _get_tank_level()

    if gallons <= 0:
        flash('Amount must be greater than 0.', 'error')
        return redirect(url_for('water_tank'))
    if gallons > level:
        flash(f'Not enough water. Only {level:.1f} gal available.', 'error')
        return redirect(url_for('water_tank'))

    entry = WaterTankLog(
        action='usage',
        gallons=round(gallons, 2),
        note=note or 'Water used',
        user_id=session.get('user_id'),
    )
    db.session.add(entry)
    log_activity('TANK_USAGE', 'Water Tank',
                 f'−{gallons:.2f} gal used — level now {level - gallons:.2f}/{TANK_CAPACITY:.0f} gal')
    try:
        db.session.commit()
        flash(f'✓ Logged {gallons:.1f} gallons used. Tank is now at {level - gallons:.1f} gal.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')

    return redirect(url_for('water_tank'))


@app.route('/api/sale/<int:sale_id>/items')
@login_required
def api_sale_items(sale_id):
    sale  = Sale.query.get_or_404(sale_id)
    items = [{'product_id': si.product_id, 'product_name': si.product.product_name,
               'quantity': si.quantity, 'price': float(si.price), 'subtotal': float(si.subtotal)}
             for si in sale.sale_items]
    customer = sale.customer.full_name if sale.customer else 'Walk-in'
    return jsonify({'items': items, 'customer': customer, 'total': float(sale.total_amount)})


# ══════════════════════════════════════════════════════
#  REPORTS
# ══════════════════════════════════════════════════════

@app.route('/reports')
@login_required
def reports():
    from sqlalchemy import func
    month          = request.args.get('month', datetime.now().strftime('%Y-%m'))
    total_revenue  = db.session.query(func.coalesce(func.sum(Sale.total_amount), 0)).filter(func.date_format(Sale.sale_date, '%Y-%m') == month).scalar()
    total_expenses = db.session.query(func.coalesce(func.sum(Expense.amount), 0)).filter(func.date_format(Expense.expense_date, '%Y-%m') == month).scalar()
    net_profit     = total_revenue - total_expenses
    sales_count    = Sale.query.filter(func.date_format(Sale.sale_date, '%Y-%m') == month).count()
    by_category    = db.session.query(Expense.category, func.sum(Expense.amount)).filter(func.date_format(Expense.expense_date, '%Y-%m') == month).group_by(Expense.category).all()
    top_products   = db.session.query(
        Product.product_name, func.sum(SaleItem.subtotal).label('revenue'), func.sum(SaleItem.quantity).label('qty'),
    ).join(SaleItem, SaleItem.product_id == Product.product_id)\
     .join(Sale, Sale.sale_id == SaleItem.sale_id)\
     .filter(func.date_format(Sale.sale_date, '%Y-%m') == month)\
     .group_by(Product.product_id).order_by(func.sum(SaleItem.subtotal).desc()).limit(5).all()
    return render_template('reports.html',
        month=month, total_revenue=total_revenue, total_expenses=total_expenses,
        net_profit=net_profit, sales_count=sales_count,
        by_category=by_category, top_products=top_products, active_page='reports')


# ══════════════════════════════════════════════════════
#  CUSTOMER PORTAL
# ══════════════════════════════════════════════════════

@app.route('/customer/logout')
def customer_logout():
    session.pop('customer_id', None)
    session.pop('customer_name', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('customer_login'))

@app.route('/customer/dashboard')
def customer_dashboard():
    if 'customer_id' not in session:
        return redirect(url_for('customer_login'))
    from sqlalchemy import func
    customer         = Customer.query.get_or_404(session['customer_id'])
    cid              = customer.customer_id
    total_orders     = DeliveryOrder.query.filter_by(customer_id=cid).count()
    pending_orders   = DeliveryOrder.query.filter_by(customer_id=cid, status='Pending').count()
    delivered_orders = DeliveryOrder.query.filter_by(customer_id=cid, status='Delivered').count()
    cancelled_orders = DeliveryOrder.query.filter_by(customer_id=cid, status='Cancelled').count()
    recent_orders    = DeliveryOrder.query.filter_by(customer_id=cid).order_by(DeliveryOrder.delivery_date.desc()).limit(6).all()

    # Most recent active (Pending or Confirmed) delivery — used by the Delivery Tracker card.
    # Ordered by created_at so we show what was placed last, not what is scheduled furthest.
    active_delivery  = DeliveryOrder.query.filter(
        DeliveryOrder.customer_id == cid,
        DeliveryOrder.status.in_(['Pending', 'Confirmed'])
    ).order_by(DeliveryOrder.created_at.desc()).first()

    order_history_labels, order_history_values, spend_labels, spend_values = [], [], [], []
    for i in range(5, -1, -1):
        ref   = (datetime.now().replace(day=1) - timedelta(days=i * 28)).replace(day=1)
        month = ref.strftime('%Y-%m')
        label = ref.strftime('%b %Y')
        count = DeliveryOrder.query.filter(DeliveryOrder.customer_id == cid,
            func.date_format(DeliveryOrder.delivery_date, '%Y-%m') == month).count()
        spend = db.session.query(func.coalesce(func.sum(DeliveryOrder.total_amount), 0)).filter(
            DeliveryOrder.customer_id == cid,
            func.date_format(DeliveryOrder.delivery_date, '%Y-%m') == month).scalar()
        order_history_labels.append(label)
        order_history_values.append(count)
        spend_labels.append(label)
        spend_values.append(float(spend))
    return render_template('customer_dashboard.html',
        customer=customer, total_orders=total_orders, pending_orders=pending_orders,
        delivered_orders=delivered_orders, cancelled_orders=cancelled_orders,
        recent_orders=recent_orders, active_delivery=active_delivery,
        order_history_labels=order_history_labels,
        order_history_values=order_history_values, spend_labels=spend_labels,
        spend_values=spend_values, active_page='customer_dashboard')

@app.route('/customer/order', methods=['GET', 'POST'])
def customer_order():
    if 'customer_id' not in session:
        return redirect(url_for('customer_login'))
    customer = Customer.query.get_or_404(session['customer_id'])
    products = Product.query.filter_by(is_active=True).order_by(Product.product_name).all()
    if request.method == 'POST':
        delivery_date = request.form.get('delivery_date', '').strip()
        notes         = request.form.get('notes', '').strip()
        product_ids   = request.form.getlist('product_id[]')
        quantities    = request.form.getlist('quantity[]')
        if not delivery_date:
            flash('Please select a delivery date.', 'error')
            return render_template('customer_order.html', customer=customer, products=products, active_page='customer_order')
        delivery = DeliveryOrder(customer_id=customer.customer_id,
                                 delivery_date=delivery_date, notes=notes, status='Pending')
        db.session.add(delivery)
        db.session.flush()
        total_amount = 0.0
        items_added  = 0
        for pid_str, qty_str in zip(product_ids, quantities):
            if not pid_str: continue
            product  = Product.query.get(int(pid_str))
            qty      = int(qty_str) if qty_str else 1
            if not product: continue
            subtotal      = float(product.price) * qty
            total_amount += subtotal
            items_added  += 1
            db.session.add(DeliveryItem(delivery_id=delivery.delivery_id,
                product_id=product.product_id, quantity=qty, price=product.price, subtotal=subtotal))
        if items_added == 0:
            db.session.rollback()
            flash('Please select at least one product.', 'error')
            return render_template('customer_order.html', customer=customer, products=products, active_page='customer_order')
        delivery.total_amount = total_amount
        try:
            db.session.commit()
            flash('Your order has been placed!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('customer_deliveries'))
    return render_template('customer_order.html', customer=customer, products=products, active_page='customer_order')

@app.route('/customer/deliveries')
def customer_deliveries():
    if 'customer_id' not in session:
        return redirect(url_for('customer_login'))
    customer  = Customer.query.get_or_404(session['customer_id'])
    search    = request.args.get('search', '').strip().lower()
    date_from = request.args.get('date_from')
    date_to   = request.args.get('date_to')
    status    = request.args.get('status')
    query     = DeliveryOrder.query.filter_by(customer_id=customer.customer_id)
    if status and status != 'All':
        query = query.filter(DeliveryOrder.status == status)
    if date_from:
        query = query.filter(DeliveryOrder.delivery_date >= date_from)
    if date_to:
        query = query.filter(DeliveryOrder.delivery_date <= date_to)
    orders = query.order_by(DeliveryOrder.delivery_date.desc()).all()
    if search:
        orders = [o for o in orders
                  if search in (o.status or '').lower()
                  or any(search in i.product.product_name.lower() for i in o.delivery_items)]
    return render_template('dashboard_customer.html', orders=orders,
        search=search, date_from=date_from, date_to=date_to,
        status=status or 'All', active_page='customer_deliveries')


# ══════════════════════════════════════════════════════
#  CUSTOMER PROFILE
# ══════════════════════════════════════════════════════

@app.route('/customer/profile')
def customer_profile():
    if 'customer_id' not in session:
        return redirect(url_for('customer_login'))
    customer = Customer.query.get_or_404(session['customer_id'])
    return render_template('customer_profile.html', customer=customer, active_page='customer_profile')

@app.route('/customer/profile/update', methods=['POST'])
def customer_profile_update():
    if 'customer_id' not in session:
        return redirect(url_for('customer_login'))
    customer  = Customer.query.get_or_404(session['customer_id'])
    form_type = request.form.get('form_type')

    if form_type == 'info':
        import re
        first_name     = request.form.get('first_name', '').strip()
        middle_initial = request.form.get('middle_initial', '').strip()
        last_name      = request.form.get('last_name', '').strip()
        phone          = request.form.get('phone', '').strip()
        email          = request.form.get('email', '').strip()
        address        = request.form.get('address', '').strip()

        if not first_name:
            flash('First name is required.', 'error')
            return redirect(url_for('customer_profile'))
        if not re.match(r'^[A-Za-z\s]+$', first_name):
            flash('First name must contain letters only.', 'error')
            return redirect(url_for('customer_profile'))
        if not last_name:
            flash('Last name is required.', 'error')
            return redirect(url_for('customer_profile'))
        if not re.match(r'^[A-Za-z\s]+$', last_name):
            flash('Last name must contain letters only.', 'error')
            return redirect(url_for('customer_profile'))
        if middle_initial and not re.match(r'^[A-Za-z]\.?$', middle_initial):
            flash('Middle initial must be a single letter.', 'error')
            return redirect(url_for('customer_profile'))
        if phone and (not phone.isdigit() or len(phone) != 11):
            flash('Phone number must be exactly 11 digits.', 'error')
            return redirect(url_for('customer_profile'))
        if email and not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
            flash('Please enter a valid email address.', 'error')
            return redirect(url_for('customer_profile'))

        parts = [first_name]
        if middle_initial:
            mi_clean = middle_initial.rstrip('.')
            parts.append(mi_clean + '.')
        parts.append(last_name)
        full_name = ' '.join(parts)

        customer.first_name     = first_name
        customer.middle_initial = middle_initial.rstrip('.') if middle_initial else None
        customer.last_name      = last_name
        customer.full_name      = full_name
        customer.phone          = phone or customer.phone
        customer.email          = email or None
        customer.address        = address or customer.address
        session['customer_name'] = full_name

        log_activity('EDIT_PROFILE', 'Profile',
                     f'Customer {full_name} updated profile info',
                     'Customer', customer.customer_id)
        try:
            db.session.commit()
            flash('Your information has been updated!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'error')

    elif form_type == 'password':
        current_password = request.form.get('current_password', '')
        new_password     = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        if not customer.password or not check_password_hash(customer.password, current_password):
            flash('Current password is incorrect.', 'error')
            return redirect(url_for('customer_profile'))
        if len(new_password) < 8:
            flash('New password must be at least 8 characters.', 'error')
            return redirect(url_for('customer_profile'))
        if new_password != confirm_password:
            flash('New passwords do not match.', 'error')
            return redirect(url_for('customer_profile'))
        customer.password = generate_password_hash(new_password)
        log_activity('CHANGE_PASSWORD', 'Profile',
                     f'Customer {customer.full_name} changed password',
                     'Customer', customer.customer_id)
        try:
            db.session.commit()
            flash('Password updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating password: {str(e)}', 'error')
    else:
        flash('Invalid request.', 'error')
    return redirect(url_for('customer_profile'))


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)