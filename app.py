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
)
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
    return session.get('role') in ('Super Admin', 'Admin')


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
        full_name='Super Administrator', username='superadmin',
        password=generate_password_hash('changeme123'),
        role='Super Admin', status='Active',
    ))
    db.session.commit()
    print('Done. username=superadmin  password=changeme123  — change it immediately!')


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

@app.route('/landing')
def landing():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    if 'customer_id' in session:
        return redirect(url_for('customer_dashboard'))
    return render_template('landing.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            if user.status == 'Inactive':
                flash('This account is deactivated.', 'error')
                return render_template('login.html')
            session.update({'user_id': user.user_id, 'username': user.username,
                            'role': user.role, 'full_name': user.full_name})
            log_activity('LOGIN', 'Auth', f'{user.full_name} logged in')
            db.session.commit()
            return redirect(url_for('dashboard'))
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

    # ── shared metrics ──────────────────────────────────────────────
    today_sales = db.session.query(
        func.coalesce(func.sum(Sale.total_amount), 0)
    ).filter(func.date(Sale.sale_date) == today).scalar()

    pending_deliveries = DeliveryOrder.query.filter_by(status='Pending').count()
    total_customers    = Customer.query.count()
    recent_sales       = Sale.query.order_by(Sale.sale_date.desc()).limit(8).all()
    inventory_items    = Inventory.query.all()
    low_stock_items    = sum(
        1 for i in inventory_items if i.quantity <= (i.minimum_stock or 10)
    )

    # 7-day trend (shared by both dashboard templates)
    sales_trend_labels, sales_trend_values = [], []
    for i in range(6, -1, -1):
        day = (datetime.now() - timedelta(days=i)).date()
        total = db.session.query(
            func.coalesce(func.sum(Sale.total_amount), 0)
        ).filter(func.date(Sale.sale_date) == day).scalar()
        sales_trend_labels.append(day.strftime('%b %d'))
        sales_trend_values.append(float(total))

    # ── admin / super-admin branch ──────────────────────────────────
    if is_admin_or_above():
        monthly_revenue = db.session.query(
            func.coalesce(func.sum(Sale.total_amount), 0)
        ).filter(func.date_format(Sale.sale_date, '%Y-%m') == month).scalar()

        monthly_expenses = db.session.query(
            func.coalesce(func.sum(Expense.amount), 0)
        ).filter(func.date_format(Expense.expense_date, '%Y-%m') == month).scalar()

        net_profit   = monthly_revenue - monthly_expenses
        total_staff  = User.query.filter(User.role.in_(['Admin', 'Operator'])).count()

        walkin_count = Sale.query.filter(
            Sale.sale_type == 'Walk-in',
            func.date_format(Sale.sale_date, '%Y-%m') == month
        ).count()
        delivery_count = Sale.query.filter(
            Sale.sale_type == 'Delivery',
            func.date_format(Sale.sale_date, '%Y-%m') == month
        ).count()

        top_products_q = db.session.query(
            Product.product_name,
            func.sum(SaleItem.quantity).label('qty'),
        ).join(SaleItem, SaleItem.product_id == Product.product_id)\
         .join(Sale, Sale.sale_id == SaleItem.sale_id)\
         .filter(func.date_format(Sale.sale_date, '%Y-%m') == month)\
         .group_by(Product.product_id)\
         .order_by(func.sum(SaleItem.quantity).desc())\
         .limit(5).all()
        top_product_names = [r[0] for r in top_products_q]
        top_product_qtys  = [int(r[1]) for r in top_products_q]

        expense_by_category = db.session.query(
            Expense.category, func.sum(Expense.amount)
        ).filter(func.date_format(Expense.expense_date, '%Y-%m') == month)\
         .group_by(Expense.category).all()

        # Super Admin extras
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
                ActivityLog.created_at.desc()
            ).limit(8).all()

        return render_template('dashboard_admin.html',
            today_sales=today_sales,
            monthly_revenue=monthly_revenue,
            monthly_expenses=monthly_expenses,
            net_profit=net_profit,
            pending_deliveries=pending_deliveries,
            total_customers=total_customers,
            low_stock_items=low_stock_items,
            recent_sales=recent_sales,
            total_staff=total_staff,
            inventory_items=inventory_items,
            sales_trend_labels=sales_trend_labels,
            sales_trend_values=sales_trend_values,
            walkin_count=walkin_count,
            delivery_count=delivery_count,
            top_product_names=top_product_names,
            top_product_qtys=top_product_qtys,
            expense_by_category=expense_by_category,
            user_role_counts=user_role_counts,
            user_role_labels=user_role_labels,
            user_role_values=user_role_values,
            total_users=total_users,
            recent_activity=recent_activity,
            active_page='dashboard',
        )

    # ── operator branch ─────────────────────────────────────────────
    delivered_today = DeliveryOrder.query.filter(
        DeliveryOrder.status == 'Delivered',
        func.date(DeliveryOrder.created_at) == today
    ).count()

    pending_delivery_list = DeliveryOrder.query.filter_by(status='Pending')\
        .order_by(DeliveryOrder.delivery_date).limit(6).all()

    walkin_today   = Sale.query.filter(
        Sale.sale_type == 'Walk-in', func.date(Sale.sale_date) == today
    ).count()
    delivery_today = Sale.query.filter(
        Sale.sale_type == 'Delivery', func.date(Sale.sale_date) == today
    ).count()

    return render_template('dashboard_operator.html',
        today_sales=today_sales,
        pending_deliveries=pending_deliveries,
        total_customers=total_customers,
        recent_sales=recent_sales,
        pending_delivery_list=pending_delivery_list,
        delivered_today=delivered_today,
        low_stock_items=low_stock_items,
        inventory_items=inventory_items,
        sales_trend_labels=sales_trend_labels,
        sales_trend_values=sales_trend_values,
        walkin_today=walkin_today,
        delivery_today=delivery_today,
        active_page='dashboard',
    )


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
@admin_required
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
            SaleItem(product_id=int(pid), quantity=quantity,
                     price=product.price, subtotal=subtotal),
            product
        ))

    if customer_id:
        customer = Customer.query.get(customer_id)
        if customer:
            total_refills = sum(
                i.quantity for i, p in items_with_products
                if 'refill' in p.product_name.lower()
            )
            if customer.loyalty_points > 0 and total_refills > 0:
                refill_total  = sum(
                    i.subtotal for i, p in items_with_products
                    if 'refill' in p.product_name.lower()
                )
                free_used     = min(customer.loyalty_points, total_refills)
                total_amount -= (refill_total / total_refills) * free_used
                customer.loyalty_points -= free_used
                remaining_refills = total_refills - free_used
            else:
                remaining_refills = total_refills

            if remaining_refills > 0:
                new_pts = remaining_refills // 10
                if new_pts > 0:
                    customer.loyalty_points += new_pts

    sale = Sale(
        user_id=session['user_id'], customer_id=customer_id,
        sale_type=sale_type, total_amount=total_amount,
        sale_date=datetime.now()
    )
    db.session.add(sale)
    db.session.flush()

    for sale_item, product in items_with_products:
        sale_item.sale_id = sale.sale_id
        db.session.add(sale_item)
        inv = Inventory.query.filter_by(product_id=product.product_id).first()
        if inv:
            inv.quantity = max(0, inv.quantity - sale_item.quantity)

    log_activity('CREATE_SALE', 'Sales',
                 f'{sale_type} sale — ₱{total_amount:.2f}', 'Sale', sale.sale_id)
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
    return render_template('user_management.html',
        users=users, is_super_admin=is_super_admin(), active_page='user_management')

