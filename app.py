from flask import flash, Flask, request, render_template, redirect, url_for, session
from extencions import db, init_extencions, login_manager
from models import User, Paquete, EstadoPaquete, Direccion, Producto
from config import Config
from flask_login import login_user, logout_user, login_required, current_user, LoginManager
from flask_sqlalchemy import SQLAlchemy 
from werkzeug.security import check_password_hash, generate_password_hash
from flask_mail import Mail, Message
from auth.decorators import admin_required
from werkzeug.utils import secure_filename
from datetime import timedelta
import ssl
import smtplib          
import os

# agrego templates y seets a mano porque no funciona si no determino el assets
app = Flask(__name__, static_folder='assets', template_folder='templates')
app.config.from_object(Config)
app.config.from_object(Config)

# --- Config DB Railway ---
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_LINK")

# Fix si Railway devuelve postgres:// en vez de postgresql://
if app.config['SQLALCHEMY_DATABASE_URI'] and app.config['SQLALCHEMY_DATABASE_URI'].startswith("postgres://"):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace("postgres://", "postgresql://", 1)

# Forzar SSL
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
#email automatico
app.config['MAIL_SERVER'] = 'smtp.purelymail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USERNAME'] = 'logistica@porencargo.co'         # tu correo
app.config['MAIL_PASSWORD'] = 'Carlos161809Aguado*2025*'           # contraseña de aplicación
app.config['MAIL_DEFAULT_SENDER'] = 'logistica@porencargo.co'   # quien envía
    
mail = Mail(app)

# rutas simples

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
        return render_template("admin_panel_ver_usuarios.html")

@app.route('/admin_panel_modificar_productos/<int:id>', methods=['GET', 'POST'])
@admin_required
def admin_panel_modificar_productos(id):
    producto = Producto.query.get_or_404(id)

    if request.method == 'POST':
        producto.nombre = request.form['nombre']
        producto.precio = request.form['precio']
        producto.peso = request.form['peso']
        producto.categoria = request.form['categoria']

        imagenes = request.files.getlist("imagenes")

nuevo_producto = Producto(
    nombre=request.form["nombre"],
    precio=request.form["precio"],
    peso=request.form["peso"],
    categoria=request.form["categoria"]
)

db.session.add(nuevo_producto)
db.session.commit()  # Guardamos primero el producto para tener su ID

for imagen in imagenes:
    if imagen.filename != "":
        filename = secure_filename(imagen.filename)
        path = os.path.join("static/uploads", filename)
        imagen.save(path)

        nueva_img = ImagenProducto(ruta=f"uploads/{filename}", producto_id=nuevo_producto.id)
        db.session.add(nueva_img)

db.session.commit()

        return redirect(url_for('admin_panel'))

    return render_template('admin_panel_modificar_productos.html', producto=producto)

@app.route('/calculadora')
def calculadora():
    return render_template("calculadora.html")
#------------
# @app.route('/admin_modificar_paquete/<int:id>', methods=['get', 'post'])
# def admin_modificar_paquete(id):
#     paquete = Paquete.query.get_or_404(id)

#     if request.method == 'POST':
#         print(request.form) 
#         paquete.nombre = request.form['nombre']
#         paquete.precio = request.form['precio']
#         paquete.numero_guia = request.form['numero_guia']
#         paquete.peso = request.form['peso']

#         db.session.commit()
        
#         return redirect(url_for('admin_panel_ver_usuarios'))
        
#     return render_template('admin_modificar_paquete.html', paquete=paquete)
#-------------------

@app.route('/admin/editar_usuario/<int:id>', methods=['GET', 'POST'])
@admin_required  # si ya tienes este decorador  
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
    # paquetes_usuario = usuario.paquetes  # Gracias al relationship
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

            # Convertimos el estado recibido como string a Enum
            estado = EstadoPaquete[estado_str]
            
            # Crear el paquete
            nuevo_paquete    = Paquete(
                nombre=nombre,
                precio=precio,
                numero_guia=numero_guia,
                peso=peso,
                estado=estado,
                id_user=id_user
            )
            print(request.form)
            db.session.add(nuevo_paquete)
            db.session.commit()
            flash("Paquete creado correctamente", "success")
            return redirect(request.referrer)
    return redirect('login_register')
    # Si es GET, muestra el formulario con usuarios y estados posibles
    usuarios = User.query.get_or_404(user_id)
    paquetes = Paquete.query.get_or_404(user_id)
    estados_posibles = list(EstadoPaquete)
    return render_template('admin_pedidos_usuario.html', paquetes=paquetes , usuario=usuarios, estados_posibles=estados_posibles)

