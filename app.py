import cloudinary
import cloudinary.uploader
from flask import flash, Flask, request, render_template, redirect, url_for, session, jsonify
from extencions import db, init_extencions, login_manager
from models import User, Paquete, EstadoPaquete, Direccion, Producto
from config import Config
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from auth.decorators import admin_required
from werkzeug.utils import secure_filename
from datetime import timedelta
import json
import http.client
import os
from dotenv import load_dotenv

load_dotenv()

cloudinary.config(
    cloud_name = os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key    = os.environ.get("CLOUDINARY_API_KEY"),
    api_secret = os.environ.get("CLOUDINARY_API_SECRET"),
    secure     = True
)

# ---------------- Configuración Brevo ----------------

BREVO_API_KEY = os.getenv("BREVO_API_KEY")
BREVO_SENDER_EMAIL = os.getenv("BREVO_SENDER_EMAIL", "logistica@porencargo.co")
BREVO_SENDER_NAME = os.getenv("BREVO_SENDER_NAME", "PorEncargo")
BREVO_URL = "https://api.brevo.com/v3/smtp/email"


def send_email(subject: str, recipient: str, body: str, sender_name: str = BREVO_SENDER_NAME, sender_email: str = BREVO_SENDER_EMAIL, html: bool = False):
    """
    Envía un correo usando la API de Brevo vía http.client.
    """
    if not BREVO_API_KEY:
        msg = "BREVO_API_KEY no configurada"
        print("Error enviando email:", msg)
        return False, msg

    conn = http.client.HTTPSConnection("api.brevo.com")

    payload_dict = {
        "sender": {"name": sender_name, "email": sender_email},
        "to": [{"email": recipient}, {"email": "logistica@porencargo.co"}],
        "subject": subject
    }

    if html:
        payload_dict["htmlContent"] = body
    else:
        payload_dict["textContent"] = body

    payload = json.dumps(payload_dict, ensure_ascii=False).encode('utf-8')

    headers = {
        "accept": "application/json",
        "api-key": BREVO_API_KEY,
        "content-type": "application/json; charset=utf-8",
    }

    try:
        conn.request("POST", "/v3/smtp/email", body=payload, headers=headers)
        res = conn.getresponse()
        data = res.read().decode("utf-8")
        if res.status in (200, 201):
            return True, data
        else:
            print(f"❌ Error enviando email: status {res.status} - {data}")
            return False, data
    except Exception as e:
        print("⚠️ Excepción enviando email:", str(e))
        return False, str(e)
    finally:
        conn.close()


# ---------------- Config Flask ----------------
app = Flask(__name__, static_folder='assets', template_folder='templates')
app.config.from_object(Config)

# --- Config DB Railway ---
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_LINK")

# Fix si Railway devuelve postgres:// en vez de postgresql://
if app.config['SQLALCHEMY_DATABASE_URI'] and app.config['SQLALCHEMY_DATABASE_URI'].startswith("postgres://"):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace("postgres://", "postgresql://", 1)

# Forzar SSL en la conexión
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "connect_args": {"sslmode": "require"}
}

app.config['UPLOAD_FOLDER'] = 'assets/img_productos'

db.init_app(app)
login_manager.init_app(app)

with app.app_context():
    db.create_all()

app.secret_key = os.urandom(24)
app.permanent_session_lifetime = timedelta(days=7) 

# ----------------- Rutas -----------------

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

@app.route('/admin_panel_add_productos')
@admin_required
def admin_panel_add_productos():
    return render_template("admin_panel_add_productos.html")

