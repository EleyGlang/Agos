import os                           # Para ma-access variables sa .env file
from dotenv import load_dotenv      # Load variables galing sa .env file
load_dotenv()                       # Execute loading nung .env file

from flask import Flask, render_template, request, redirect, url_for, session, flash
# render_template: Nir-render yung mga HTML files para makita ng users
# request: Mga inputs ng user na sinesend ni browser sa system, nir-request niya sa system from user
# redirect: Nag r-redirect ng users sa mga HTMLs na gagamitin or pupuntahan nila
# url_for: Nag g-generate ng urls para sa mga route functions
# session: Nag s-store ng session data per use ng system per user
# flash: Nag p-pop up na notifications depende if success or error yung nangyari

from functools import wraps          # Nag p-preserve ng metadata
from datetime import datetime        # Pag manipulate nung date and time

# Database models - Ini-import mga tables sa models folder (Kilangan ng SQLAlcehmy)
from models import (
    db,                    
    User,                  
    Customer,              
    Product,               
    Inventory,             
    Sale,                  
    SaleItem,              
    DeliveryOrder,         
    DeliveryItem,          
    Expense,               
    LoyaltyTransaction     
)

from werkzeug.security import generate_password_hash, check_password_hash
# generate_password_hash: Cinoconvert yung simple text password tapos hinahash para more secure and harder for hackers
# check_password_hash: Nag v-verify if yung text password ay match sa hashed version

app = Flask(__name__, static_folder='static')

app.secret_key = os.environ.get('SECRET_KEY')

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')

db.init_app(app)



def login_required(f):
    @wraps(f)  # Preserves original function name and docstring
    def decorated(*args, **kwargs):
        # Check if nakalogin si user
        if 'user_id' not in session:
            flash('Please log in to continue.', 'error')
            return redirect(url_for('login'))
        # If nakalogin nga siya, continue normal execution system
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # Check kung naka login
        if 'user_id' not in session:
            flash('Please log in to continue.', 'error')
            return redirect(url_for('login'))
        
        # Check kung Admin ang role sa system
        if session.get('role') != 'Admin':
            flash('Admin access required.', 'error')
            return redirect(url_for('dashboard'))  
        
        # If both check = good, continue
        return f(*args, **kwargs)
    return decorated


@app.route('/')
def index():      
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """
   LOGIN PROCESS:
    1. Kunin username and password sa form
    2. Search sa database kung may credentials user
    3. Verify yung password gamit check_password_hash()
    4. Check account status (Active/Inactive)
    5. Store user info sa session, meaning si UserA ang current na gumagmit ng system
    6. Redirect papunta dashboard
    
    SECURITY FEATURES:
    - Passwords stored as bcrypt hashes, hindi plain text, for more security with user info
    - Sasabihin na wrong ang credentials PERO hindi sasabihin kung username or password ang mali
    - Inactive accounts napipigilan mag log in
    """
    
    # If nakalogin na user, skip na login and diretso dashboard
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    # Nag h-handle ng user form submissions para sa username and password
    if request.method == 'POST':
        # Extract form data, strip ginagamit para tanggalin yung whitespaces (e.g. "Lord Aron Galang")
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        # Check sa database if yung na input na username ay may match sa databaase
        # .first() returns User object or None
        user = User.query.filter_by(username=username).first()

        # check_password_hash cinocompare yung na input na password sa hashed password sa database
        if user and check_password_hash(user.password, password):
            
            # Chinecheck if deactivated yung account sa database
            if user.status == 'Inactive':
                flash('This account has been deactivated. Contact an administrator.', 'error')
                return render_template('login.html')

            # Nag s-store ng user info sa session
            session['user_id']   = user.user_id
            session['username']  = user.username
            session['role']      = user.role     
            session['full_name'] = user.full_name
            
            # Redirect to dashboard
            return redirect(url_for('dashboard'))
        else:
            #Sasabihin na wrong ang credentials PERO hindi sasabihin kung username or password ang mali
            flash('Invalid username or password.', 'error')


    return render_template('login.html')


