# app.py (reemplazo completo, usa Brevo API en lugar de Flask-Mail / SMTP)
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

# Cargar .env si existe (útil para pruebas locales)
load_dotenv()

# ---------------- Configuración Brevo ----------------
BREVO_API_KEY = os.getenv("BREVO_API_KEY")
BREVO_SENDER_EMAIL = os.getenv("BREVO_SENDER_EMAIL", "logistica@porencargo.co")
BREVO_SENDER_NAME = os.getenv("BREVO_SENDER_NAME", "PorEncargo")
BREVO_URL = "https://api.brevo.com/v3/smtp/email"

def send_email(subject: str, recipient: str, body: str, sender_name: str = BREVO_SENDER_NAME, sender_email: str = BREVO_SENDER_EMAIL):
    """
    Envía un correo usando la API de Brevo vía http.client (sin requests).
    Devuelve (True, response_text) si tuvo éxito, (False, response_text) si falló.
    """
    if not BREVO_API_KEY:
        msg = "BREVO_API_KEY no configurada"
        print("Error enviando email:", msg)
        return False, msg

    conn = http.client.HTTPSConnection("api.brevo.com")
    payload = json.dumps({
        "sender": {"name": sender_name, "email": sender_email},
        "to": [{"email": recipient}],
        "subject": subject,
        "textContent": body
    })
    headers = {
        'accept': "application/json",
        'api-key': BREVO_API_KEY,
        'content-type': "application/json"
    }

    try:
        conn.request("POST", "/v3/smtp/email", body=payload, headers=headers)
        res = conn.getresponse()
        data = res.read().decode("utf-8")
        if res.status in (200, 201):
            return True, data
        else:
            print(f"Error enviando email: status {res.status} - {data}")
            return False, data
    except Exception as e:
        print("Error enviando email (excepción):", str(e))
        return False, str(e)
    finally:
        conn.close()

# ---------------- Config Flask ----------------
app = Flask(__name__, static_folder='assets', template_folder='templates')
app.config.from_object(Config)
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
# --- Fin config DB ---

app.config['UPLOAD_FOLDER'] = 'assets/img_productos'

db.init_app(app)
login_manager.init_app(app)

with app.app_context():
    db.create_all()

app.secret_key = os.urandom(24)
app.permanent_session_lifetime = timedelta(days=7)  # dura 7 días

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
    paquetes = Paquete.query.all()  # si ya tenés un modelo de paquetes
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
        # Actualizar datos del producto
        producto.nombre = request.form['nombre']
        producto.precio = request.form['precio']
        producto.peso = request.form['peso']
        producto.categoria = request.form['categoria']

        # Procesar imágenes
        imagenes = request.files.getlist("imagenes")

        for imagen in imagenes:
            if imagen and imagen.filename != "":
                filename = secure_filename(imagen.filename)
                path = os.path.join("static/uploads", filename)  # ruta donde se guarda
                imagen.save(path)

                # si tienes modelo ImagenProducto destrábalo; aquí se mantiene tu intención
                try:
                    nueva_img = ImagenProducto(ruta=f"uploads/{filename}", producto_id=producto.id)
                    db.session.add(nueva_img)
                except NameError:
                    # Si no definiste ImagenProducto en models, solo ignoramos añadir
                    pass

        db.session.commit()
        return redirect(url_for('admin_panel'))

    return render_template('admin_panel_modificar_productos.html', producto=producto)