@app.route('/admin_panel_ver_usuarios')
@admin_required
def admin_panel_ver_usuarios():
    usuarios = User.query.all()
    paquetes = Paquete.query.all()
    productos= Producto.query.all()
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

        # Procesar imágenes nuevas
        imagenes = request.files.getlist("imagenes")

        for imagen in imagenes:
            if imagen and imagen.filename != "":
                try:
                    # Configuración preventiva por si acaso
                    if not cloudinary.config().api_key:
                        cloudinary.config(
                            cloud_name = os.environ.get("CLOUDINARY_CLOUD_NAME"), 
                            api_key = os.environ.get("CLOUDINARY_API_KEY"), 
                            api_secret = os.environ.get("CLOUDINARY_API_SECRET"),
                            secure = True
                        )
                    
                    # SUBIDA A CLOUDINARY
                    upload_result = cloudinary.uploader.upload(imagen, folder="productos")
                    producto.imagen = upload_result['secure_url'] 
                except Exception as e:
                    print(f"Error subiendo a Cloudinary: {e}")

        db.session.commit()
        return redirect(url_for('admin_panel'))

    return render_template('admin_panel_modificar_productos.html', producto=producto)

@app.route('/calculadora')  
def calculadora():
    return render_template("calculadora.html")

@app.route('/add_productos', methods=['GET', 'POST'])
def add_productos():
    if request.method == 'POST':
        nombre = request.form['nombre']
        precio = request.form['precio']
        peso = request.form['peso']
        categoria = request.form['categoria']
        imagen = request.files.get('imagen')

        ruta_imagen = None
        if imagen and imagen.filename != '':
            try:
                upload_result = cloudinary.uploader.upload(imagen, folder="productos")
                ruta_imagen = upload_result['secure_url']
            except Exception as e:
                print(f"Error subiendo a Cloudinary: {e}")
                return f"Error de Cloudinary: {e}", 500

        # 👈 nuevo_producto FUERA del if/try, al mismo nivel que ruta_imagen
        nuevo_producto = Producto(
            nombre=nombre,
            precio=precio,
            peso=peso,
            imagen=ruta_imagen,
            categoria=categoria
        )

        db.session.add(nuevo_producto)
        db.session.commit()
        return redirect(url_for('admin_panel_add_productos'))
    return render_template('admin_panel_add_productos.html')
    
@app.route('/admin/editar_usuario/<int:id>', methods=['GET', 'POST'])
@admin_required
def admin_editar_usuario(id):
    usuario = User.query.get_or_404(id)

    if request.method == 'POST':
        usuario.user_first_name = request.form['nombre']
        usuario.user_last_name = request.form['apellido']
        usuario.email = request.form['email']
        usuario.number = request.form['numero']

        db.session.commit()
        return redirect(url_for('admin_panel_ver_usuarios'))

    return render_template('admin_editar_usuario.html', usuario=usuario)

@app.route('/admin/eliminar_usuario/<int:id>', methods=['GET','POST'])
@admin_required
def admin_eliminar_usuario(id):
    usuario = User.query.get_or_404(id)
    if request.method == 'GET':
        db.session.delete(usuario)
        db.session.commit()
        return redirect(url_for('admin_panel_ver_usuarios'))

@app.route('/admin/pedidos_usuario/<int:user_id>')
@admin_required
def admin_ver_pedidos_usuario(user_id):
    usuario = User.query.get_or_404(user_id)
    paquetes_usuario = Paquete.query.filter_by(id_user=usuario.id).order_by(Paquete.prealerta.desc()).all()
    estados_posibles = list(EstadoPaquete)
    return render_template('admin_pedidos_usuario.html', usuario=usuario, paquetes=paquetes_usuario, estados_posibles=estados_posibles)
    
@app.route('/admin/direcciones_usuario/<int:user_id>')
@admin_required
def admin_ver_direcciones_usuario(user_id):
    usuario = User.query.get_or_404(user_id)
    direcciones_usuario = usuario.direcciones
    return render_template('admin_direcciones_usuario.html', usuario=usuario, direcciones=direcciones_usuario)