@app.route('/logout')
@login_required  #Need nakalogin para makalogout (Mindset ba)
def logout():
    
    session.clear()  # Tinatanggal lahat ng session data
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required 
def dashboard():
      
    # Import SQL functions para sa database queries
    from sqlalchemy import func
    
    # Kinukuha date and time ngayon para mafilter data
    today = datetime.now().date()
    
    
    today_sales = db.session.query(
        func.coalesce(func.sum(Sale.total_amount), 0)
    ).filter(
        func.date(Sale.sale_date) == today
    ).scalar()  
    

    pending_deliveries = DeliveryOrder.query.filter_by(status='Pending').count()
    
    total_customers = Customer.query.count()
    
    recent_sales = Sale.query.order_by(Sale.sale_date.desc()).limit(5).all()
    
    if session['role'] == 'Admin':
        current_month = datetime.now().strftime('%Y-%m')
        
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
        
        
        net_profit = monthly_revenue - monthly_expenses
        
        low_stock_items = Inventory.query.filter(Inventory.quantity <= 10).count()
        
        
        return render_template(
            'dashboard_admin.html',
            today_sales=today_sales,
            monthly_revenue=monthly_revenue,
            monthly_expenses=monthly_expenses,
            net_profit=net_profit,
            pending_deliveries=pending_deliveries,
            total_customers=total_customers,
            low_stock_items=low_stock_items,
            recent_sales=recent_sales,
            active_page='dashboard'
        )
    
    else:
        items_in_stock = db.session.query(
            func.coalesce(func.sum(Inventory.quantity), 0)
        ).scalar()
        
        return render_template(
            'dashboard_operator.html',
            today_sales=today_sales,
            items_in_stock=items_in_stock,
            pending_deliveries=pending_deliveries,
            total_customers=total_customers,
            recent_sales=recent_sales,
            active_page='dashboard'
        )



@app.route('/sales')
@login_required
def sales():
    
    sales_list = Sale.query.order_by(Sale.sale_date.desc()).all()
    
    customers = Customer.query.order_by(Customer.full_name).all()
    
    products = Product.query.order_by(Product.product_name).all()
    
    return render_template('sales.html', sales=sales_list, customers=customers, products=products)
 
