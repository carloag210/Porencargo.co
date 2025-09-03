from flask import flash, Flask, request, render_template, redirect, url_for, session
from extencions import db, init_extencions, login_manager
from models import User, Paquete, EstadoPaquete, Direccion, Producto
from config import Config
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from flask_mail import Mail, Message
from auth.decorators import admin_required
from werkzeug.utils import secure_filename
from datetime import timedelta
import os

# Inicialización de la app
app = Flask(__name__, static_folder='assets', template_folder='templates')
app.config.from_object(Config)

# --- Configuración de la base de datos ---
if os.environ.get("FLASK_ENV") == "development":
    # ENTORNO LOCAL (SQLite)
    app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///porencargo_local.db"
else:
    # PRODUCCIÓN (Railway)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_LINK")
    if app.config['SQLALCHEMY_DATABASE_URI'] and app.config['SQLALCHEMY_DATABASE_URI'].startswith("postgres://"):
        app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace("postgres://", "postgresql://", 1)
    # Forzar SSL en producción
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        "connect_args": {"sslmode": "require"}
    }

# Carpeta de uploads
app.config['UPLOAD_FOLDER'] = 'assets/img_productos'

# Inicialización de extensiones
db.init_app(app)
login_manager.init_app(app)

with app.app_context():
    db.create_all()

# Configuración de sesiones
app.secret_key = os.urandom(24)
app.permanent_session_lifetime = timedelta(days=7)

# Configuración de correo
app.config['MAIL_SERVER'] = 'smtp.purelymail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USERNAME'] = 'logistica@porencargo.co'
app.config['MAIL_PASSWORD'] = 'Carlos161809Aguado*2025*'
app.config['MAIL_DEFAULT_SENDER'] = 'logistica@porencargo.co'
mail = Mail(app)

# ------------------- Rutas -------------------

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login_register')
def login_register():
    return render_template('login_register.html')

@app.route('/rastrea_tu_orden')
def rastrea_tu_orden():
    return render_template('rastrea_tu_orden.html')

@app.route('/productos')
def productos():
    productos = Producto.query.all()
    return render_template('productos.html', productos=productos)

@app.route('/producto/<int:id>')
def producto_detalle(id):
    producto = Producto.query.get_or_404(id)
    return render_template('producto_detalle.html', producto=producto)

# ------------------- ADMIN -------------------

@app.route('/admin_panel_add_productos')
@admin_required
def admin_panel_add_productos():
    return render_template("admin_panel_add_productos.html")

@app.route('/admin_panel_ver_usuarios')
@admin_required
def admin_panel_ver_usuarios():
    usuarios = User.query.all()
    paquetes = Paquete.query.all()
    productos = Producto.query.all()
    estados_posibles = list(EstadoPaquete)
    return render_template(
        'admin_panel_ver_usuarios.html', 
        usuarios=usuarios, 
        paquetes=paquetes,
        estados_posibles=estados_posibles,
        productos=productos
    )

@app.route('/admin_panel_modificar_productos/<int:id>', methods=['GET', 'POST'])
@admin_required
def admin_panel_modificar_productos(id):
    producto = Producto.query.get_or_404(id)
    if request.method == 'POST':
        producto.nombre = request.form['nombre']
        producto.precio = request.form['precio']
        producto.peso = request.form['peso']
        producto.categoria = request.form['categoria']

        nueva_imagen = request.files['imagen']
        if nueva_imagen:
            nombre_archivo = secure_filename(nueva_imagen.filename)
            ruta_relativa = os.path.join('img_productos', nombre_archivo)
            ruta_completa = os.path.join(app.config['UPLOAD_FOLDER'], nombre_archivo)
            nueva_imagen.save(ruta_completa)
            producto.imagen = ruta_relativa

        db.session.commit()
        return redirect(url_for('admin_panel'))

    return render_template('admin_panel_modificar_productos.html', producto=producto)

# ------------------- LOGIN / REGISTRO -------------------

@app.route('/registro', methods=['POST'])
def registro():
    user_first_name = request.form['user_first_name']
    user_last_name = request.form['user_last_name']
    email = request.form['email']
    number = request.form['number']
    password_plana = request.form['password']
    password_hasheada = generate_password_hash(password_plana)

    if User.query.filter_by(email=email).first() or User.query.filter_by(number=number).first():
        flash('Correo o número ya registrado', 'error')
        return redirect('/login_register')

    nuevo_usuario = User(
        user_first_name=user_first_name, 
        user_last_name=user_last_name, 
        email=email, 
        number=number,
        password=password_hasheada
    )

    db.session.add(nuevo_usuario)
    db.session.commit()
    
    # Correo al admin
    msg_admin = Message('Nuevo usuario registrado', recipients=['carloag210@hotmail.com'])
    msg_admin.body = f'Usuario: {user_first_name} {user_last_name}, Email: {email}'
    mail.send(msg_admin)

    # Correo al usuario
    msg_user = Message('Bienvenido a PorEncargo!', recipients=[nuevo_usuario.email])
    msg_user.body = f"Hola {user_first_name}, tu registro fue exitoso."
    mail.send(msg_user)

    flash('Usuario registrado con éxito', 'success')
    return redirect('/login_register')

@app.route('/login', methods=['POST'])
def login():
    email = request.form['email']
    password = request.form['password']
    user = User.query.filter_by(email=email).first()
    if user and check_password_hash(user.password, password):
        session.permanent = True
        login_user(user)
        if user.is_admin:
            return redirect('/admin')
        flash("Has ingresado con éxito", "success")
        return redirect('/pedidos_del_usuario')
    flash("Correo o contraseña incorrecta", "error")
    return redirect('/login_register')

@app.route('/logout')
def logout():
    logout_user()
    flash("Has cerrado sesión con éxito", "success")
    return redirect('/login_register')

# ------------------- PRODUCTOS -------------------

@app.route('/add_productos', methods=['GET', 'POST'])
@admin_required
def add_productos():
    if request.method == 'POST':
        nombre = request.form['nombre']
        precio = request.form['precio']
        peso = request.form['peso']
        categoria = request.form['categoria']
        imagen = request.files['imagen']

        ruta_imagen = None
        if imagen:
            nombre_archivo = secure_filename(imagen.filename)
            ruta_relativa = os.path.join('img_productos', nombre_archivo)
            ruta_completa = os.path.join(app.config['UPLOAD_FOLDER'], nombre_archivo)
            imagen.save(ruta_completa)
            ruta_imagen = ruta_relativa

        nuevo_producto = Producto(nombre=nombre, precio=precio, peso=peso, imagen=ruta_imagen, categoria=categoria)
        db.session.add(nuevo_producto)
        db.session.commit()
        return redirect(url_for('admin_panel_add_productos'))

    return render_template('admin_panel_add_productos.html')

# ------------------- RUN -------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
