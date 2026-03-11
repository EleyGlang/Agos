import os
from dotenv import load_dotenv

load_dotenv()

from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mysqldb import MySQL
from functools import wraps
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from config import DevelopmentConfig
from models import db
from models import User, Customer, Product, Inventory, Sale, SaleItem, DeliveryOrder, DeliveryItem, Expense, LoyaltyTransaction


app = Flask(__name__)

app.config.from_object(DevelopmentConfig)

db.init_app(app)

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
            flash('Please log in to continue.','error')
            return redirect(url_for('login'))
        if session.get('role') != 'Admin':
            flash('Admin access is required!', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated

    @app.route('/')
    def index():
        if 'user_id' in session:
            return redirect(url_for('dashboard'))
        return render_template('login.html')

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '').strip()
            role = request.form.get('role', 'Operator')

            user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password) and user.role == role:
            session['user_id']  = user.user_id
            session['username'] = user.username
            session['role']     = user.role
            session['full_name'] = user.full_name
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials or wrong role selected.', 'error')

    return render_template('login.html')

    @app.route('/logout')
    @login_required
    def logout():
        session.clear()
        flash('Logout Successful.', 'success')
        return redirect(url_for('login'))

    @app.route('admin/create-user', methods=['GET', 'POST'])
    @admin_required
    def create_user():
         if request.method == 'POST':
            full_name = request.form.get('full_name', '').strip()
            username  = request.form.get('username',  '').strip()
            email     = request.form.get('email',     '').strip()
            password  = request.form.get('password',  '').strip()
            role      = request.form.get('role', 'Operator')

            new_user = User(
                full_name = full_name,
                username = username,
                email = email,
                password = generate_password_hash(password),
                role = role
            )

            try:
            # add() stages the object, commit() writes it to MySQL.
                db.session.add(new_user)
                db.session.commit()
                flash(f'Account created for {full_name}.', 'success')
            except Exception:
                # rollback() undoes the failed transaction so the
                # session stays clean for the next operation.
                db.session.rollback()
                flash('Username or email already exists.', 'error')

            return redirect(url_for('create_user'))

    return render_template('create_user.html')

    @app.route('/dashboard')
    @login_required
    def dashboard():
        from sqlalchemy import func
        today = datetime.utcnown().date()

        today_sales = db.session.query(func.coalesce(func.sum(Sale.total_amount), 0)).filter(func.data(Sale.sale_date) == today).scalar()

        pending_deliveries = DeliveryOrder.query.filter_by(status='Pending').count()
        total_customers = Customer.query.count()

        stats = {
            'today_sales':        today_sales,
            'pending_deliveries': pending_deliveries,
            'total_customers':    total_customers, 
        }
