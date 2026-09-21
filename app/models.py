from datetime import datetime

from sqlalchemy import text
from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

# Tabla intermedia N:N entre Álbum y Formato
album_formato = db.Table(
    'album_formato',
    db.Column('album_id', db.Integer, db.ForeignKey('album.id', ondelete='CASCADE'), primary_key=True),
    db.Column('formato_id', db.Integer, db.ForeignKey('formato.id', ondelete='CASCADE'), primary_key=True)
)

# Tabla intermedia N:N entre Banda y Género
banda_genero = db.Table(
    'banda_genero',
    db.Column('banda_id', db.Integer, db.ForeignKey('banda.id', ondelete='CASCADE'), primary_key=True),
    db.Column('genero_id', db.Integer, db.ForeignKey('genero.id', ondelete='CASCADE'), primary_key=True)
)


class Pais(db.Model):
    __tablename__ = 'pais'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False, unique=True, index=True)
    continente = db.Column(db.String(50), nullable=False)
    codigo_iso = db.Column(db.String(2), unique=True, nullable=True)

    bandas = db.relationship('Banda', backref='pais', lazy=True)

    def __repr__(self):
        return f'<Pais {self.nombre}>'


class Genero(db.Model):
    __tablename__ = 'genero'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False, unique=True, index=True)
    descripcion = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f'<Genero {self.nombre}>'


class Formato(db.Model):
    __tablename__ = 'formato'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(80), nullable=False, index=True)

    # Auto-referencia para crear jerarquía (Padre -> Subformatos)
    padre_id = db.Column(db.Integer, db.ForeignKey('formato.id', ondelete='CASCADE'), nullable=True)

    # Relación que permite acceder a .subformatos y a .padre
    subformatos = db.relationship(
        'Formato',
        backref=db.backref('padre', remote_side=[id]),
        lazy='select',
        cascade='all, delete-orphan'
    )

    def __repr__(self):
        if self.padre:
            return f'<Subformato {self.padre.nombre} -> {self.nombre}>'
        return f'<FormatoPrincipal {self.nombre}>'


class SelloDiscografico(db.Model):
    __tablename__ = 'sello_discografico'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False, unique=True, index=True)

    # Clave foránea hacia la tabla 'pais'
    pais_id = db.Column(db.Integer, db.ForeignKey('pais.id'), nullable=True)

    # Relación para acceder al objeto país directamente
    pais = db.relationship('Pais', backref=db.backref('sellos', lazy=True))

    def __repr__(self):
        return f'<SelloDiscografico {self.nombre}>'


class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuario'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    nickname = db.Column(db.String(100), nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=True, index=True)
    instagram = db.Column(db.String(120), unique=True, nullable=True, index=True)
    facebook = db.Column(db.String(120), unique=True, nullable=True, index=True)
    youtube = db.Column(db.String(120), unique=True, nullable=True, index=True)
    discogs = db.Column(db.String(120), unique=True, nullable=True, index=True)
    nombre = db.Column(db.String(100), nullable=True)
    apellido = db.Column(db.String(100), nullable=True)
    telefono = db.Column(db.String(20), nullable=True)
    descripcion = db.Column(db.String(255), nullable=True)
    direccion = db.Column(db.String(255), nullable=True)

    password_hash = db.Column(db.String(255), nullable=False)
    url_avatar = db.Column(db.String(255), nullable=True)
    url_footer = db.Column(db.String(255), nullable=True)
    es_admin = db.Column(db.Boolean, default=False)

    # Relaciones con su colección privada
    bandas = db.relationship('Banda', backref='usuario', lazy='dynamic', cascade="all, delete-orphan")
    albumes = db.relationship('Album', backref='usuario', lazy='dynamic', cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<Usuario {self.username}>'


class Banda(db.Model):
    __tablename__ = 'banda'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre = db.Column(db.String(255), nullable=False)
    formacion = db.Column(db.Integer, nullable=True)
    disolucion = db.Column(db.Integer, nullable=True)
    activo = db.Column(db.Boolean, default=True)
    logo = db.Column(db.String(500), nullable=True)

    # Claves foráneas (Usuario y País)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id', ondelete='CASCADE'), nullable=False, index=True)
    pais_id = db.Column(db.Integer, db.ForeignKey('pais.id'), nullable=True)

    # Relaciones
    generos = db.relationship('Genero', secondary=banda_genero, backref=db.backref('bandas', lazy='select'))
    albumes = db.relationship('Album', backref='banda', lazy=True, cascade="all, delete-orphan")

    # Índice para acelerar búsquedas
    __table_args__ = (
        db.Index('idx_banda_usuario_nombre', 'usuario_id', 'nombre'),
    )

    def __repr__(self):
        return f'<Banda {self.nombre}>'


class Ubicacion(db.Model):
    __tablename__ = 'ubicaciones'

    id = db.Column(db.Integer, primary_key=True)
    mueble = db.Column(db.String(100), nullable=False)   # Ej: "Mueble 1", "Estantería Principal", "Rack Vinilos"
    estante = db.Column(db.String(100), nullable=False)  # Ej: "Estante 2", "Nivel Superior", "Caja 3"
    descripcion = db.Column(db.String(255), nullable=True) # Notas opcionales (ej: "Lado izquierdo")

    # Cada usuario administra sus propias ubicaciones
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)

    # Relación inversa con los discos guardados allí
    albumes = db.relationship('Album', backref='ubicacion', lazy='dynamic')

    def __repr__(self):
        return f"{self.mueble} - {self.estante}"