@app.route('/sales/new', methods=['POST'])
@login_required
def new_sale():
    """
    CREATE NEW SALE
    
    PROCESS FLOW:
    1. Get form data (customer, sale type, products, quantities)
    2. Handle "New Customer" creation if needed
    3. Calculate totals
    4. Apply loyalty points (if applicable)
    5. Deduct inventory
    6. Save sale to database
    7. Log loyalty transaction
    
    LOYALTY RULES:
    - 10 refills = 1 point
    - 1 point = 1 free refill
    """
  
    customer_id = request.form.get('customer_id') or None  # None if empty
    sale_type   = request.form.get('sale_type', 'Walk-in') 
    
    # Validate that delivery sales require a customer
    if sale_type == 'Delivery' and not customer_id:
        flash('Delivery sales require a customer to be selected or created.', 'error')
        return redirect(url_for('sales'))
    
    product_ids = request.form.getlist('product_id[]')  
    quantities  = request.form.getlist('quantity[]')  
    
    
    if customer_id == 'new':
        new_customer_name    = request.form.get('new_customer_name', '').strip()
        new_customer_number  = request.form.get('new_customer_number', '').strip()
        new_customer_address = request.form.get('new_customer_address', '').strip()
        
        if not new_customer_name:
            flash('Customer name is required when creating a new customer.', 'error')
            return redirect(url_for('sales'))

        # Phone number must be exactly 11 digits
        if new_customer_number and not new_customer_number.isdigit():
            flash('Contact number must only contain digits.', 'error')
            return redirect(url_for('sales'))
        if new_customer_number and len(new_customer_number) != 11:
            flash('Contact number must be exactly 11 digits.', 'error')
            return redirect(url_for('sales'))
        
        new_customer = Customer(
            full_name=new_customer_name,
            contact_number=new_customer_number,
            address=new_customer_address
        )
        
        db.session.add(new_customer)
        db.session.flush()  # Generates customer_id before commit
        
        customer_id = new_customer.customer_id
        flash(f'New customer "{new_customer_name}" added successfully!', 'success')
    
    total_amount = 0.0
    items_with_products = []  
    
    for product_id, qty_str in zip(product_ids, quantities):
        product_id = int(product_id)
        quantity   = int(qty_str)
        
        product = Product.query.get(product_id)
        if not product:
            continue  # Skip if product not found
        
        subtotal = float(product.price) * quantity
        total_amount += subtotal
        
        sale_item = SaleItem(
            product_id=product_id,
            quantity=quantity,
            price=product.price,
            subtotal=subtotal
        )
        
        items_with_products.append((sale_item, product))
    
    if customer_id:
        customer = Customer.query.get(customer_id)
        
        total_refills = sum(
            item.quantity for item, product in items_with_products
            if 'refill' in product.product_name.lower()
        )
        
        # If customer has loyalty points AND bought refills
        if customer.loyalty_points > 0 and total_refills > 0:
            # Calculate refill subtotal (only refill items)
            refill_items_total = sum(
                item.subtotal for item, product in items_with_products
                if 'refill' in product.product_name.lower()
            )
            
            # Use as many points as possible (max = number of refills)
            free_refills_used = min(customer.loyalty_points, total_refills)
            
            price_per_refill = refill_items_total / total_refills
            discount = price_per_refill * free_refills_used
            total_amount -= discount
            
            # Deduct used points from customer
            customer.loyalty_points -= free_refills_used
            
            # Log redemption in LoyaltyTransaction (negative = used points)
            redemption = LoyaltyTransaction(
                customer_id=customer_id,
                points_change=-free_refills_used,
                transaction_type='Redemption',
                description=f'Used {free_refills_used} point(s) for free refill(s)'
            )
            db.session.add(redemption)
            
            # Calculate remaining paid refills
            remaining_refills = total_refills - free_refills_used
        else:
            # No points to use
            remaining_refills = total_refills
        
        # 10 refills = 1 point (integer division)
        if remaining_refills > 0:
            new_points = remaining_refills // 10  
            leftover   = remaining_refills % 10   
            
            if new_points > 0:
                customer.loyalty_points += new_points
                
                earning = LoyaltyTransaction(
                    customer_id=customer_id,
                    points_change=new_points,
                    transaction_type='Earned',
                    description=f'Earned {new_points} point(s) from {remaining_refills} refill(s) ({leftover} towards next point)'
                )
                db.session.add(earning)
    
  
    
    sale = Sale(
        user_id=session['user_id'],       # Sino nag record ng sale
        customer_id=customer_id,          # Sinong customer (if meron, or None for walk-in)
        sale_type=sale_type,              # 'Walk-in' or 'Delivery'
        total_amount=total_amount,        # Total amount
        sale_date=datetime.now()          # Time sale was recorded
    )
    
    # Add sale to session
    db.session.add(sale)
    db.session.flush()  # Get sale_id before adding items
    
    
    for sale_item, product in items_with_products:
        sale_item.sale_id = sale.sale_id
        db.session.add(sale_item)
        
       
        inventory = Inventory.query.filter_by(product_id=product.product_id).first()
        if inventory:
           
            inventory.quantity = max(0, inventory.quantity - sale_item.quantity)
    
    
    try:
        db.session.commit()  # Save everything
        flash('Sale recorded successfully!', 'success')
    except Exception as e:
        db.session.rollback()  # Undo changes if error
        flash(f'Error recording sale: {str(e)}', 'error')
    
    return redirect(url_for('sales'))


@app.route('/user_management')
@login_required
@admin_required
def user_management():
    users = User.query.all()
    return render_template('user_management.html', users=users, active_page='user_management')


@app.route('/expense_management')
@login_required
@admin_required
def expense_management():
    # Placeholder for expense management
    flash('Expense management feature coming soon.', 'info')
    return redirect(url_for('dashboard'))