@app.route('/admin/users', methods=['POST'])
@login_required
@admin_required
def create_user():
    # Supports split-name fields from the form
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
        full_name=full_name, username=username,
        password=generate_password_hash(password),
        role=role, status='Active'
    )
    db.session.add(new_user)
    db.session.flush()
    log_activity('CREATE_USER', 'Users',
                 f'Account created for {full_name} (@{username}) as {role}',
                 'User', new_user.user_id)
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
    return redirect(url_for('user_management'))

@app.route('/admin/users/<int:user_id>/reset-password', methods=['POST'])
@login_required
@super_admin_required
def reset_user_password(user_id):
    user         = User.query.get_or_404(user_id)
    new_password = request.form.get('new_password', '').strip()
    if len(new_password) < 8:
        flash('Password must be at least 8 characters.', 'error')
        return redirect(url_for('user_management'))
    user.password = generate_password_hash(new_password)
    log_activity('RESET_PASSWORD', 'Users', f'Password reset for @{user.username}', 'User', user_id)
    try:
        db.session.commit()
        flash(f'Password for @{user.username} reset.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')
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
                 f'{user.full_name} (@{user.username}) deleted', 'User', user_id)
    try:
        db.session.delete(user)
        db.session.commit()
        flash(f'Account for {user.full_name} deleted.', 'success')
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
#  ACTIVITY LOG  (Super Admin only)
# ══════════════════════════════════════════════════════

