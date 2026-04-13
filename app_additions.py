"""
app_additions.py
================
Add these additions to your existing app.py file.

1. ADD the landing route near the top of your routes (after the index route).
2. UPDATE the index() function to redirect to landing if not logged in.
3. ADD 'active_page' variable to every route that renders a page with a sidebar.

─────────────────────────────────────────────────────────
CHANGE 1: Update index() to redirect to landing page
─────────────────────────────────────────────────────────

Replace this:
    @app.route('/')
    def index():
        return redirect(url_for('dashboard') if 'user_id' in session else url_for('login'))

With this:
    @app.route('/')
    def index():
        if 'user_id' in session:
            return redirect(url_for('dashboard'))
        if 'customer_id' in session:
            return redirect(url_for('customer_dashboard'))
        return redirect(url_for('landing'))

─────────────────────────────────────────────────────────
CHANGE 2: Add landing route (paste this into app.py)
─────────────────────────────────────────────────────────
"""

# ── Landing Page ──────────────────────────────────────
# Add this route to app.py just before or after the login route.

# @app.route('/landing')
# def landing():
#     # Redirect logged-in users straight to their dashboard
#     if 'user_id' in session:
#         return redirect(url_for('dashboard'))
#     if 'customer_id' in session:
#         return redirect(url_for('customer_dashboard'))
#     return render_template('landing.html')


"""
─────────────────────────────────────────────────────────
CHANGE 3: Add active_page to every route render_template call
─────────────────────────────────────────────────────────

The unified sidebar uses active_page to highlight the current link.
Add active_page='<key>' to each render_template call in app.py.

Key mapping:
  dashboard        → active_page='dashboard'
  sales            → active_page='sales'
  inventory        → active_page='inventory'
  products         → active_page='products'
  customers        → active_page='customers'
  deliveries       → active_page='deliveries'
  user_management  → active_page='user_management'
  expenses / expense_management → active_page='expenses'
  reports          → active_page='reports'
  activity_log     → active_page='activity_log'

  Customer routes:
  customer_dashboard   → active_page='customer_dashboard'
  customer_order       → active_page='customer_order'
  customer_deliveries  → active_page='customer_deliveries'

Example — update the dashboard route:

    return render_template('dashboard_admin.html',
        today_sales=today_sales,
        ...
        active_page='dashboard')   # ← ADD THIS

─────────────────────────────────────────────────────────
CHANGE 4: customer_login route — redirect to landing if not logged in
─────────────────────────────────────────────────────────

In the customer_login view, after checking for sessions, you may want
to add a landing link. No code change needed beyond adding the landing route.
"""

# ── COPY-PASTE READY: Full landing route block ──────────────────

LANDING_ROUTE = """
@app.route('/landing')
def landing():
    \"\"\"Public landing page — redirects logged-in users to their dashboard.\"\"\"
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    if 'customer_id' in session:
        return redirect(url_for('customer_dashboard'))
    return render_template('landing.html')
"""

# ── COPY-PASTE READY: Updated index route ────────────────────────

INDEX_ROUTE = """
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    if 'customer_id' in session:
        return redirect(url_for('customer_dashboard'))
    return redirect(url_for('landing'))
"""

if __name__ == '__main__':
    print("=== app_additions.py ===")
    print("Copy LANDING_ROUTE into app.py")
    print("Replace the existing index() with INDEX_ROUTE")
    print("Add active_page='<key>' to every render_template call")
    print(LANDING_ROUTE)
    print(INDEX_ROUTE)