@app.route('/admin/users', methods=['GET', 'POST'])
@admin_required  
def create_user():
    """
    USER MANAGEMENT PAGE
    
    FEATURES:
    - Create new user accounts (Admin or Operator)
    - View all users
    - Activate/Deactivate accounts
    - Search users
    
    SECURITY:
    - Passwords hashed with bcrypt
    - Duplicate username/email prevented
    - Can't deactivate your own account
    """
    
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        username  = request.form.get('username', '').strip()
        password  = request.form.get('password', '').strip()
        role      = request.form.get('role', 'Operator')  
        
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists. Please choose another.', 'error')
            return redirect(url_for('create_user'))

        if not full_name or not all(char.isalpha() or char.isspace() for char in full_name):
            flash('Full name must contain only letters and spaces.', 'error')
            return redirect(url_for('create_user'))
            
        hashed_password = generate_password_hash(password)
        
        new_user = User(
            full_name=full_name,
            username=username,
            password=hashed_password,
            role=role,
            status='Active'
        )
        
        try:
            db.session.add(new_user)
            db.session.commit()
            flash(f'User {username} created successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating user: {str(e)}', 'error')
        
        return redirect(url_for('create_user'))
    
    users = User.query.order_by(User.user_id.desc()).all()
    return render_template('user_management.html', users=users)


@app.route('/admin/users/<int:user_id>/toggle', methods=['POST'])
@admin_required
def toggle_user_status(user_id):
    """
    ACTIVATE / DEACTIVATE USER ACCOUNT
    
    Toggles user status between 'Active' and 'Inactive'
    Inactive users cannot log in
    
    SECURITY:
    - Prevents admin from deactivating their own account
    """
    
    user = User.query.get_or_404(user_id)
    
    if user_id == session['user_id']:
        flash('You cannot deactivate your own account.', 'error')
        return redirect(url_for('create_user'))
    
    user.status = 'Inactive' if user.status == 'Active' else 'Active'
    
    try:
        db.session.commit()
        flash(f'User {user.username} is now {user.status}.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating user: {str(e)}', 'error')
    
    return redirect(url_for('create_user'))



@app.route('/customers', methods=['GET', 'POST'])
@login_required
def customers():
    """
    CUSTOMER MANAGEMENT PAGE
    
    FEATURES:
    - Add new customers
    - View all customers with loyalty points
    - Edit customer details
    - Search customers
    
    WHY TRACK CUSTOMERS?
    - Loyalty program (earn & redeem points)
    - Delivery address tracking
    - Sales history per customer
    """
    
    if request.method == 'POST':
        full_name      = request.form.get('full_name', '').strip()
        contact_number = request.form.get('contact_number', '').strip()
        address        = request.form.get('address', '').strip()
        
        if not full_name:
            flash('Customer name is required.', 'error')
            return redirect(url_for('customers'))

        if not all(char.isalpha() or char.isspace() for char in full_name):
            flash('Customer name must contain only letters and spaces.', 'error')
            return redirect(url_for('customers'))

        if contact_number:
            if not contact_number.isdigit():
                flash('Contact number must only contain digits.', 'error')
                return redirect(url_for('customers'))
            if len(contact_number) != 11:
                flash('Contact number must be exactly 11 digits.', 'error')
                return redirect(url_for('customers'))
        
        new_customer = Customer(
            full_name=full_name,
            contact_number=contact_number,
            address=address
        )
        
        try:
            db.session.add(new_customer)
            db.session.commit()
            flash(f'Customer {full_name} added successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding customer: {str(e)}', 'error')
        
        return redirect(url_for('customers'))
    
    customers_list = Customer.query.order_by(Customer.full_name).all()


