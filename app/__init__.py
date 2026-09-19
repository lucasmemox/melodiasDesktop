from datetime import datetime, timedelta, timezone
import json
import os
import sys
from flask import Flask, redirect, request, url_for, send_from_directory
from flask_admin import Admin, AdminIndexView, expose
from flask_admin.contrib.sqla import ModelView
from flask_login import LoginManager, current_user, login_user
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from wtforms import PasswordField

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()


def get_user_data_dir():
    """Ruta persistente en AppData del usuario (sobrevive a reinstalaciones/actualizaciones)."""
    app_data = os.path.join(
        os.environ.get('APPDATA', os.path.expanduser('~')), 'MelodiasLocal'
    )
    os.makedirs(app_data, exist_ok=True)
    return app_data


def get_bundle_dir():
    """Ruta temporal de PyInstaller o directorio actual en desarrollo."""
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.abspath(os.path.dirname(__file__))


def init_default_user():
    """Crea el usuario 'coleccionista' (ID 1) si no existe."""
    from app.models import Usuario

    user = db.session.get(Usuario, 1)
    if not user:
        usuario_local = Usuario(
            id=1,
            username='coleccionista',
            email='local@melodias.app',
            nombre='Usuario',
            apellido='Local',
            es_admin=True
        )
        usuario_local.set_password('metal123')
        db.session.add(usuario_local)
        db.session.commit()


def poblar_desde_json():
    """Puebla las tablas maestras si están vacías leyendo seeds.json."""
    from app.models import Formato, Genero, Pais, SelloDiscografico

    # Verificación global: si todas las tablas clave tienen datos, no ejecutamos nada
    if (Pais.query.count() > 0 and
        Formato.query.count() > 0 and
        Genero.query.count() > 0 and
        SelloDiscografico.query.count() > 0):
        return

    bundle_dir = get_bundle_dir()
    json_path = os.path.join(bundle_dir, 'seeds.json')

    if not os.path.exists(json_path):
        json_path = os.path.join(bundle_dir, 'app', 'seeds.json')

    if not os.path.exists(json_path):
        print("No se encontró el archivo seeds.json")
        return

    with open(json_path, 'r', encoding='utf-8') as f:
        datos = json.load(f)

    # 1. Países
    if Pais.query.count() == 0:
        for item in datos.get('pais', []):
            db.session.add(
                Pais(
                    id=item['id'],
                    nombre=item['nombre'],
                    continente=item.get('continente', 'Desconocido'),
                    codigo_iso=item.get('codigo_iso')
                )
            )

    # 2. Formatos
    if Formato.query.count() == 0:
        for item in datos.get('formato', []):
            db.session.add(
                Formato(
                    id=item['id'],
                    nombre=item['nombre'],
                    padre_id=item.get('padre_id')
                )
            )

    # 3. Géneros
    if Genero.query.count() == 0:
        for item in datos.get('genero', []):
            db.session.add(
                Genero(
                    id=item['id'],
                    nombre=item['nombre'],
                    descripcion=item.get('descripcion')
                )
            )

    # 4. Sellos Discográficos (Soporta la clave 'sello' o 'sello_discografico')
    if SelloDiscografico.query.count() == 0:
        sellos_json = datos.get('sello_discografico') or datos.get('sello') or []
        for item in sellos_json:
            db.session.add(
                SelloDiscografico(
                    id=item['id'],
                    nombre=item['nombre'],
                    pais_id=item.get('pais_id')
                )
            )

    db.session.commit()
    print("Tablas maestras pobladas correctamente.")


def create_app():
    bundle_dir = get_bundle_dir()
    data_dir = get_user_data_dir()

    # Detección flexible de plantillas y archivos estáticos
    template_dir = os.path.join(bundle_dir, 'templates')
    if not os.path.exists(template_dir):
        template_dir = os.path.join(bundle_dir, 'app', 'templates')

    static_dir = os.path.join(bundle_dir, 'static')
    if not os.path.exists(static_dir):
        static_dir = os.path.join(bundle_dir, 'app', 'static')

    app = Flask(__name__,
                template_folder=template_dir,
                static_folder=static_dir)

    db_path = os.path.join(data_dir, 'melodias_local.db')
    covers_path = os.path.join(data_dir, 'uploads', 'covers')
    os.makedirs(covers_path, exist_ok=True)

    app.config['SQLALCHEMY_DATABASE_URI'] = (
        f'sqlite:///{os.path.abspath(db_path)}'
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'melodias-desktop-secret'
    app.config['UPLOAD_FOLDER'] = covers_path
    app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=365)
    app.config['REMEMBER_COOKIE_REFRESH_EACH_REQUEST'] = True

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'main.login'
    migrate.init_app(app, db)

    from app.models import Usuario

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(Usuario, int(user_id))

    @app.before_request
    def auto_login_desktop():
        if not current_user.is_authenticated:
            from app.models import Usuario
            user = db.session.get(Usuario, 1)
            if user is not None:
                login_user(user, remember=True)

    @app.context_processor
    def inject_now():
        return {'now': lambda: datetime.now(timezone.utc)}

    # Ruta con respaldo automático para servir portadas en Dev y Producción
    @app.route('/uploads/covers/<path:filename>', endpoint='serve_cover_uploads')
    @app.route('/static/uploads/covers/<path:filename>', endpoint='serve_cover_static')
    def serve_cover(filename):
        # Lista exhaustiva de rutas posibles en entorno local (Dev) y compilado (Desktop)
        posibles_rutas = [
            covers_path,  # AppData / ~/MelodiasLocal/uploads/covers
            os.path.join(static_dir, 'uploads', 'covers'),
            os.path.abspath(os.path.join(bundle_dir, '..', 'app', 'static', 'uploads', 'covers')),
            os.path.abspath(os.path.join(bundle_dir, '..', 'static', 'uploads', 'covers')),
            os.path.abspath(os.path.join(os.getcwd(), 'app', 'static', 'uploads', 'covers')),
            os.path.abspath(os.path.join(os.getcwd(), 'static', 'uploads', 'covers')),
        ]

        for carpeta in posibles_rutas:
            ruta_completa = os.path.join(carpeta, filename)
            if os.path.exists(ruta_completa):
                return send_from_directory(carpeta, filename)

        print(f"[WARN] No se encontró '{filename}' en ninguna ruta:")
        for r in posibles_rutas:
            print(f"  - {r}")

        return send_from_directory(covers_path, filename)

    from app.routes import main_bp

    app.register_blueprint(main_bp)

    with app.app_context():
        db.create_all()
        init_default_user()
        poblar_desde_json()

    return app