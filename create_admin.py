from app import app, db, User
from werkzeug.security import generate_password_hash

with app.app_context():
    # Delete any existing admin first
    existing_admin = User.query.filter_by(username='admin').first()
    if existing_admin:
        db.session.delete(existing_admin)
        db.session.commit()
        print("Deleted existing admin")
    
    # Create new admin with fresh password hash
    password_hash = generate_password_hash('agos2019')
    print(f"Generated password hash: {password_hash}\n")
    
    admin = User(
        first_name='Admin',
        last_name='User',
        username='admin',
        password=password_hash,
        role='Admin',
        status='Active'
    )
    
    db.session.add(admin)
    db.session.commit()
    
    # Verify it was created
    verify = User.query.filter_by(username='admin').first()
    if verify:
        print("✓ Admin created successfully!")
        print(f"  Username: {verify.username}")
        print(f"  Role: {verify.role}")
        print(f"  Status: {verify.status}")
        
        # Test the password
        from werkzeug.security import check_password_hash
        if check_password_hash(verify.password, 'agos2019'):
            print("Password verification works!")
        else:
            print("Password verification FAILED")
    else:
        print("Failed to create admin")