@app.route('/customers/<int:customer_id>/edit', methods=['POST'])
@login_required
def edit_customer(customer_id):
    """
    EDIT CUSTOMER DETAILS
    
    Updates customer name, contact, or address
    """
    
    customer = Customer.query.get_or_404(customer_id)
    
    customer.full_name      = request.form.get('full_name', customer.full_name).strip()
    customer.contact_number = request.form.get('contact_number', customer.contact_number).strip()
    customer.address        = request.form.get('address', customer.address).strip()
    
    try:
        db.session.commit()
        flash(f'Customer {customer.full_name} updated successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating customer: {str(e)}', 'error')
    
    return redirect(url_for('customers'))


@app.route('/inventory', methods=['GET', 'POST'])
@login_required
def inventory():
    """
    INVENTORY PAGE
    
    FEATURES:
    - View current stock levels
    - Manually adjust stock (add/deduct)
    - Low stock alerts
    
    AUTO-DEDUCTION:
    - Stock automatically deducted when sale is recorded
    - Stock automatically deducted when delivery is marked "Delivered"
    """
    
    if request.method == 'POST':
        product_id = int(request.form.get('product_id'))
        action     = request.form.get('action')     
        qty_change = int(request.form.get('quantity'))
        
        item = Inventory.query.filter_by(product_id=product_id).first()
        
        if not item:
            flash('Inventory item not found.', 'error')
            return redirect(url_for('inventory'))
        
        if action == 'add':
            item.quantity += qty_change
            flash(f'Added {qty_change} units to {item.product.product_name}.', 'success')
        
        elif action == 'deduct':
            if item.quantity < qty_change:
                flash('Not enough stock to deduct!', 'error')
                return redirect(url_for('inventory'))
            
            item.quantity -= qty_change
            flash(f'Deducted {qty_change} units from {item.product.product_name}.', 'success')
        
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            flash(f'Error adjusting inventory: {str(e)}', 'error')
        
        return redirect(url_for('inventory'))
    
    inventory_items = Inventory.query.all()
    products = Product.query.all()
  


@app.route('/deliveries', methods=['GET', 'POST'])
@login_required
def deliveries():
    """
    DELIVERY MANAGEMENT PAGE
    
    FEATURES:
    - Create delivery orders
    - Track delivery status (Pending/Delivered)
    - View delivery history
    
    WORKFLOW:
    1. Create delivery (Status: Pending)
    2. Mark as Delivered
    3. Auto-creates Sale record
    4. Auto-deducts inventory
    """
    
    if request.method == 'POST':
        customer_id    = int(request.form.get('customer_id'))
        delivery_date  = request.form.get('delivery_date')
        notes          = request.form.get('notes', '').strip()
        product_ids    = request.form.getlist('product_id[]')
        quantities     = request.form.getlist('quantity[]')
        
        delivery = DeliveryOrder(
            customer_id=customer_id,
            delivery_date=delivery_date,
            notes=notes,
            status='Pending'  
        )
        
        db.session.add(delivery)
        db.session.flush() 
        
        total_amount = 0.0
        for product_id, qty_str in zip(product_ids, quantities):
            product_id = int(product_id)
            quantity   = int(qty_str)
            
            product = Product.query.get(product_id)
            if not product:
                continue
            
            subtotal = float(product.price) * quantity
            total_amount += subtotal
            
            delivery_item = DeliveryItem(
                delivery_id=delivery.delivery_id,
                product_id=product_id,
                quantity=quantity,
                price=product.price,
                subtotal=subtotal
            )
            db.session.add(delivery_item)
        
        delivery.total_amount = total_amount
        
        try:
            db.session.commit()
            flash('Delivery order created successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating delivery: {str(e)}', 'error')
        
        return redirect(url_for('deliveries'))
    
    deliveries_list = DeliveryOrder.query.order_by(DeliveryOrder.delivery_date.desc()).all()
    customers = Customer.query.order_by(Customer.full_name).all()
    products = Product.query.all()
    
  