@app.route('/activity-log')
@login_required
@super_admin_required
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
        log_activity('CREATE_CUSTOMER', 'Customers',
                     f'Customer "{full_name}" added', 'Customer', nc.customer_id)
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
    log_activity('EDIT_CUSTOMER', 'Customers',
                 f'Customer "{c.full_name}" updated', 'Customer', customer_id)
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
    log_activity('DELETE_CUSTOMER', 'Customers',
                 f'Customer "{c.full_name}" deleted', 'Customer', customer_id)
    try:
        db.session.delete(c)
        db.session.commit()
        flash('Customer deleted!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')
    return redirect(url_for('customers'))


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
            log_activity('INVENTORY_ADD', 'Inventory',
                         f'Added {qty_change} units to "{item.product.product_name}"',
                         'Inventory', item.inventory_id)
            flash(f'Added {qty_change} units to {item.product.product_name}.', 'success')
        elif action == 'deduct':
            if item.quantity < qty_change:
                flash('Not enough stock!', 'error')
                return redirect(url_for('inventory'))
            item.quantity -= qty_change
            log_activity('INVENTORY_DEDUCT', 'Inventory',
                         f'Deducted {qty_change} units from "{item.product.product_name}"',
                         'Inventory', item.inventory_id)
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

        delivery = DeliveryOrder(
            customer_id=customer_id, delivery_date=delivery_date,
            notes=notes, status='Pending'
        )
        db.session.add(delivery)
        db.session.flush()

        total_amount = 0.0
        for pid, qty_str in zip(product_ids, quantities):
            product  = Product.query.get(int(pid))
            if not product:
                continue
            qty      = int(qty_str)
            subtotal = float(product.price) * qty
            total_amount += subtotal
            db.session.add(DeliveryItem(
                delivery_id=delivery.delivery_id,
                product_id=int(pid), quantity=qty,
                price=product.price, subtotal=subtotal
            ))
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
    if new_status == 'Delivered' and delivery.status != 'Delivered':
        sale = Sale(
            user_id=session['user_id'], customer_id=delivery.customer_id,
            sale_type='Delivery', total_amount=delivery.total_amount,
            sale_date=datetime.now()
        )
        db.session.add(sale)
        db.session.flush()
        for di in delivery.delivery_items:
            db.session.add(SaleItem(
                sale_id=sale.sale_id, product_id=di.product_id,
                quantity=di.quantity, price=di.price, subtotal=di.subtotal
            ))
            inv = Inventory.query.filter_by(product_id=di.product_id).first()
            if inv:
                inv.quantity = max(0, inv.quantity - di.quantity)
    delivery.status = new_status
    log_activity('UPDATE_DELIVERY', 'Deliveries',
                 f'Delivery #{delivery_id} → {new_status}', 'DeliveryOrder', delivery_id)
    try:
        db.session.commit()
        flash(f'Delivery updated to {new_status}.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')
    return redirect(url_for('deliveries'))


# ══════════════════════════════════════════════════════
#  EXPENSES
# ══════════════════════════════════════════════════════

@app.route('/expense_management')
@login_required
@admin_required
def expense_management():
    return render_template('expenses.html',
        expenses=Expense.query.order_by(Expense.expense_date.desc()).all(),
        active_page='expenses')