@app.route('/admin/actualizar_estado', methods=['POST'])
def actualizar_estado():
    paquete_id = request.form.get('paquete_id')
    nuevo_estado_str = request.form.get('nuevo_estado')
    p_nombre = request.form.get('nombre')#cambios que puse para que chat gpt los vea
    p_precio = request.form.get('precio')#cambios que puse para que chat gpt los vea
    p_numero_guia = request.form.get('numero_guia')#cambios que puse para que chat gpt los vea
    p_peso = request.form.get('peso')#cambios que puse para que chat gpt los vea

    paquete = Paquete.query.get(paquete_id)

    if paquete is None:
        return "Paquete no encontrado", 404

    # Actualizar estado
    paquete.estado = EstadoPaquete(nuevo_estado_str)

    paquete.nombre = p_nombre#cambios que puse para que chat gpt los vea
    paquete.precio = p_precio#cambios que puse para que chat gpt los vea
    paquete.numero_guia = p_numero_guia#cambios que puse para que chat gpt los vea
    paquete.peso = p_peso#cambios que puse para que chat gpt los vea

    # Actualizar prealerta si el admin marcó "resuelta"
    if 'prealerta_resuelta' in request.form:
        paquete.prealerta = False  # ✅ ESTO es lo que faltaba

    db.session.commit()  # guarda los cambios

    return redirect(request.referrer)

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
    # id = request.form.get('id')  # <- obtenemos el ID del producto seleccionado
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
    # flash("Dirección eliminada con éxito", "success")
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

    msg_al_admin = Message('Nuevo usuario registrado',
                  recipients=['carloag210@hotmail.com'])  #<<<<<<<<<<----------------
    msg_al_admin.body = f'Se ha registrado un nuevo usuario:\n\nNombre del usuario: {user_first_name}\n Apellido del usuario:{user_last_name}\nCorreo: {email}'
    mail.send(msg_al_admin)
    msg_al_usuario = Message('¡Bienvenido a PorEncargo!, ', 
                  recipients=[nuevo_usuario.email])  #<<<<<<<<<<----------------
    msg_al_usuario.body = f"Buenas Tardes\n\nTe informamos que se realizó con éxito la apertura de tu casillero con código:\n(COCAR8480)\n\nCuando realices una compra, por favor envíanos el número de tracking para rastrearlo.\n\nRecuerda que todas las cajas deben venir marcadas con tu nombre y código de casillero así:\nNAME:{user_first_name} {user_last_name} / COCAR8480\n\nLa dirección de envío de tus paquetes es:\n\nADDRESS: 7705 NW 46th ST\nCITY: DORAL\nSTATE: FLORIDA\nZIP: 33195\nPHONE: 3057176595\nUNITED STATES\n\nTarifas:\n\nSERVICIO DE CASILLERO\nTARIFA PRODUCTOS HASTA 199 USD\n\nDirección Física en Doral - Florida - Estados Unidos\nTarifa: $14.000 COP todo incluido por libra para productos hasta 199 USD\nAcumulamos tus paquetes totalmente gratis\nAlmacenamiento gratis máximo por 20 días\n\nTARIFAS PRODUCTOS MAYOR A 199 USD\n\nTarifas:\nValor por libra: $2.8 USD + 10% de impuestos del valor declarado\n\nCondiciones para computadores:\nComputadores portátiles: $38 USD + 10% del valor en USD\n\nCARGA COMERCIAL (más de 6 productos iguales y mayor a 200 USD)\nSIN RESTRICCIONES COMERCIALES\nDesde $3.5 USD por libra + 29% de impuestos\n\nTe recomendamos agregar el código de tu casillero en el área de \"número de suite o apto\" al momento de ingresar la dirección.\n\n¡Ya puedes utilizar tu casillero!\n\nQuedamos atentos a cualquier inquietud.\n\nCordialmente,\n\nCarlos Aguado\nPorEncargo.co\nP.O. BOX Manager\nCel: +57 3186505475\n7705 NW 46 ST, Doral, Florida 33166\n\nPorEncargo, LLC assumes no responsibility for any package or items shipped to us or delivered to us by USPS, since there is no record of real-time status of deliveries, or proof of signature by that company.\n\nPorEncargo, LLC no asume responsabilidad por ningún paquete o artículo transportado o entregado a nosotros por USPS, dado que no hay constancia de status en tiempo real de las entregas, ni prueba de firma por parte de dicha compañía."
    mail.send(msg_al_usuario)

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
            flash("has ingresado con exito","success")
            return redirect('/pedidos_del_usuario')
        flash("contraseña incorrecta","error")
    return redirect('/login_register')

@app.route('/logout')
def logout():
    logout_user()
    flash("Has cerrado sesion con exito","success")
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
        return redirect(url_for('pedidos_del_usuario'))  # o a donde quieras llevarlo

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
    # Ejemplo: obtener todos los paquetes y usuarios
    usuarios = User.query.all()
    paquetes = Paquete.query.all()  # si ya tenés un modelo de paquetes
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
            print(nombre_archivo)
            ruta_relativa = os.path.join('img_productos', nombre_archivo)
            print(ruta_relativa)
            ruta_completa = os.path.join(app.config['UPLOAD_FOLDER'], nombre_archivo)
            print(ruta_completa)
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
        msg_al_admin = Message('Nueva prealerta registrada',
                    recipients=['carloag210@hotmail.com'])   
        msg_al_admin.body = f'Se ha registrado un nuevo usuario:\n\nNombre del usuario: {user.user_first_name}\n Apellido del usuario:{user.user_last_name}\nCorreo: {user.email}'
        mail.send(msg_al_admin)

        return redirect(url_for('pedidos_del_usuario'))  # ajusta según tu vista de usuario

    # si es GET, renderiza el formulario
    estados_posibles = list(EstadoPaquete)  # para el <select>
    return render_template('formulario_paquete_usuario.html', estados_posibles=estados_posibles, usuario=current_user)

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)



