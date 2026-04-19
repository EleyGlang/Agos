"""
════════════════════════════════════════════════════════
  HOW TO APPLY THESE CHANGES TO app.py
════════════════════════════════════════════════════════

STEP 1 ─ models.py
  Add the WaterTankLog class (see models_addition.py).
  Then run:  flask db migrate -m "add water tank log"
             flask db upgrade

STEP 2 ─ app.py top-level import
  In the "from models import (...)" block, add WaterTankLog:

    from models import (
        db, User, Customer, Product, Inventory,
        Sale, SaleItem, DeliveryOrder, DeliveryItem,
        Expense, LoyaltyTransaction, ActivityLog,
        Return_Model as Return, ReturnItem,
        WaterTankLog                          # ← ADD THIS
    )

STEP 3 ─ Replace review_return() with the version below.
  Find the existing function and swap it out wholesale.

STEP 4 ─ Add the Water Tank section below the RETURNS section.
════════════════════════════════════════════════════════
"""

# ══════════════════════════════════════════════════════
#  STEP 3  —  REPLACE review_return() WITH THIS VERSION
#  (Loyalty points are rolled back on refill-item returns)
# ══════════════════════════════════════════════════════

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


# ══════════════════════════════════════════════════════
#  STEP 4  —  ADD BELOW THE RETURNS SECTION IN app.py
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