class Album(db.Model):
    __tablename__ = 'album'

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(150), nullable=False)
    lanzamiento = db.Column(db.Integer, nullable=True)        # Año de la edición/lanzamiento específico
    es_reedicion = db.Column(db.Boolean, default=False)        # Flag opcional para marcar si es reedición
    anio_original = db.Column(db.Integer, nullable=True)       # Opcional: año del lanzamiento original de la obra
    numero_catalogo = db.Column(db.String(50), nullable=True)  # Ej: "NR 055", "OSMOSE 001"
    numero_pistas = db.Column(db.Integer, nullable=True)
    duracion_total = db.Column(db.Interval, nullable=True)
    notas = db.Column(db.Text, nullable=True)
    url_portada = db.Column(db.String(500), nullable=True)
    ubicacion_fisica = db.Column(db.String(100), nullable=True)
    disponible = db.Column(db.Boolean, default=True, server_default=text('true'), nullable=False)
    precio = db.Column(db.Float, default=0.0)
    visible = db.Column(db.Boolean, default=True, server_default=text('true'), nullable=False)

    # Claves foráneas
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id', ondelete='CASCADE'), nullable=False, index=True)
    banda_id = db.Column(db.Integer, db.ForeignKey('banda.id', ondelete='CASCADE'), nullable=False, index=True)
    sello_id = db.Column(db.Integer, db.ForeignKey('sello_discografico.id'), nullable=True)
    ubicacion_id = db.Column(db.Integer, db.ForeignKey('ubicaciones.id'), nullable=True)

    # Relaciones
    sello = db.relationship('SelloDiscografico', backref='albumes', lazy=True)
    formatos = db.relationship('Formato', secondary=album_formato, backref=db.backref('albumes', lazy='dynamic'))

    # Índices compuestos
    __table_args__ = (
        db.Index('idx_album_usuario_titulo', 'usuario_id', 'titulo'),
        db.Index('idx_album_banda_lanzamiento', 'banda_id', 'lanzamiento'),
    )

    def __repr__(self):
        return f'<Album {self.titulo} ({self.lanzamiento})>'


class ListaDeseos(db.Model):
    __tablename__ = 'lista_deseos'

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)

    # Datos básicos del deseo
    banda = db.Column(db.String(120), nullable=False)
    disco = db.Column(db.String(150), nullable=False)

    # Clave foránea al Formato Principal (Padre)
    formato_id = db.Column(db.Integer, db.ForeignKey('formato.id'), nullable=False)

    # Clasificación y Estados
    prioridad = db.Column(db.String(10), nullable=False, default='Media')  # 'Alta', 'Media', 'Baja'
    es_mio = db.Column(db.Boolean, default=False, nullable=False)

    # Fechas
    fecha_alta = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    fecha_adquisicion = db.Column(db.DateTime, nullable=True)

    # Relaciones SQLAlchemy
    usuario = db.relationship('Usuario', backref=db.backref('deseos', lazy=True))
    formato = db.relationship('Formato', backref=db.backref('deseos', lazy=True))

    def __repr__(self):
        return f'<Deseo {self.banda} - {self.disco} ({self.formato.nombre if self.formato else "Sin Formato"})>'