@app.route('/admin/crear_paquete/<int:user_id>', methods=['GET', 'POST'])
@admin_required
def crear_paquete(user_id):
    if request.method == 'POST':
        nombre = request.form['nombre']
        precio = request.form['precio']
        numero_guia = request.form['numero_guia']
        peso = request.form['peso']
        estado_str = request.form['estado']
        id_user = request.form['id_user']
        fecha_recibido = request.form.get('fecha_recibido') 

        estado = EstadoPaquete[estado_str]

        nuevo_paquete = Paquete(
            nombre=nombre,
            precio=precio,
            numero_guia=numero_guia,
            peso=peso,
            estado=estado,
            id_user=id_user,
            fecha_recibido=fecha_recibido
        )

        db.session.add(nuevo_paquete)
        db.session.commit()
        flash("Paquete creado correctamente", "success")
        return redirect(request.referrer)

    usuario = User.query.get_or_404(user_id)
    estados_posibles = list(EstadoPaquete)
    return render_template('admin_pedidos_usuario.html', usuario=usuario, estados_posibles=estados_posibles)

@app.route('/admin/actualizar_estado', methods=['POST'])
def actualizar_estado():
    paquete_id = request.form.get('paquete_id')
    nuevo_estado_str = request.form.get('nuevo_estado')
    p_nombre = request.form.get('nombre')
    p_precio = request.form.get('precio')
    p_numero_guia = request.form.get('numero_guia')
    p_peso = request.form.get('peso')
    fecha_recibido = request.form.get('fecha_recibido')

    paquete = Paquete.query.get(paquete_id)

    if paquete is None:
        return "Paquete no encontrado", 404

    estado_anterior = paquete.estado.name if paquete.estado else "Sin estado"

    paquete.estado = EstadoPaquete(nuevo_estado_str)
    paquete.nombre = p_nombre
    paquete.precio = p_precio
    paquete.numero_guia = p_numero_guia
    paquete.peso = p_peso

    if fecha_recibido:
        paquete.fecha_recibido = fecha_recibido

    try:
        db.session.commit()
        # Enviar correo al usuario
        try:
            subject_user = f"Actualización de tu paquete: {paquete.nombre}"
            body_user = f"""
Hola {paquete.usuario.user_first_name},

Tu paquete "{paquete.nombre}" (Guía: {paquete.numero_guia or 'N/A'}) ha cambiado de estado:

📦 Estado anterior: {estado_anterior}
➡️ Nuevo estado: {paquete.estado.value}

Puedes ingresar a tu cuenta en PorEncargo.co para ver más detalles.

Saludos,  
Equipo PorEncargo
"""
            ok, resp = send_email(subject_user, paquete.usuario.email, body_user)
            if not ok:
                print("❌ Error enviando notificación al usuario:", resp)
        except Exception as e:
            print("⚠️ Excepción enviando correo:", str(e))

        return redirect(request.referrer)

    except Exception as e:
        db.session.rollback()
        return f"Error al actualizar el paquete: {str(e)}", 500

@app.route('/marcar_consolidar', methods=['POST'])
@login_required
def marcar_consolidar():
    paquete_id = request.form.get("paquete_id")
    paquete = Paquete.query.get_or_404(paquete_id)
    if paquete.id_user != current_user.id:
        return {"success": False, "error": "No tienes permisos"}, 403
    paquete.consolidar = bool(request.form.get("consolidar"))
    db.session.commit()
    return {"success": True, "consolidar": paquete.consolidar}

@app.route('/nueva_direccion', methods=['POST'])
@login_required
def nueva_direccion():
    id_user=current_user.id
    pais = request.form['pais']
    ciudad = request.form['ciudad']
    direccion = request.form['direccion']
    codigo_postal = request.form['codigo_postal']
    name = request.form['name']

    new_direccion = Direccion(
        id_user=id_user,
        pais=pais,
        ciudad=ciudad,
        direccion=direccion,
        codigo_postal=codigo_postal,
        name=name)
    
    db.session.add(new_direccion)
    db.session.commit()
    return redirect('/direcciones')

@app.route('/eliminar_producto/<int:id>', methods=['POST'])
@admin_required
def eliminar_producto(id):
    producto = Producto.query.get_or_404(id)
    db.session.delete(producto)
    db.session.commit()
    return redirect(url_for('admin_panel'))

