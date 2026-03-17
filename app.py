import os
from dotenv import load_dotenv
load_dotenv()

from flask import (
    Flask, render_template, request,
    redirect, url_for, session, flash
)
from functools import wraps
from datetime import datetime

from models import (
    db,
    User, Customer, Product, Inventory,
    Sale, SaleItem, DeliveryOrder, DeliveryItem,
    Expense, LoyaltyTransaction
)
from werkzeug.security import generate_password_hash, check_password_hash

# ─────────────────────────────────────────
# APP CONFIG
# ─────────────────────────────────────────
app = Flask(__name__, static_folder='static')
app.secret_key = os.environ.get('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI']    = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)


# ─────────────────────────────────────────
# AUTH DECORATORS
# ─────────────────────────────────────────
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
        if session.get('role') != 'Admin':
            flash('Admin access required.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated



# ─────────────────────────────────────────
# AUTH ROUTES
# ─────────────────────────────────────────
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    # If already logged in, skip login page entirely
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        user = User.query.filter_by(username=username).first()

        # Backend handles role — user only provides credentials.
        # If username exists and password matches, let them in.
        # The dashboard route then reads session['role'] to decide
        # which template to serve.
        if user and check_password_hash(user.password, password):
            # Only allow active accounts to log in
            if user.status == 'Inactive':
                flash('This account has been deactivated. Contact your administrator.', 'error')
                return render_template('login.html')

            session['user_id']   = user.user_id
            session['username']  = user.username
            session['role']      = user.role
            session['full_name'] = user.full_name
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password.', 'error')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))


# ─────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────
@app.route('/dashboard')
@login_required
def dashboard():
    from sqlalchemy import func
    today         = datetime.utcnow().date()
    current_month = datetime.utcnow().strftime('%Y-%m')

    # Stats shared by both roles
    today_sales = db.session.query(
        func.coalesce(func.sum(Sale.total_amount), 0)
    ).filter(func.date(Sale.sale_date) == today).scalar()

    pending_deliveries = DeliveryOrder.query.filter_by(status='Pending').count()
    total_customers    = Customer.query.count()

    # Recent sales shown in the dashboard table (latest 5)
    recent_sales = Sale.query.order_by(Sale.sale_date.desc()).limit(5).all()

    if session['role'] == 'Admin':
        low_stock = Inventory.query.filter(
            Inventory.quantity <= Inventory.minimum_stock
        ).count()

        monthly_revenue = db.session.query(
            func.coalesce(func.sum(Sale.total_amount), 0)
        ).filter(
            func.date_format(Sale.sale_date, '%Y-%m') == current_month
        ).scalar()

        monthly_expenses = db.session.query(
            func.coalesce(func.sum(Expense.amount), 0)
        ).filter(
            func.date_format(Expense.expense_date, '%Y-%m') == current_month
        ).scalar()

        return render_template('dashboard_admin.html',
            today_sales        = today_sales,
            pending_deliveries = pending_deliveries,
            total_customers    = total_customers,
            low_stock          = low_stock,
            monthly_revenue    = monthly_revenue,
            monthly_expenses   = monthly_expenses,
            net_profit         = float(monthly_revenue) - float(monthly_expenses),
            recent_sales       = recent_sales
        )

    # Operator dashboard needs stock count and pending delivery list
    items_in_stock = db.session.query(
        func.coalesce(func.sum(Inventory.quantity), 0)
    ).scalar()

    # First 5 pending deliveries shown in the queue preview card
    pending_delivery_list = DeliveryOrder.query.filter_by(
        status='Pending'
    ).order_by(DeliveryOrder.created_at.desc()).limit(5).all()

    return render_template('dashboard_operator.html',
        today_sales          = today_sales,
        pending_deliveries   = pending_deliveries,
        total_customers      = total_customers,
        items_in_stock       = items_in_stock,
        recent_sales         = recent_sales,
        pending_delivery_list = pending_delivery_list
    )


# ─────────────────────────────────────────
# USER MANAGEMENT  (Admin only)
# ─────────────────────────────────────────
@app.route('/admin/users', methods=['GET', 'POST'])
@admin_required
def create_user():
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        username  = request.form.get('username',  '').strip()
        email     = request.form.get('email',     '').strip()
        password  = request.form.get('password',  '').strip()
        role      = request.form.get('role', 'Operator')

        if not all([full_name, username, email, password]):
            flash('All fields are required.', 'error')
            return redirect(url_for('create_user'))

        new_user = User(
            full_name = full_name,
            username  = username,
            email     = email,
            password  = generate_password_hash(password),
            role      = role,
            status    = 'Active'
        )
        try:
            db.session.add(new_user)
            db.session.commit()
            flash(f'Account created for {full_name}.', 'success')
        except Exception:
            db.session.rollback()
            flash('Username or email already exists.', 'error')

        return redirect(url_for('create_user'))

    # Pass all users to populate the accounts table on the right side
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('user_management.html', users=users)


@app.route('/admin/users/<int:user_id>/toggle', methods=['POST'])
@admin_required
def toggle_user_status(user_id):
    # Prevent admin from deactivating their own account
    if user_id == session['user_id']:
        flash('You cannot deactivate your own account.', 'error')
        return redirect(url_for('create_user'))

    user = User.query.get(user_id)
    if not user:
        flash('User not found.', 'error')
        return redirect(url_for('create_user'))

    # Flip the status
    user.status = 'Inactive' if user.status == 'Active' else 'Active'
    db.session.commit()
    flash(f'{user.full_name} has been {"deactivated" if user.status == "Inactive" else "activated"}.', 'success')
    return redirect(url_for('create_user'))


# ─────────────────────────────────────────
# SALES  (Both roles)
# ─────────────────────────────────────────
@app.route('/sales')
@login_required
def sales():
    all_sales = Sale.query.order_by(Sale.sale_date.desc()).all()
    customers = Customer.query.order_by(Customer.full_name).all()
    products  = Product.query.filter_by(is_active=True).order_by(Product.product_name).all()
    return render_template('sales.html',
        sales     = all_sales,
        customers = customers,
        products  = products
    )


@app.route('/sales/new', methods=['POST'])
@login_required
def new_sale():
    customer_id = request.form.get('customer_id') or None
    sale_type   = request.form.get('sale_type', 'Walk-in')
    product_ids = request.form.getlist('product_id[]')
    quantities  = request.form.getlist('quantity[]')

    if not product_ids:
        flash('Please add at least one product.', 'error')
        return redirect(url_for('sales'))

    # Build line items and compute total
    items        = []
    total_amount = 0

    for product_id, qty_str in zip(product_ids, quantities):
        if not product_id:
            continue
        product  = Product.query.get(int(product_id))
        quantity = int(qty_str) if qty_str else 1
        subtotal = float(product.price) * quantity
        total_amount += subtotal

        items.append(SaleItem(
            product_id = product.product_id,
            quantity   = quantity,
            price      = product.price,
            subtotal   = subtotal
        ))

        # Deduct from inventory automatically
        inventory = Inventory.query.filter_by(product_id=product.product_id).first()
        if inventory:
            inventory.quantity = max(0, inventory.quantity - quantity)

    if not items:
        flash('Please select a valid product.', 'error')
        return redirect(url_for('sales'))

    sale = Sale(
        customer_id  = int(customer_id) if customer_id else None,
        user_id      = session['user_id'],
        sale_type    = sale_type,
        total_amount = total_amount
    )
    db.session.add(sale)
    # flush() gets the generated sale_id before we commit,
    # so we can attach it to the sale_items and loyalty_transaction below
    db.session.flush()

    for item in items:
        item.sale_id = sale.sale_id
        db.session.add(item)

    # Loyalty points — only for registered customers
    if customer_id:
        customer = Customer.query.get(int(customer_id))
        if customer:
            customer.loyalty_points += 1
            loyalty = LoyaltyTransaction(
                customer_id      = customer.customer_id,
                sale_id          = sale.sale_id,
                points_earned    = 1
            )
            db.session.add(loyalty)
            if customer.loyalty_points % 10 == 0:
                flash(f'🎉 {customer.full_name} has earned a free refill!', 'success')

    db.session.commit()
    flash('Sale recorded successfully.', 'success')
    return redirect(url_for('sales'))


# ─────────────────────────────────────────
# INVENTORY
# ─────────────────────────────────────────
@app.route('/inventory')
@login_required
def inventory():
    items     = Inventory.query.all()
    low_stock = [i for i in items if i.quantity <= i.minimum_stock]
    return render_template('inventory.html', items=items, low_stock=low_stock)


@app.route('/inventory/update', methods=['POST'])
@login_required
def update_inventory():
    inventory_id = request.form.get('inventory_id', type=int)
    action       = request.form.get('action')
    qty_change   = request.form.get('quantity', type=int, default=0)

    item = Inventory.query.get(inventory_id)
    if not item:
        flash('Item not found.', 'error')
        return redirect(url_for('inventory'))

    if action == 'add':
        item.quantity += qty_change
    elif action == 'deduct':
        if item.quantity < qty_change:
            flash('Not enough stock to deduct that amount.', 'error')
            return redirect(url_for('inventory'))
        item.quantity -= qty_change

    db.session.commit()
    flash('Inventory updated.', 'success')
    return redirect(url_for('inventory'))


# ─────────────────────────────────────────
# CUSTOMERS
# ─────────────────────────────────────────
@app.route('/customers')
@login_required
def customers():
    all_customers = Customer.query.order_by(Customer.full_name).all()
    return render_template('customers.html', customers=all_customers)


@app.route('/customers/new', methods=['POST'])
@login_required
def new_customer():
    full_name      = request.form.get('full_name', '').strip()
    contact_number = request.form.get('contact_number', '').strip()
    address        = request.form.get('address', '').strip()

    if not full_name:
        flash('Full name is required.', 'error')
        return redirect(url_for('customers'))

    customer = Customer(
        full_name      = full_name,
        contact_number = contact_number,
        address        = address
    )
    db.session.add(customer)
    db.session.commit()
    flash(f'{full_name} added successfully.', 'success')
    return redirect(url_for('customers'))


@app.route('/customers/<int:customer_id>/edit', methods=['POST'])
@login_required
def edit_customer(customer_id):
    customer = Customer.query.get(customer_id)
    if not customer:
        flash('Customer not found.', 'error')
        return redirect(url_for('customers'))

    customer.full_name      = request.form.get('full_name', '').strip()
    customer.contact_number = request.form.get('contact_number', '').strip()
    customer.address        = request.form.get('address', '').strip()
    db.session.commit()
    flash('Customer updated.', 'success')
    return redirect(url_for('customers'))


@app.route('/customers/<int:customer_id>/delete', methods=['POST'])
@admin_required
def delete_customer(customer_id):
    customer = Customer.query.get(customer_id)
    if not customer:
        flash('Customer not found.', 'error')
        return redirect(url_for('customers'))

    db.session.delete(customer)
    db.session.commit()
    flash('Customer deleted.', 'success')
    return redirect(url_for('customers'))


# ─────────────────────────────────────────
# DELIVERIES
# ─────────────────────────────────────────
@app.route('/deliveries')
@login_required
def deliveries():
    all_deliveries = DeliveryOrder.query.order_by(DeliveryOrder.created_at.desc()).all()
    customers      = Customer.query.order_by(Customer.full_name).all()
    products       = Product.query.filter_by(is_active=True).order_by(Product.product_name).all()
    return render_template('deliveries.html',
        deliveries = all_deliveries,
        customers  = customers,
        products   = products
    )


@app.route('/deliveries/new', methods=['POST'])
@login_required
def new_delivery():
    customer_id   = request.form.get('customer_id', type=int)
    delivery_date = request.form.get('delivery_date')
    notes         = request.form.get('notes', '').strip()
    product_ids   = request.form.getlist('product_id[]')
    quantities    = request.form.getlist('quantity[]')

    delivery = DeliveryOrder(
        customer_id   = customer_id,
        user_id       = session['user_id'],
        delivery_date = delivery_date,
        notes         = notes
    )
    db.session.add(delivery)
    db.session.flush()

    for product_id, qty_str in zip(product_ids, quantities):
        if not product_id:
            continue
        product  = Product.query.get(int(product_id))
        quantity = int(qty_str) if qty_str else 1
        subtotal = float(product.price) * quantity
        db.session.add(DeliveryItem(
            delivery_id = delivery.delivery_id,
            product_id  = product.product_id,
            quantity    = quantity,
            price       = product.price,
            subtotal    = subtotal
        ))

    db.session.commit()
    flash('Delivery order created.', 'success')
    return redirect(url_for('deliveries'))


@app.route('/deliveries/<int:delivery_id>/status', methods=['POST'])
@login_required
def update_delivery_status(delivery_id):
    delivery   = DeliveryOrder.query.get(delivery_id)
    new_status = request.form.get('status')

    if not delivery:
        flash('Delivery not found.', 'error')
        return redirect(url_for('deliveries'))

    delivery.status = new_status

    # When marked Delivered, auto-create a sale record
    if new_status == 'Delivered':
        total_amount = sum(float(i.subtotal) for i in delivery.delivery_items)
        sale = Sale(
            customer_id  = delivery.customer_id,
            user_id      = session['user_id'],
            sale_type    = 'Delivery',
            total_amount = total_amount
        )
        db.session.add(sale)
        db.session.flush()

        for d_item in delivery.delivery_items:
            db.session.add(SaleItem(
                sale_id    = sale.sale_id,
                product_id = d_item.product_id,
                quantity   = d_item.quantity,
                price      = d_item.price,
                subtotal   = d_item.subtotal
            ))
            # Deduct inventory
            inv = Inventory.query.filter_by(product_id=d_item.product_id).first()
            if inv:
                inv.quantity = max(0, inv.quantity - d_item.quantity)

    db.session.commit()
    flash(f'Delivery marked as {new_status}.', 'success')
    return redirect(url_for('deliveries'))


# ─────────────────────────────────────────
# EXPENSES
# ─────────────────────────────────────────
@app.route('/expenses')
@login_required
def expenses():
    all_expenses = Expense.query.order_by(Expense.expense_date.desc()).all()
    return render_template('expenses.html', expenses=all_expenses)


@app.route('/expenses/new', methods=['POST'])
@login_required
def new_expense():
    expense = Expense(
        user_id      = session['user_id'],
        category     = request.form.get('category', '').strip(),
        description  = request.form.get('description', '').strip(),
        amount       = request.form.get('amount', type=float),
        expense_date = request.form.get('expense_date')
    )
    db.session.add(expense)
    db.session.commit()
    flash('Expense logged.', 'success')
    return redirect(url_for('expenses'))


@app.route('/expenses/<int:expense_id>/edit', methods=['POST'])
@login_required
def edit_expense(expense_id):
    expense = Expense.query.get(expense_id)
    if not expense:
        flash('Expense not found.', 'error')
        return redirect(url_for('expenses'))

    expense.category     = request.form.get('category', '').strip()
    expense.description  = request.form.get('description', '').strip()
    expense.amount       = request.form.get('amount', type=float)
    expense.expense_date = request.form.get('expense_date')
    db.session.commit()
    flash('Expense updated.', 'success')
    return redirect(url_for('expenses'))


@app.route('/expenses/<int:expense_id>/delete', methods=['POST'])
@admin_required
def delete_expense(expense_id):
    expense = Expense.query.get(expense_id)
    if not expense:
        flash('Expense not found.', 'error')
        return redirect(url_for('expenses'))

    db.session.delete(expense)
    db.session.commit()
    flash('Expense deleted.', 'success')
    return redirect(url_for('expenses'))


# ─────────────────────────────────────────
# REPORTS  (Admin only)
# ─────────────────────────────────────────
@app.route('/reports')
@admin_required
def reports():
    from sqlalchemy import func

    month = request.args.get('month', datetime.utcnow().strftime('%Y-%m'))

    total_revenue = db.session.query(
        func.coalesce(func.sum(Sale.total_amount), 0)
    ).filter(
        func.date_format(Sale.sale_date, '%Y-%m') == month
    ).scalar()

    total_expenses = db.session.query(
        func.coalesce(func.sum(Expense.amount), 0)
    ).filter(
        func.date_format(Expense.expense_date, '%Y-%m') == month
    ).scalar()

    by_category = db.session.query(
        Expense.category,
        func.sum(Expense.amount).label('total')
    ).filter(
        func.date_format(Expense.expense_date, '%Y-%m') == month
    ).group_by(Expense.category).all()

    deliveries = DeliveryOrder.query.filter(
        func.date_format(DeliveryOrder.created_at, '%Y-%m') == month
    ).all()

    return render_template('reports.html',
        month          = month,
        total_revenue  = total_revenue,
        total_expenses = total_expenses,
        net_profit     = float(total_revenue) - float(total_expenses),
        by_category    = by_category,
        deliveries     = deliveries
    )


# ─────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
