from app import app, db
from models import User
from werkzeug.security import generate_password_hash

with app.app_context():
    admin = User(
        user_first_name='Carlos',
        user_last_name='Carlosa',
        email='carlos@admin.com',
        number='3112978483',
        password=generate_password_hash('admin123'),  # Cambia por la contraseña que quieras
        is_admin=True
    )
    db.session.add(admin)
    db.session.commit()
    print("✅ Usuario admin creado correctamente.")