@app.route('/eliminar_paquete/<int:id>', methods=['POST'])
@admin_required
def eliminar_paquete(id):
    paquete = Paquete.query.get_or_404(id)
    db.session.delete(paquete)
    db.session.commit()
    flash('Paquete eliminado correctamente.', 'success')
    return redirect(request.referrer or url_for('admin_panel'))

@app.route('/eliminar_direccion/<int:id>', methods=['POST'])
@login_required
def eliminar_direccion(id):
    direccion = Direccion.query.get_or_404(id)
    if direccion.id_user != current_user.id:
        flash("No tienes permiso para eliminar esta dirección", "error")
        return redirect(url_for('direcciones'))
    db.session.delete(direccion)
    db.session.commit()
    return redirect(url_for('direcciones'))

@app.route('/registro', methods=['POST'])
def registro():
    user_first_name = request.form['user_first_name']
    user_last_name = request.form['user_last_name']
    email = request.form['email']
    number = request.form['number']
    password_plana = request.form['password']
    password_hasheada = generate_password_hash(password_plana)

    usuario_existente_email = User.query.filter_by(email=email).first()
    if usuario_existente_email :
        flash('este correo ya ha sido registrado','error')
        return redirect ('/login_register')
    
    usuario_existente_number = User.query.filter_by(number=number).first()
    if usuario_existente_number:
        flash('este numero ya ha sido registrado','error')
        return redirect ('/login_register')
    
    nuevo_usuario = User(
        user_first_name=user_first_name, 
        user_last_name=user_last_name, 
        email=email, 
        number=number,
        password=password_hasheada)
    
    db.session.add(nuevo_usuario)
    db.session.commit()

    subject_admin = 'Nuevo usuario registrado'
    body_admin = f'Se ha registrado un nuevo usuario:\n\nNombre del usuario: {user_first_name}\n Apellido del usuario:{user_last_name}\nCorreo: {email}'
    ok, resp = send_email(subject_admin, "carloag210@hotmail.com", body_admin)
    if not ok:
        print("Error notificando admin:", resp)
        flash("Usuario creado, pero hubo un problema notificando al administrador", "warning")

    # --- Mensaje de bienvenida (USO DE COMILLAS TRIPLES PARA TEXTO LARGO) ---
    subject_user = '¡Bienvenido a PorEncargo!, '
    mensaje_bienvenida = f"""Buenas Tardes

Te informamos que se realizó con éxito la apertura de tu casillero con código:
(COCAR8480)

Cuando realices una compra, por favor envíanos el número de tracking para rastrearlo.

Recuerda que todas las cajas deben venir marcadas con tu nombre y código de casillero así:
NAME:{user_first_name} {user_last_name} / C1093

La dirección de envío de tus paquetes es:

ADDRESS: 1716 Northwest 28th Terrace
CITY: CAPE CORAL
STATE: FLORIDA
ZIP: 33993
PHONE: (786) 432 1524
UNITED STATES

Tarifas:
SERVICIO DE CASILLERO
... (resto del mensaje) ...
"""
    ok2, resp2 = send_email(subject_user, nuevo_usuario.email, mensaje_bienvenida)
    if not ok2:
        print("Error enviando bienvenida al usuario:", resp2)
        flash("Usuario creado, pero hubo un problema enviando el correo de bienvenida", "warning")

    flash('Usuario registrado con éxito', 'success')
    return redirect('/login_register')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method=='POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            session.permanent = True
            login_user(user)
            if user.is_admin:
                return redirect('/admin')
            flash("Bienvenido a su Cuenta","success")
            return redirect('/pedidos_del_usuario')
        flash("contraseña incorrecta","error")
    return redirect('/login_register')

@app.route('/logout')
def logout():
    logout_user()
    flash("Hasta Pronto","success")
    return redirect('/login_register')