@app.route('/expenses', methods=['GET', 'POST'])
@login_required
@admin_required
def expenses():
    if request.method == 'POST':
        category     = request.form.get('category', '').strip()
        description  = request.form.get('description', '').strip()
        amount       = float(request.form.get('amount'))
        expense_date = request.form.get('expense_date')
        exp = Expense(
            user_id=session['user_id'], category=category,
            description=description, amount=amount, expense_date=expense_date
        )
        db.session.add(exp)
        db.session.flush()
        log_activity('CREATE_EXPENSE', 'Expenses',
                     f'"{description}" — ₱{amount:.2f}', 'Expense', exp.expense_id)
        try:
            db.session.commit()
            flash('Expense recorded!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('expenses'))
    return render_template('expenses.html',
        expenses=Expense.query.order_by(Expense.expense_date.desc()).all(),
        active_page='expenses')

@app.route('/expenses/<int:expense_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    log_activity('DELETE_EXPENSE', 'Expenses',
                 f'"{expense.description}" deleted', 'Expense', expense_id)
    try:
        db.session.delete(expense)
        db.session.commit()
        flash('Expense deleted!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')
    return redirect(url_for('expenses'))


# ══════════════════════════════════════════════════════
#  REPORTS
# ══════════════════════════════════════════════════════

@app.route('/reports')
@login_required
@admin_required
def reports():
    from sqlalchemy import func
    month          = request.args.get('month', datetime.now().strftime('%Y-%m'))
    total_revenue  = db.session.query(func.coalesce(func.sum(Sale.total_amount), 0)).filter(func.date_format(Sale.sale_date, '%Y-%m') == month).scalar()
    total_expenses = db.session.query(func.coalesce(func.sum(Expense.amount), 0)).filter(func.date_format(Expense.expense_date, '%Y-%m') == month).scalar()
    net_profit     = total_revenue - total_expenses
    sales_count    = Sale.query.filter(func.date_format(Sale.sale_date, '%Y-%m') == month).count()
    by_category    = db.session.query(Expense.category, func.sum(Expense.amount)).filter(func.date_format(Expense.expense_date, '%Y-%m') == month).group_by(Expense.category).all()
    top_products   = db.session.query(
        Product.product_name,
        func.sum(SaleItem.subtotal).label('revenue'),
        func.sum(SaleItem.quantity).label('qty'),
    ).join(SaleItem, SaleItem.product_id == Product.product_id)\
     .join(Sale, Sale.sale_id == SaleItem.sale_id)\
     .filter(func.date_format(Sale.sale_date, '%Y-%m') == month)\
     .group_by(Product.product_id)\
     .order_by(func.sum(SaleItem.subtotal).desc())\
     .limit(5).all()

    return render_template('reports.html',
        month=month, total_revenue=total_revenue, total_expenses=total_expenses,
        net_profit=net_profit, sales_count=sales_count,
        by_category=by_category, top_products=top_products, active_page='reports')


# ══════════════════════════════════════════════════════
#  CUSTOMER PORTAL
# ══════════════════════════════════════════════════════

@app.route('/customers/create', methods=['POST'])
@login_required
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

    username = request.form.get('username')
    password = request.form.get('password')
    contact  = request.form.get('contact_number', '').strip()
    address  = request.form.get('address', '').strip()

    if Customer.query.filter_by(username=username).first():
        flash('Username already exists.', 'error')
        return redirect(url_for('customers'))

    nc = Customer(
        full_name=full_name, username=username,
        password=generate_password_hash(password),
        contact_number=contact, address=address
    )
    db.session.add(nc)
    db.session.flush()
    log_activity('CREATE_CUSTOMER', 'Customers',
                 f'Customer account created for {full_name}', 'Customer', nc.customer_id)
    db.session.commit()
    flash('Customer account created!', 'success')
    return redirect(url_for('customers'))

@app.route('/customer/login', methods=['GET', 'POST'])
def customer_login():
    if 'customer_id' in session:
        return redirect(url_for('customer_dashboard'))
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        customer = Customer.query.filter_by(username=username).first()
        if customer and customer.password and check_password_hash(customer.password, password):
            session['customer_id']   = customer.customer_id
            session['customer_name'] = customer.full_name
            return redirect(url_for('customer_dashboard'))
        flash('Invalid username or password.', 'error')
    return render_template('customer_login.html')

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
    customer         = Customer.query.get_or_404(session['customer_id'])
    total_orders     = DeliveryOrder.query.filter_by(customer_id=customer.customer_id).count()
    pending_orders   = DeliveryOrder.query.filter_by(customer_id=customer.customer_id, status='Pending').count()
    delivered_orders = DeliveryOrder.query.filter_by(customer_id=customer.customer_id, status='Delivered').count()
    recent_orders    = DeliveryOrder.query.filter_by(customer_id=customer.customer_id)\
        .order_by(DeliveryOrder.delivery_date.desc()).limit(5).all()
    return render_template('customer_dashboard.html', customer=customer,
        total_orders=total_orders, pending_orders=pending_orders,
        delivered_orders=delivered_orders, recent_orders=recent_orders,
        active_page='customer_dashboard')

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
            return render_template('customer_order.html', customer=customer,
                                   products=products, active_page='customer_order')
        delivery = DeliveryOrder(
            customer_id=customer.customer_id,
            delivery_date=delivery_date, notes=notes, status='Pending'
        )
        db.session.add(delivery)
        db.session.flush()
        total_amount = 0.0
        items_added  = 0
        for pid_str, qty_str in zip(product_ids, quantities):
            if not pid_str:
                continue
            product  = Product.query.get(int(pid_str))
            qty      = int(qty_str) if qty_str else 1
            if not product:
                continue
            subtotal      = float(product.price) * qty
            total_amount += subtotal
            items_added  += 1
            db.session.add(DeliveryItem(
                delivery_id=delivery.delivery_id,
                product_id=product.product_id, quantity=qty,
                price=product.price, subtotal=subtotal
            ))
        if items_added == 0:
            db.session.rollback()
            flash('Please select at least one product.', 'error')
            return render_template('customer_order.html', customer=customer,
                                   products=products, active_page='customer_order')
        delivery.total_amount = total_amount
        try:
            db.session.commit()
            flash('Your order has been placed!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('customer_deliveries'))
    return render_template('customer_order.html', customer=customer,
                           products=products, active_page='customer_order')

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
        orders = [
            o for o in orders
            if search in (o.status or '').lower()
            or any(search in i.product.product_name.lower() for i in o.delivery_items)
        ]
    return render_template('customer_deliveries.html', orders=orders,
        search=search, date_from=date_from, date_to=date_to,
        status=status or 'All', active_page='customer_deliveries')


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