@app.route('/calculadora')
def calculadora():
    return render_template("calculadora.html")

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
    direcciones_usuario = usuario.direcciones  # Gracias al relationship
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
        fecha_recibido = request.form.get('fecha_recibido')  # opcional

        # Convertimos el estado recibido como string a Enum
        estado = EstadoPaquete[estado_str]

        # Crear el paquete
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

    # GET: mostrar formulario
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
    fecha_recibido = request.form.get('fecha_recibido')  # opcional

    paquete = Paquete.query.get(paquete_id)

    if paquete is None:
        return "Paquete no encontrado", 404

    # Guardar estado anterior para el correo
    estado_anterior = paquete.estado.name if paquete.estado else "Sin estado"

    # Actualizar estado y demás campos
    paquete.estado = EstadoPaquete(nuevo_estado_str)
    paquete.nombre = p_nombre
    paquete.precio = p_precio
    paquete.numero_guia = p_numero_guia
    paquete.peso = p_peso

    if fecha_recibido:
        paquete.fecha_recibido = fecha_recibido

    try:
        db.session.commit()

        # 🚀 Enviar correo al usuario con plantilla HTML
        try:
            subject_user = f"Actualización de tu paquete: {paquete.nombre}"

            body_user_html = render_template(
                "email_paquete.html",
                user_nombre=paquete.usuario.user_first_name,
                paquete_nombre=paquete.nombre,
                paquete_guia=paquete.numero_guia or "N/A",
                estado_anterior=estado_anterior,
                estado_nuevo=paquete.estado.value,
                year=datetime.now().year
            )

            ok, resp = send_email(
                subject_user,
                paquete.usuario.email,
                body_user_html,
                html=True   # 👈 importante: marcar que es HTML
            )
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

    # Verificamos que el paquete sea del usuario logueado
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

    # flash("direccion registrada con exito","success")
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

    # Verificar que esa dirección le pertenece al usuario actual
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

    # --- Notificar admin (antes: Message + mail.send) ---
    subject_admin = 'Nuevo usuario registrado'
    body_admin = f'Se ha registrado un nuevo usuario:\n\nNombre del usuario: {user_first_name}\n Apellido del usuario:{user_last_name}\nCorreo: {email}'
    ok, resp = send_email(subject_admin, "carloag210@hotmail.com", body_admin)
    if not ok:
        # No mostramos detalles crudos al usuario, solo un mensaje amigable
        print("Error notificando admin:", resp)
        flash("Usuario creado, pero hubo un problema notificando al administrador", "warning")

    # --- Mensaje de bienvenida al usuario (idéntico al que tenías) ---
    subject_user = '¡Bienvenido a PorEncargo!, '
    mensaje_bienvenida = f"""Buenas Tardes

Te informamos que se realizó con éxito la apertura de tu casillero con código:
(COCAR8480)

Cuando realices una compra, por favor envíanos el número de tracking para rastrearlo.

Recuerda que todas las cajas deben venir marcadas con tu nombre y código de casillero así:
NAME:{user_first_name} {user_last_name} / COCAR8480

La dirección de envío de tus paquetes es:

ADDRESS: 7705 NW 46th ST
CITY: DORAL
STATE: FLORIDA
ZIP: 33195
PHONE: 3057176595
UNITED STATES

Tarifas:

SERVICIO DE CASILLERO
TARIFA PRODUCTOS HASTA 199 USD

Dirección Física en Doral - Florida - Estados Unidos
Tarifa: $14.000 COP todo incluido por libra para productos hasta 199 USD
Acumulamos tus paquetes totalmente gratis
Almacenamiento gratis máximo por 20 días

TARIFAS PRODUCTOS MAYOR A 199 USD

Tarifas:
Valor por libra: $2.8 USD + 10% de impuestos del valor declarado

Condiciones para computadores:
Computadores portátiles: $38 USD + 10% del valor en USD

CARGA COMERCIAL (más de 6 productos iguales y mayor a 200 USD)
SIN RESTRICCIONES COMERCIALES
Desde $3.5 USD por libra + 29% de impuestos

Te recomendamos agregar el código de tu casillero en el área de "número de suite o apto" al momento de ingresar la dirección.

¡Ya puedes utilizar tu casillero!

Quedamos atentos a cualquier inquietud.

Cordialmente,

Carlos Aguado
PorEncargo.co
P.O. BOX Manager
Cel: +57 3186505475
7705 NW 46 ST, Doral, Florida 33166

PorEncargo, LLC assumes no responsibility for any package or items shipped to us or delivered to us by USPS, since there is no record of real-time status of deliveries, or proof of signature by that company.

PorEncargo, LLC no asume responsabilidad por ningún paquete o artículo transportado o entregado a nosotros por USPS, dado que no hay constancia de status en tiempo real de las entregas, ni prueba de firma por parte de dicha compañía.
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

        usuarios_existentes = User.query.all()
        for u in usuarios_existentes:
            print(f"En base: '{u.email}'")
        
        print(f"Email recibido: '{email}'")

        user = User.query.filter_by(email=email).first()

        print(f"usuario encontrado: '{user}'")

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
    paquete = None  # Por defecto no hay nada
    if request.method == "POST":
        email = request.form.get("email")
        numero_guia = request.form.get("numero_guia")

        usuario_email = User.query.filter_by(email=email).first()
        if not usuario_email:
            flash('usuario no existe','error')
            return render_template("rastrea_tu_orden.html", paquete=None)   
        # Si el usuario existe, buscamos el paquete
        paquete = Paquete.query.filter_by(numero_guia=numero_guia, id_user=usuario_email.id).first()
        if not paquete:
            flash('Paquete no encontrado para este usuario','error')
            return render_template("rastrea_tu_orden.html")   

        # En todos los casos se renderiza la misma plantilla, con o sin resultado
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

@app.route('/add_productos', methods=['GET', 'POST'])
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
        estado = request.form['estado']  # debería venir como estado.name
        
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
            prealerta=True  # Aquí está la magia
        )

        db.session.add(nuevo_paquete)
        db.session.commit()            
        # --- Notificar al admin con Brevo ---
        subject_paquete = 'Nueva prealerta registrada'
        body_paquete = f'Se ha registrado un nuevo usuario:\n\nNombre del usuario: {user.user_first_name}\n Apellido del usuario:{user.user_last_name}\nCorreo: {user.email}'
        ok3, resp3 = send_email(subject_paquete, "carloag210@hotmail.com", body_paquete)
        if not ok3:
            print("Error notificando admin de prealerta:", resp3)
            flash("Prealerta creada, pero hubo un problema notificando al administrador", "warning")

        return redirect(url_for('pedidos_del_usuario'))

    # si es GET, renderiza el formulario
    estados_posibles = list(EstadoPaquete)  # para el <select>
    return render_template('formulario_paquete_usuario.html', estados_posibles=estados_posibles, usuario=current_user)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)


