@app.route('/pedidos_del_usuario')
@login_required
def pedidos_del_usuario():
    paquetes_usuario = current_user.paquetes
    return render_template('pedidos_usuario.html', paquetes=paquetes_usuario)

@app.route('/direcciones')
@login_required
def direcciones():
    direcciones_lugares = current_user.direcciones
    return render_template('mis_direcciones.html', direccioness=direcciones_lugares)

@app.route('/info')
@login_required
def info():
    return render_template("informa.html", user=current_user)

@app.route('/editar_usuario', methods=['GET', 'POST'])
@login_required
def editar_usuario():
    if request.method == 'POST':
        current_user.user_first_name = request.form['user_first_name']
        current_user.user_last_name = request.form['user_last_name']
        current_user.email = request.form['email']
        current_user.number = request.form['number']
        db.session.commit()
        flash('Información actualizada correctamente', 'success')
        return redirect(url_for('pedidos_del_usuario'))

    return render_template('editar_usuario.html', user=current_user)

@app.route("/rastrear", methods=["GET", "POST"])
def rastrear_pedido():
    paquete = None 
    if request.method == "POST":
        email = request.form.get("email")
        numero_guia = request.form.get("numero_guia")

        usuario_email = User.query.filter_by(email=email).first()
        if not usuario_email:
            flash('usuario no existe','error')
            return render_template("rastrea_tu_orden.html", paquete=None)   
        paquete = Paquete.query.filter_by(numero_guia=numero_guia, id_user=usuario_email.id).first()
        if not paquete:
            flash('Paquete no encontrado para este usuario','error')
            return render_template("rastrea_tu_orden.html")   

        return render_template("rastrea_tu_orden.html", paquete=paquete)

    return render_template("rastrea_tu_orden.html", paquete=None)

@app.route('/admin')
@login_required
@admin_required
def admin_panel():
    usuarios = User.query.all()
    paquetes = Paquete.query.all()
    productos= Producto.query.all()
    estados_posibles = list(EstadoPaquete)
    return render_template(
        'admin_panel.html', 
        usuarios=usuarios, 
        paquetes=paquetes,
        estados_posibles=estados_posibles,
        productos=productos
    )

@app.route('/add_prealerta')
@login_required
def add_prealerta():
    estados_posibles = list(EstadoPaquete)
    return render_template("use_prealertar.html", estados_posibles=estados_posibles)

@app.route('/usuario/crear_paquete', methods=['GET', 'POST'])
@login_required
def crear_paquete_usuario():
    user = current_user
    if request.method == 'POST':
        nombre = request.form['nombre']
        numero_guia = request.form['numero_guia']
        precio = request.form['precio']
        peso = request.form['peso']
        estado = request.form['estado']
        
        numero_guia_existente = Paquete.query.filter_by(numero_guia=numero_guia).first()
        if numero_guia_existente:
            flash('Este numero de guia ya ha sido utilizado','error')
            return redirect('/add_prealerta')

        nuevo_paquete = Paquete(
            nombre=nombre,
            numero_guia=numero_guia,
            precio=precio,
            peso=peso,
            id_user=current_user.id,
            estado=estado,
            prealerta=True
        )

        db.session.add(nuevo_paquete)
        db.session.commit()            
        subject_paquete = 'Nueva prealerta registrada'
        body_paquete = f'Se ha registrado un nuevo usuario:\n\nNombre del usuario: {user.user_first_name}\n Apellido del usuario:{user.user_last_name}\nCorreo: {user.email}'
        ok3, resp3 = send_email(subject_paquete, "carloag210@hotmail.com", body_paquete)
        if not ok3:
            print("Error notificando admin de prealerta:", resp3)
            flash("Prealerta creada, pero hubo un problema notificando al administrador", "warning")

        return redirect(url_for('pedidos_del_usuario'))

    estados_posibles = list(EstadoPaquete)
    return render_template('formulario_paquete_usuario.html', estados_posibles=estados_posibles, usuario=current_user)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)






