from extencions import db
from sqlalchemy import Column, Integer, String, Boolean, Float, ForeignKey, Enum
# la clomuna de arriba solo hace que s epueda tranajar con clomun, etc sin mensionar db. al principio
from sqlalchemy.orm import relationship
from flask_login import UserMixin
import enum

class EstadoPaquete(enum.Enum):
    COMPRADO = "Comprado en Tienda"
    DESPACHADO_TIENDA = "Despachado por Tienda"
    EN_ENVIO = "Despachado Bodega Miami"
    EN_BODEGA_MIAMI = "Llegó a Bodega Miami"
    EN_AEROPUERTO = "Llegó Aeropuerto Bogotá"
    EN_COLOMBIA = "En Bodega Medellín"
    LLEGO = "Despachado a tú Dirección"

class Paquete(db.Model):
    __tablename__ = 'paquetes'

    id = Column(Integer, primary_key=True, autoincrement=True)
    id_user = Column(Integer, ForeignKey('users.id'), nullable=False)
    nombre = Column(String(100), nullable=False)
    precio = Column(String(50), nullable=False)
    numero_guia = Column(String(100), unique=True, nullable=False)
    peso = Column(String(50), unique=False, nullable=False)
    estado = Column(Enum(EstadoPaquete), default=EstadoPaquete.EN_ENVIO, nullable=False)
    prealerta = Column(Boolean, default=False, nullable=False)


    usuario = relationship('User', back_populates='paquetes')

    def __repr__(self):
        return f"<Paquete(nombre='{self.nombre}', estado='{self.estado.name}', usuario_id={self.id_user})>"

class User(db.Model, UserMixin):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    is_admin = Column(Boolean, default=False)
    user_first_name = Column(String(100), nullable=False)
    user_last_name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    number = Column(Float, nullable=False, unique=True)
    password = Column(String(255), nullable=False)

    paquetes = relationship('Paquete', cascade="all, delete-orphan", back_populates='usuario', lazy=True)
    direcciones = relationship('Direccion', cascade="all, delete-orphan", back_populates='usuario', lazy=True)


    def __repr__(self):
        return f"<Usuario(user_name='{self.user_first_name}', email='{self.email}')>"
    
class Direccion(db.Model):
    __tablename__ = 'direcciones'

    id = Column(Integer, primary_key=True, autoincrement=True)  # ID único de la dirección
    id_user = Column(Integer, ForeignKey('users.id'), nullable=False)  # Relación con usuario

    pais = Column(String(100), nullable=False)
    ciudad = Column(String(100), nullable=False)
    direccion = Column(String(200), nullable=False)
    codigo_postal = Column(String(20), nullable=True)
    name = Column(String(100), nullable=False, default='')
    # Relación reversa para acceder desde el usuario
    usuario = relationship('User', back_populates='direcciones')


class Producto(db.Model):
    __tablename__ = 'productos'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.Text, nullable=False)
    precio = db.Column(db.String(50), nullable=False)
    imagen = db.Column(db.Text)  # ruta de imagen
    categoria = db.Column(db.Text, nullable=False)
    
    def __repr__(self):
        return f'<Producto {self.nombre}>'