@app.route('/deliveries/<int:delivery_id>/status', methods=['POST'])
@login_required
def update_delivery_status(delivery_id):
    """
    UPDATE DELIVERY STATUS
    
    When status changes to "Delivered":
    1. Auto-creates Sale record
    2. Copies items from delivery to sale
    3. Deducts inventory
 
    """
    
    delivery = DeliveryOrder.query.get_or_404(delivery_id)
    new_status = request.form.get('status')
    
    if new_status == 'Delivered' and delivery.status != 'Delivered':
        
        sale = Sale(
            user_id=session['user_id'],
            customer_id=delivery.customer_id,
            sale_type='Delivery',
            total_amount=delivery.total_amount,
            sale_date=datetime.now()
        )
        
        db.session.add(sale)
        db.session.flush()  # Get sale_id
        
        for delivery_item in delivery.delivery_items:
            sale_item = SaleItem(
                sale_id=sale.sale_id,
                product_id=delivery_item.product_id,
                quantity=delivery_item.quantity,
                price=delivery_item.price,
                subtotal=delivery_item.subtotal
            )
            db.session.add(sale_item)
            
            # Deduct inventory
            inventory = Inventory.query.filter_by(product_id=delivery_item.product_id).first()
            if inventory:
                inventory.quantity = max(0, inventory.quantity - delivery_item.quantity)
    
    # Update delivery status
    delivery.status = new_status
    
    try:
        db.session.commit()
        flash(f'Delivery status updated to {new_status}.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating delivery: {str(e)}', 'error')
    
    return redirect(url_for('deliveries'))


@app.route('/expenses', methods=['GET', 'POST'])
@admin_required  
def expenses():
    """
    EXPENSE MANAGEMENT PAGE
    
    FEATURES:
    - Record business expenses
    - Categorize expenses (Utilities, Supplies, etc.)
    - View expense history
    
    WHY TRACK EXPENSES?
    - Calculate net profit (Revenue - Expenses)
    - Budget planning
    - Tax preparation
    - Identify cost-saving opportunities
    """
    
    if request.method == 'POST':
        category     = request.form.get('category', '').strip()
        description  = request.form.get('description', '').strip()
        amount       = float(request.form.get('amount'))
        expense_date = request.form.get('expense_date')
        
        expense = Expense(
            user_id=session['user_id'],  
            category=category,
            description=description,
            amount=amount,
            expense_date=expense_date
        )
        
        try:
            db.session.add(expense)
            db.session.commit()
            flash('Expense recorded successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error recording expense: {str(e)}', 'error')
        
        return redirect(url_for('expenses'))
    
    expenses_list = Expense.query.order_by(Expense.expense_date.desc()).all()
    return render_template('expenses.html', expenses=expenses_list)


@app.route('/expenses/<int:expense_id>/delete', methods=['POST'])
@admin_required
def delete_expense(expense_id):
    """
    DELETE EXPENSE RECORD
    
    Permanently removes expense from database
    """
    
    expense = Expense.query.get_or_404(expense_id)
    
    try:
        db.session.delete(expense)
        db.session.commit()
        flash('Expense deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting expense: {str(e)}', 'error')
    
    return redirect(url_for('expenses'))


@app.route('/reports')
@admin_required
def reports():
    """
    FINANCIAL REPORTS PAGE
    
    FEATURES:
    - Monthly revenue vs expenses
    - Net profit calculation
    - Expense breakdown by category
    - Sales trends
    
    DEFAULT: Current month report
    Can filter by month using query parameter
    """
    
    from sqlalchemy import func
    
    month = request.args.get('month', datetime.now().strftime('%Y-%m'))
    
   
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
    
   
    net_profit = total_revenue - total_expenses
   
    by_category = db.session.query(
        Expense.category,
        func.sum(Expense.amount).label('total')
    ).filter(
        func.date_format(Expense.expense_date, '%Y-%m') == month
    ).group_by(Expense.category).all()
    
   
    sales_count = Sale.query.filter(
        func.date_format(Sale.sale_date, '%Y-%m') == month
    ).count()
    
    return render_template('reports.html',
                         month=month,
                         total_revenue=total_revenue,
                         total_expenses=total_expenses,
                         net_profit=net_profit,
                         by_category=by_category,
                         sales_count=sales_count)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)