from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, Response, current_app, send_file
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from app.models import Usuario, Banda, Pais, Album, Formato, Genero, SelloDiscografico, Ubicacion, Pais
from app import db
import io, csv, os, time, requests,  uuid
from sqlalchemy import func
from sqlalchemy.orm import joinedload, selectinload
from app.utils import guardar_logo_banda, guardar_portada_album
from werkzeug.security import check_password_hash, generate_password_hash
from app.discogs_service import buscar_disco_discogs, obtener_detalle_banda_discogs
from app.discogs_service import buscar_banda_discogs as service_buscar_banda_discogs
from urllib.parse import quote
from PIL import Image
from app.forms import FormatoForm, UbicacionForm, SelloDiscograficoForm, GeneroForm

main_bp = Blueprint('main', __name__)


def _filtrar_bandas_usuario(query_texto):
    """Auxiliar para filtrar las bandas pertenecientes ÚNICAMENTE al usuario logueado."""
    base_query = Banda.query.filter(Banda.usuario_id == current_user.id)

    if not query_texto:
        return base_query

    # Necesarios para evitar errores de consulta sobre tablas no vinculadas
    return base_query.outerjoin(Banda.pais).outerjoin(Banda.generos).filter(
        db.or_(
            Banda.nombre.ilike(f'%{query_texto}%'),
            Pais.nombre.ilike(f'%{query_texto}%'),
            Genero.nombre.ilike(f'%{query_texto}%')
        )
    ).distinct()


@main_bp.route('/')
@login_required
def index():
    page = request.args.get('page', 1, type=int)
    q = request.args.get('q', '', type=str).strip()

    query = _filtrar_bandas_usuario(q)
    bandas = query.order_by(Banda.nombre.asc()).paginate(page=page, per_page=9, error_out=False)

    return render_template('index.html', bandas=bandas, q=q)


@main_bp.route('/api/bandas/buscar')
@login_required
def api_buscar_bandas():
    q = request.args.get('q', '', type=str).strip()

    limit = 30 if q else 9
    bandas = _filtrar_bandas_usuario(q).order_by(Banda.nombre.asc()).limit(limit).all()

    resultados = [
        {
            'id': b.id,
            'nombre': b.nombre,
            'logo': url_for('static', filename=f'uploads/covers/{b.logo}') if b.logo else None,
            'pais': b.pais.nombre if b.pais else None,
            'genero': " / ".join([g.nombre for g in b.generos]) if b.generos else 'No especificado',
            'formacion': b.formacion or '?',
            'disolucion': b.disolucion or ('Activo' if b.activo else 'Disuelta'),
            'albumes_count': len(b.albumes),
            'albumes': [{'titulo': a.titulo, 'lanzamiento': a.lanzamiento or 'S/A'} for a in b.albumes[:3]],
            'detalle_url': url_for('main.detalle_banda', id=b.id),
            'edit_url': url_for('main.editar_banda', id=b.id)
        }
        for b in bandas
    ]

    return jsonify({
        'bandas': resultados,
        'es_admin': current_user.es_admin
    })


@main_bp.route('/banda/<int:id>')
@login_required
def detalle_banda(id):
    # Carga la banda filtrada por el usuario junto con sus álbumes, sellos y ubicaciones
    banda = Banda.query.options(
        joinedload(Banda.albumes).joinedload(Album.ubicacion),
        joinedload(Banda.albumes).joinedload(Album.sello)
    ).filter_by(id=id, usuario_id=current_user.id).first_or_404()

    return render_template('detalle_banda.html', banda=banda)


@main_bp.route('/banda/nueva', methods=['GET', 'POST'])
@login_required
def nueva_banda():
    if request.method == 'POST':
        nombre_raw = request.form.get('nombre', '')
        nombre = nombre_raw.strip().upper()

        # Usamos tu helper con Pillow/WebP
        logo_file = request.files.get('logo')
        discogs_url = request.form.get('logo_discogs_url')
        nombre_archivo_logo = guardar_logo_banda(file_storage=logo_file, discogs_url=discogs_url)

        nueva_banda = Banda(
            nombre=nombre,
            logo=nombre_archivo_logo,
            pais_id=request.form.get('pais_id') or None,
            formacion=request.form.get('formacion') or None,
            disolucion=request.form.get('disolucion') or None,
            activo='activo' in request.form,
            usuario_id=current_user.id
        )

        generos_ids = request.form.getlist('generos')
        if generos_ids:
            nueva_banda.generos = Genero.query.filter(Genero.id.in_(generos_ids)).all()

        db.session.add(nueva_banda)
        db.session.commit()
        flash('Banda creada correctamente.', 'success')
        return redirect(url_for('main.detalle_banda', id=nueva_banda.id))

    paises = Pais.query.order_by(Pais.nombre.asc()).all()
    generos = Genero.query.order_by(Genero.nombre.asc()).all()
    return render_template('banda_form.html', banda=None, paises=paises, generos=generos)


@main_bp.route('/banda/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_banda(id):
    banda = Banda.query.filter_by(id=id, usuario_id=current_user.id).first_or_404()

    if request.method == 'POST':
        nombre_raw = request.form.get('nombre', '')
        banda.nombre = nombre_raw.strip().upper()
        banda.pais_id = request.form.get('pais_id') or None
        banda.formacion = request.form.get('formacion') or None
        banda.disolucion = request.form.get('disolucion') or None
        banda.activo = 'activo' in request.form

        generos_ids = request.form.getlist('generos')
        banda.generos = Genero.query.filter(Genero.id.in_(generos_ids)).all() if generos_ids else []

        # --- GESTIÓN DE LOGO ---
        logo_file = request.files.get('logo')
        discogs_url = request.form.get('logo_discogs_url')

        nuevo_logo = guardar_logo_banda(file_storage=logo_file, discogs_url=discogs_url)
        if nuevo_logo:
            banda.logo = nuevo_logo

        db.session.commit()
        flash('Banda actualizada correctamente.', 'success')
        return redirect(url_for('main.detalle_banda', id=banda.id))

    paises = Pais.query.order_by(Pais.nombre.asc()).all()
    generos = Genero.query.order_by(Genero.nombre.asc()).all()
    return render_template('banda_form.html', banda=banda, paises=paises, generos=generos)


@main_bp.route('/album/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo_album():
    banda_id = request.args.get('banda_id', type=int)
    banda = Banda.query.filter_by(id=banda_id, usuario_id=current_user.id).first_or_404()

    if request.method == 'POST':
        titulo = request.form.get('titulo')
        lanzamiento = request.form.get('lanzamiento') or None
        sello_id = request.form.get('sello_id') or None
        ubicacion_id = request.form.get('ubicacion_id') or None
        formato_id = request.form.get('formato_id')  # Es el ID del subformato
        notas = request.form.get('notas') or None

        disponible = request.form.get('disponible') == '1'
        portada_file = request.files.get('portada')
        url_remota = request.form.get('url_portada_remota')

        # Procesa archivo local si existe; de lo contrario, procesa la URL remota de Discogs
        ruta_portada = guardar_portada_album(portada_file, url_remota)

        nuevo_a = Album(
            titulo=titulo,
            lanzamiento=lanzamiento,
            sello_id=int(sello_id) if sello_id else None,
            ubicacion_id=int(ubicacion_id) if ubicacion_id else None,
            disponible=disponible,
            url_portada=ruta_portada,
            notas=notas.strip() if notas else None,
            banda_id=banda.id,
            usuario_id=current_user.id
        )

        if formato_id:
            subformato_obj = Formato.query.get(int(formato_id))
            if subformato_obj:
                nuevo_a.formatos = [subformato_obj]

        db.session.add(nuevo_a)
        db.session.commit()

        flash('Álbum agregado con éxito.', 'success')
        return redirect(url_for('main.detalle_banda', id=banda.id))

    sellos = SelloDiscografico.query.order_by(SelloDiscografico.nombre.asc()).all()
    # Traer solo los 5 formatos principales (los que no tienen padre)
    formatos = Formato.query.filter_by(padre_id=None).order_by(Formato.nombre.asc()).all()
    ubicaciones = Ubicacion.query.filter_by(usuario_id=current_user.id).order_by(Ubicacion.mueble.asc(), Ubicacion.estante.asc()).all()

    return render_template('album_form.html', album=None, banda=banda, sellos=sellos, formatos=formatos, ubicaciones=ubicaciones)


@main_bp.route('/album/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_album(id):
    album = Album.query.join(Banda).filter(Album.id == id, Banda.usuario_id == current_user.id).first_or_404()

    if request.method == 'POST':
        album.titulo = request.form.get('titulo')
        album.lanzamiento = request.form.get('lanzamiento') or None

        sello_id = request.form.get('sello_id')
        album.sello_id = int(sello_id) if sello_id else None

        ubicacion_id = request.form.get('ubicacion_id')
        album.ubicacion_id = int(ubicacion_id) if ubicacion_id else None

        album.disponible = request.form.get('disponible') == '1'

        notas = request.form.get('notas')
        album.notas = notas.strip() if notas else None

        # 1. Obtener archivo local y URL remota de Discogs
        portada_file = request.files.get('portada')
        url_remota = request.form.get('url_portada_remota')

        # 2. Procesar imagen (prioriza archivo subido, si no descarga de Discogs a WEBP)
        nueva_portada = guardar_portada_album(portada_file, url_remota)
        if nueva_portada:
            album.url_portada = nueva_portada

        # 3. Formatos
        formato_id = request.form.get('formato_id')
        if formato_id:
            subformato_obj = Formato.query.get(int(formato_id))
            album.formatos = [subformato_obj] if subformato_obj else []
        else:
            album.formatos = []

        db.session.commit()
        flash('Álbum actualizado correctamente.', 'success')
        return redirect(url_for('main.detalle_banda', id=album.banda_id))

    sellos = SelloDiscografico.query.order_by(SelloDiscografico.nombre.asc()).all()
    formatos = Formato.query.filter_by(padre_id=None).order_by(Formato.nombre.asc()).all()
    ubicaciones = Ubicacion.query.filter_by(usuario_id=current_user.id).order_by(Ubicacion.mueble.asc(), Ubicacion.estante.asc()).all()

    return render_template('album_form.html', album=album, banda=album.banda, sellos=sellos, formatos=formatos, ubicaciones=ubicaciones)

@main_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        username_or_email = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        # Detecta si la casilla "Recordarme" o "Guardar clave" fue marcada
        remember_me = True if request.form.get('remember') else False

        # Permite buscar coincidencia por username O por email
        user = Usuario.query.filter(
            db.or_(
                Usuario.username == username_or_email,
                Usuario.email == username_or_email
            )
        ).first()

        if user and user.check_password(password):
            # Se le pasa el parámetro 'remember' a Flask-Login
            login_user(user, remember=remember_me)

            next_page = request.args.get('next')
            return redirect(next_page or url_for('main.index'))

        flash('Usuario o contraseña incorrectos.', 'danger')

    return render_template('login.html')


@main_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.login'))


@main_bp.route('/coleccion/exportar/csv')
@login_required
def exportar_csv():
    # Consultar la colección del usuario (podés agregar joinedload si querés optimizar aún más)
    albumes = Album.query.options(
    joinedload(Album.banda),
    joinedload(Album.sello),
    joinedload(Album.ubicacion),
    selectinload(Album.formatos).joinedload(Formato.padre)
    ).filter_by(usuario_id=current_user.id).all()

    # Crear buffer en memoria
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')  # Delimitador ';' ideal para Excel en español

    # Encabezados
    writer.writerow(['Banda', 'Título', 'Año', 'Sello', 'Ubicación Física', 'Formato'])

    for a in albumes:
        banda_nombre = a.banda.nombre if a.banda else ''
        sello_nombre = a.sello.nombre if a.sello else ''

        # --- LÓGICA PARA EXTRAER LA UBICACIÓN FÍSICA ---
        if a.ubicacion:
            # Si el modelo Ubicacion tiene 'nombre' usalo, de lo contrario combina mueble y estante
            if hasattr(a.ubicacion, 'nombre') and a.ubicacion.nombre:
                ubicacion_str = a.ubicacion.nombre
            else:
                mueble = getattr(a.ubicacion, 'mueble', '')
                estante = getattr(a.ubicacion, 'estante', '')
                ubicacion_str = f"{mueble} - Estante {estante}".strip(" -")
        else:
            ubicacion_str = ''

        # --- LÓGICA DE FORMATO PADRE - HIJO ---
        lista_formatos = []
        for f in a.formatos:
            if f.padre:
                # Si el formato tiene un padre asignado (ej: "Vinilo" -> "LP, 12\"")
                lista_formatos.append(f"{f.padre.nombre} - {f.nombre}")
            else:
                # Si es un formato raíz/padre directo
                lista_formatos.append(f.nombre)

        # Unir todos los formatos asignados al álbum separados por coma
        formato_str = ", ".join(lista_formatos) if lista_formatos else ''

        writer.writerow([
            banda_nombre,
            a.titulo,
            a.lanzamiento or '',
            sello_nombre,
            ubicacion_str or '',
            formato_str,
        ])

    # Configurar respuesta HTTP para descarga
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': 'attachment; filename=mi_coleccion.csv'}
    )

@main_bp.route('/api/discogs/buscar', methods=['GET'])
@login_required
def api_buscar_discogs():
    query = request.args.get('q', '').strip()
    if not query or len(query) < 3:
        return jsonify([])
    try:
        return jsonify(buscar_disco_discogs(query))
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main_bp.route('/api/discogs/buscar_banda', methods=['GET'])
@login_required
def api_buscar_banda_discogs():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])

    # 2. Llamada usando el alias importado
    resultados = service_buscar_banda_discogs(query)
    return jsonify(resultados)



@main_bp.app_context_processor
def inject_stats():
    # Si el usuario no está autenticado, devolvemos valores vacíos
    if not current_user.is_authenticated:
        return {'stats': None}

    # 1. Total de discos
    total_discos = Album.query.filter_by(usuario_id=current_user.id).count()

    # 2. Total de bandas únicas pertenecientes a la colección del usuario
    total_bandas = db.session.query(func.count(func.distinct(Album.banda_id)))\
                             .filter(Album.usuario_id == current_user.id)\
                             .scalar() or 0

    # 3. Distribución por Formato Cabecera (Padre)
    FormatoPadre = db.aliased(Formato)

    formato_counts = db.session.query(
        func.coalesce(FormatoPadre.nombre, Formato.nombre).label('nombre_cabecera'),
        func.count(Album.id)
    ).join(Album.formatos)\
     .outerjoin(FormatoPadre, Formato.padre_id == FormatoPadre.id)\
     .filter(Album.usuario_id == current_user.id)\
     .group_by('nombre_cabecera')\
     .order_by(func.count(Album.id).desc())\
     .all()

    distribucion_formatos = []
    if total_discos > 0:
        for nombre_formato, cantidad in formato_counts:
            porcentaje = round((cantidad / total_discos) * 100, 1)
            distribucion_formatos.append({
                'nombre': nombre_formato,
                'cantidad': cantidad,
                'porcentaje': porcentaje
            })

    # 4. Top 3 o Top 5 de Bandas con más lanzamientos cargados
    top_bandas = db.session.query(
        Banda.nombre,
        func.count(Album.id).label('total_albumes')
    ).join(Album, Banda.id == Album.banda_id)\
     .filter(Album.usuario_id == current_user.id)\
     .group_by(Banda.id)\
     .order_by(func.count(Album.id).desc())\
     .limit(5).all()

    return {
        'stats': {
            'total_discos': total_discos,
            'total_bandas': total_bandas,
            'formatos': distribucion_formatos,
            'top_bandas': top_bandas
        }
    }

@main_bp.route('/api/discogs/buscar_banda')
@login_required
def buscar_banda_discogs():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])

    # 1. Obtener configuraciones de Flask
    token = current_app.config.get('DISCOGS_TOKEN', '')
    user_agent = current_app.config.get('DISCOGS_USER_AGENT', 'MelodiasDesktop/1.0')

    # 2. Configurar headers según las reglas de Discogs
    headers = {
        'User-Agent': user_agent
    }

    # 3. Pasar los parámetros en la petición de requests (evita errores con caracteres especiales)
    params = {
        'q': query,
        'type': 'artist',
        'per_page': 5
    }

    # Agregar el token si existe
    if token:
        params['token'] = token

    url = "https://api.discogs.com/database/search"

    try:
        response = requests.get(url, headers=headers, params=params, timeout=5)

        # Imprimir en consola si Discogs devuelve un error HTTP (ej. 401, 403, 429)
        if response.status_code != 200:
            print(f"--> Error Discogs API status {response.status_code}: {response.text}")
            return jsonify([])

        data = response.json()
        resultados = []

        for item in data.get('results', []):
            imagen_url = item.get('cover_image') or item.get('thumb') or ''

            if 'spacer.gif' in imagen_url:
                imagen_url = ''

            resultados.append({
                'id': item.get('id'),
                'nombre_original': item.get('title'),
                'portada': imagen_url,
                'perfil_corto': item.get('snippet', '') or item.get('title')
            })

        return jsonify(resultados)

    except Exception as e:
        print(f"--> Excepción en la llamada a Discogs: {e}")
        return jsonify([])


# ==========================================
# SECCIÓN: COLECCIÓN DEL USUARIO
# =========================================
@main_bp.route('/coleccion')
@login_required
def ver_coleccion():
    # Obtener parámetros de la URL
    q = request.args.get('q', default='', type=str).strip()
    formato_id = request.args.get('formato_id', type=int)
    genero_id = request.args.get('genero_id', type=int)
    sello_id = request.args.get('sello_id', type=int)
    pais_id = request.args.get('pais_id', type=int)

    # Base Query: Álbumes del usuario actual
    query = Album.query.join(Banda).filter(Album.usuario_id == current_user.id)

    # Búsqueda por Texto (Afecta tanto al nombre de la Banda como al Título del Álbum)
    if q:
        termino = f"%{q}%"
        query = query.filter(
            db.or_(
                Banda.nombre.ilike(termino),
                Album.titulo.ilike(termino)
            )
        )

    # Filtro por Formato (incluye subformatos)
    if formato_id:
        query = query.filter(
            Album.formatos.any(
                db.or_(
                    Formato.id == formato_id,
                    Formato.padre_id == formato_id
                )
            )
        )

    # Filtro por Género (asociado a la Banda del álbum)
    if genero_id:
        query = query.filter(Banda.generos.any(Genero.id == genero_id))

    # Filtro por Sello Discográfico
    if sello_id:
        query = query.filter(Album.sello_id == sello_id)

    # Filtro por País de origen de la Banda
    if pais_id:
        query = query.filter(Banda.pais_id == pais_id)

    # Ordenar por Nombre de Banda y Título del Álbum
    albumes = query.order_by(Banda.nombre.asc(), Album.titulo.asc()).all()

    # Opciones para rellenar los selectores de filtros
    formatos = Formato.query.filter(Formato.padre_id.is_(None)).order_by(Formato.nombre.asc()).all()
    generos = Genero.query.order_by(Genero.nombre.asc()).all()
    sellos = SelloDiscografico.query.order_by(SelloDiscografico.nombre.asc()).all()
    paises = Pais.query.order_by(Pais.nombre.asc()).all()

    return render_template(
        'coleccion.html',
        albumes=albumes,
        formatos=formatos,
        generos=generos,
        sellos=sellos,
        paises=paises,
        filtros_acti={
            'q': q,
            'formato_id': formato_id,
            'genero_id': genero_id,
            'sello_id': sello_id,
            'pais_id': pais_id
        }
    )

# ==========================================
# SECCIÓN: API DISCOS / BANDAS
# ========================================

@main_bp.route('/api/discogs/banda/<int:artist_id>', methods=['GET'])
@login_required
def api_detalle_banda_discogs(artist_id):
    detalle = obtener_detalle_banda_discogs(artist_id)
    if not detalle:
        return jsonify({'error': 'No se encontró la banda'}), 404
    return jsonify(detalle)



# ==========================================
# SECCIÓN: PERFIL DE USUARIO
# ==========================================

@main_bp.route('/perfil', methods=['GET', 'POST'])
@login_required
def perfil():
    if request.method == 'POST':
        nickname = request.form.get('nickname')
        email = request.form.get('email')

        # Campos de contraseña
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if 'avatar' in request.files:
            file = request.files['avatar']
            if file and file.filename != '':
                # Borrar logo anterior si existe para no acumular basura
                if current_user.url_avatar:
                    ruta_vieja = os.path.join(current_app.root_path, 'static', current_user.url_avatar)
                    if os.path.exists(ruta_vieja):
                        try:
                            os.remove(ruta_vieja)
                        except OSError:
                            pass

                # Guardar el nuevo logo manteniendo proporción y transparencia
                current_user.url_avatar = guardar_logo_usuario(file)

        # IMAGEN DEL FOOTER
        if 'footer_img' in request.files:
            file_footer = request.files['footer_img']
            if file_footer and file_footer.filename != '':
                # Borrar banner anterior si existe
                if current_user.url_footer:
                    ruta_footer_vieja = os.path.join(current_app.root_path, 'static', current_user.url_footer)
                    if os.path.exists(ruta_footer_vieja):
                        try:
                            os.remove(ruta_footer_vieja)
                        except OSError:
                            pass

                # Guardar el nuevo banner optimizado
                current_user.url_footer = guardar_footer_usuario(file_footer)

        # Actualizamos datos básicos
        current_user.nickname = nickname
        current_user.email = email

        # Lógica de cambio de contraseña si el usuario completó algún campo
        if current_password or new_password or confirm_password:
            if not current_password or not new_password or not confirm_password:
                flash('Para cambiar la contraseña debes completar todos los campos de seguridad.', 'warning')
                return redirect(url_for('main.perfil'))

            # Validar contraseña actual (soporta atributo password_hash o clave_hash según tu modelo)
            password_actual_hash = getattr(current_user, 'password_hash', getattr(current_user, 'clave_hash', None))

            if not check_password_hash(password_actual_hash, current_password):
                flash('La contraseña actual es incorrecta.', 'danger')
                return redirect(url_for('main.perfil'))

            if new_password != confirm_password:
                flash('Las nuevas contraseñas no coinciden.', 'danger')
                return redirect(url_for('main.perfil'))

            if len(new_password) < 6:
                flash('La nueva contraseña debe tener al menos 6 caracteres.', 'warning')
                return redirect(url_for('main.perfil'))

            # Asignamos el nuevo hash
            if hasattr(current_user, 'password_hash'):
                current_user.password_hash = generate_password_hash(new_password)
            elif hasattr(current_user, 'clave_hash'):
                current_user.clave_hash = generate_password_hash(new_password)
            elif hasattr(current_user, 'set_password'):
                current_user.set_password(new_password)

            flash('Contraseña actualizada con éxito.', 'success')

        db.session.commit()
        flash('Perfil actualizado correctamente.', 'success')
        return redirect(url_for('main.perfil'))

    return render_template('perfil.html', usuario=current_user)

# Función auxiliar para guardar logo de usuario
def guardar_logo_usuario(file_storage):
    """Redimensiona el logo conservando proporción y transparencia (Alto máx: 180px)"""
    nombre_archivo = f"logo_{uuid.uuid4().hex[:8]}.webp"

    carpeta_destino = os.path.join(current_app.root_path, 'static', 'uploads', 'logos')
    os.makedirs(carpeta_destino, exist_ok=True)
    ruta_completa = os.path.join(carpeta_destino, nombre_archivo)

    img = Image.open(file_storage)

    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA")

    # Mayor resolución máxima para preservar nitidez
    alto_max = 180
    ancho_original, alto_original = img.size

    if alto_original > alto_max:
        ratio = alto_max / float(alto_original)
        ancho_nuevo = int(float(ancho_original) * float(ratio))
        img = img.resize((ancho_nuevo, alto_max), Image.Resampling.LANCZOS)

    img.save(ruta_completa, 'WEBP', quality=95)

    return f"uploads/logos/{nombre_archivo}"

# ==========================================
# Función auxiliar para guardar imagen de footer/banner de usuario
# ==========================================

def guardar_footer_usuario(file_storage):
    """Redimensiona el banner/footer conservando proporción y transparencia (Ancho máx: 1200px)"""
    nombre_archivo = f"footer_{uuid.uuid4().hex[:8]}.webp"

    carpeta_destino = os.path.join(current_app.root_path, 'static', 'uploads', 'footers')
    os.makedirs(carpeta_destino, exist_ok=True)
    ruta_completa = os.path.join(carpeta_destino, nombre_archivo)

    img = Image.open(file_storage)

    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA")

    # Ancho máximo ideal para banners responsivos
    ancho_max = 1200
    ancho_original, alto_original = img.size

    if ancho_original > ancho_max:
        ratio = ancho_max / float(ancho_original)
        alto_nuevo = int(float(alto_original) * float(ratio))
        img = img.resize((ancho_max, alto_nuevo), Image.Resampling.LANCZOS)

    img.save(ruta_completa, 'WEBP', quality=90)

    return f"uploads/footers/{nombre_archivo}"


@main_bp.route('/api/albumes/buscar')
@login_required
def buscar_albumes():
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify({'albumes': []})

    albumes = Album.query.join(Banda).filter(
        (Album.titulo.ilike(f'%{q}%')) | (Banda.nombre.ilike(f'%{q}%'))
    ).limit(10).all()

    return jsonify({'albumes': [{
        'id': a.id,
        'titulo': a.titulo,
        'banda': a.banda.nombre,
        'lanzamiento': a.lanzamiento
    } for a in albumes]})

# --- LISTAR Y CREAR UBICACIONES ---
@main_bp.route('/ubicaciones', methods=['GET', 'POST'])
@login_required
def listar_ubicaciones():
    form = UbicacionForm()
    if form.validate_on_submit():
        nueva_ubicacion = Ubicacion(
            mueble=form.mueble.data,
            estante=form.estante.data,
            descripcion=form.descripcion.data,
            usuario_id=current_user.id
        )
        db.session.add(nueva_ubicacion)
        db.session.commit()
        flash('Ubicación guardada con éxito.', 'success')
        return redirect(url_for('main.listar_ubicaciones'))

    # Se obtienen únicamente las ubicaciones del usuario autenticado
    ubicaciones = Ubicacion.query.filter_by(usuario_id=current_user.id).order_by(Ubicacion.mueble, Ubicacion.estante).all()
    return render_template('ubicaciones/listar.html', ubicaciones=ubicaciones, form=form)

# --- EDITAR UBICACIÓN ---
@main_bp.route('/ubicaciones/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_ubicacion(id):
    ubicacion = Ubicacion.query.filter_by(id=id, usuario_id=current_user.id).first_or_404()
    form = UbicacionForm(obj=ubicacion)

    if form.validate_on_submit():
        ubicacion.mueble = form.mueble.data
        ubicacion.estante = form.estante.data
        ubicacion.descripcion = form.descripcion.data
        db.session.commit()
        flash('Ubicación actualizada correctamente.', 'success')
        return redirect(url_for('main.listar_ubicaciones'))

    return render_template('ubicaciones/editar.html', form=form, ubicacion=ubicacion)

# --- ELIMINAR UBICACIÓN ---
@main_bp.route('/ubicaciones/<int:id>/eliminar', methods=['POST'])
@login_required
def eliminar_ubicacion(id):
    ubicacion = Ubicacion.query.filter_by(id=id, usuario_id=current_user.id).first_or_404()

    # Verificar si tiene álbumes o discos asociados antes de borrar
    if ubicacion.albumes.count() > 0:
        flash(f'No se puede eliminar "{ubicacion.mueble} - {ubicacion.estante}" porque tiene {ubicacion.albumes.count()} disco(s) asignados.', 'warning')
        return redirect(url_for('main.listar_ubicaciones'))

    db.session.delete(ubicacion)
    db.session.commit()
    flash('Ubicación eliminada con éxito.', 'info')
    return redirect(url_for('main.listar_ubicaciones'))

@main_bp.route('/ubicaciones/<int:id>/exportar', methods=['GET'])
@login_required
def exportar_ubicacion(id):
    ubicacion = Ubicacion.query.filter_by(id=id, usuario_id=current_user.id).first_or_404()

    # Como la relación es lazy='dynamic', ejecutamos .all() para obtener la lista real
    discos = ubicacion.albumes.all() if hasattr(ubicacion.albumes, 'all') else ubicacion.albumes

    if not discos:
        flash('La ubicación no tiene discos para exportar.', 'warning')
        return redirect(url_for('main.listar_ubicaciones'))

    # Crear buffer en memoria
    si = io.StringIO()
    # Agregar BOM UTF-8 para que Excel reconozca correctamente caracteres con tilde/ñ
    si.write('\ufeff')

    cw = csv.writer(si, delimiter=';')

    # Encabezados
    cw.writerow(['Banda', 'Título', 'Lanzamiento', 'Mueble', 'Estante'])

    # Filas con los discos
    for album in discos:
        banda_nombre = album.banda.nombre if album.banda else 'Varios Artistas'
        cw.writerow([banda_nombre, album.titulo, album.lanzamiento or '', ubicacion.mueble, ubicacion.estante])

    output = si.getvalue()
    nombre_archivo = f"discos_{ubicacion.mueble}_{ubicacion.estante}.csv".replace(" ", "_").lower()

    return Response(
        output,
        mimetype="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename={nombre_archivo}",
            "Content-Type": "text/csv; charset=utf-8"
        }
    )

@main_bp.route('/ubicaciones/mover', methods=['GET', 'POST'])
@login_required
def mover_discos_ubicacion():
    if request.method == 'POST':
        origen_id = request.form.get('origen_id', type=int)
        destino_id = request.form.get('destino_id', type=int)
        album_ids = request.form.getlist('album_ids', type=int)

        if not album_ids:
            flash('No seleccionaste ningún disco para mover.', 'warning')
            return redirect(url_for('main.mover_discos_ubicacion', origen_id=origen_id, destino_id=destino_id))

        # Validar si el usuario omitió la ubicación destino
        if destino_id is None:
            flash('Debes seleccionar una ubicación destino válida.', 'danger')
            return redirect(url_for('main.mover_discos_ubicacion', origen_id=origen_id))

        # Definir el nuevo destino: si es 0 pasa a ser None ("Sin Ubicación"), si es mayor a 0 mantiene el ID
        nuevo_destino = destino_id if destino_id > 0 else None

        # Actualización masiva
        Album.query.filter(
            Album.id.in_(album_ids),
            Album.usuario_id == current_user.id
        ).update({Album.ubicacion_id: nuevo_destino}, synchronize_session=False)

        db.session.commit()
        flash(f'Se movieron {len(album_ids)} discos correctamente.', 'success')

        return redirect(url_for('main.mover_discos_ubicacion', origen_id=nuevo_destino))

    # Método GET: Cargar ubicaciones y álbumes según el origen seleccionado
    origen_id = request.args.get('origen_id', type=int)
    destino_id = request.args.get('destino_id', type=int)

    ubicaciones = Ubicacion.query.filter_by(usuario_id=current_user.id).order_by(Ubicacion.mueble, Ubicacion.estante).all()

    albumes_origen = []
    if origen_id is not None:
        if origen_id == 0:
            # Opción 0: Discos sin ubicación asignada
            albumes_origen = Album.query.join(Banda).filter(
                Album.usuario_id == current_user.id,
                Album.ubicacion_id.is_(None)
            ).order_by(Banda.nombre, Album.titulo).all()
        else:
            albumes_origen = Album.query.join(Banda).filter(
                Album.usuario_id == current_user.id,
                Album.ubicacion_id == origen_id
            ).order_by(Banda.nombre, Album.titulo).all()

    albumes_destino = []
    if destino_id:
        albumes_destino = Album.query.filter_by(usuario_id=current_user.id, ubicacion_id=destino_id).all()

    return render_template(
        'ubicaciones/mover.html',
        ubicaciones=ubicaciones,
        origen_id=origen_id,
        destino_id=destino_id,
        albumes_origen=albumes_origen,
        albumes_destino=albumes_destino
    )

##################################
# --- LISTAR Y CREAR SELLOS ---
################################

@main_bp.route('/sellos', methods=['GET', 'POST'])
@login_required
def listar_sellos():
    form = SelloDiscograficoForm()

    # Cargar las opciones del combo desplegable de países
    paises = Pais.query.order_by(Pais.nombre).all()
    form.pais_id.choices = [(0, '-- Seleccionar País (Opcional) --')] + [(p.id, p.nombre) for p in paises]

    if form.validate_on_submit():
        pais_id_seleccionado = form.pais_id.data if form.pais_id.data != 0 else None

        nuevo_sello = SelloDiscografico(
            nombre=form.nombre.data.strip(),
            pais_id=pais_id_seleccionado
        )
        db.session.add(nuevo_sello)
        db.session.commit()
        flash('Sello discográfico agregado con éxito.', 'success')
        return redirect(url_for('main.listar_sellos'))

    # Traer sellos ordenados alfabéticamente
    sellos = SelloDiscografico.query.order_by(SelloDiscografico.nombre).all()
    return render_template('sellos/listar.html', sellos=sellos, form=form)

# --- EDITAR SELLO ---
@main_bp.route('/sellos/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_sello(id):
    sello = SelloDiscografico.query.get_or_404(id)
    form = SelloDiscograficoForm(obj=sello)

    # Cargar las opciones de países y preseleccionar la actual
    paises = Pais.query.order_by(Pais.nombre).all()
    form.pais_id.choices = [(0, '-- Seleccionar País (Opcional) --')] + [(p.id, p.nombre) for p in paises]

    if request.method == 'GET':
        form.pais_id.data = sello.pais_id if sello.pais_id else 0

    if form.validate_on_submit():
        sello.nombre = form.nombre.data.strip()
        sello.pais_id = form.pais_id.data if form.pais_id.data != 0 else None

        db.session.commit()
        flash('Sello discográfico actualizado con éxito.', 'success')
        return redirect(url_for('main.listar_sellos'))

    return render_template('sellos/editar.html', form=form, sello=sello)

# --- ELIMINAR SELLO ---
@main_bp.route('/sellos/<int:sello_id>/eliminar', methods=['POST'])
@login_required
def eliminar_sello(sello_id):
    sello = SelloDiscografico.query.get_or_404(sello_id)

    # Se reemplaza .count() por len() sobre la lista
    if sello.albumes and len(sello.albumes) > 0:
        flash('No se puede eliminar el sello porque tiene álbumes asociados.', 'danger')
        return redirect(url_for('main.listar_sellos'))

    db.session.delete(sello)
    db.session.commit()
    flash('Sello discográfico eliminado correctamente.', 'success')
    return redirect(url_for('main.listar_sellos'))

# --- LISTAR Y CREAR GÉNEROS ---
@main_bp.route('/generos', methods=['GET', 'POST'])
@login_required
def listar_generos():
    form = GeneroForm()

    if form.validate_on_submit():
        nuevo_genero = Genero(
            nombre=form.nombre.data.strip(),
            descripcion=form.descripcion.data.strip() if form.descripcion.data else None
        )
        db.session.add(nuevo_genero)
        db.session.commit()
        flash('Género musical guardado con éxito.', 'success')
        return redirect(url_for('main.listar_generos'))

    generos = Genero.query.order_by(Genero.nombre).all()
    return render_template('generos/listar.html', generos=generos, form=form)

# --- EDITAR GÉNERO ---
@main_bp.route('/generos/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_genero(id):
    genero = Genero.query.get_or_404(id)
    form = GeneroForm(obj=genero)

    if form.validate_on_submit():
        genero.nombre = form.nombre.data.strip()
        genero.descripcion = form.descripcion.data.strip() if form.descripcion.data else None

        db.session.commit()
        flash('Género musical actualizado correctamente.', 'success')
        return redirect(url_for('main.listar_generos'))

    return render_template('generos/editar.html', form=form, genero=genero)

# --- ELIMINAR GÉNERO ---
@main_bp.route('/generos/<int:id>/eliminar', methods=['POST'])
@login_required
def eliminar_genero(id):
    genero = Genero.query.get_or_404(id)

    # Si tenés relación con discos/bandas, podrías validar referencias antes de borrar:
    if hasattr(genero, 'albumes') and genero.albumes.count() > 0:
       flash(f'No se puede eliminar "{genero.nombre}" porque tiene discos asignados.', 'warning')
       return redirect(url_for('main.listar_generos'))

    db.session.delete(genero)
    db.session.commit()
    flash('Género eliminado con éxito.', 'info')
    return redirect(url_for('main.listar_generos'))

# ==========================================
# SECCIÓN: FORMATOS Y SUBFORMATOS
# ==========================================
@main_bp.route('/formatos', methods=['GET', 'POST'])
@login_required
def listar_formatos():
    form = FormatoForm()
    # Cargar los formatos principales ([NULL] en padre_id) para el selector
    formatos_padre = Formato.query.filter(Formato.padre_id.is_(None)).order_by(Formato.nombre.asc()).all()

    # Llenar las opciones del SelectField (0 para 'Ninguno / Formato Principal')
    form.padre_id.choices = [(0, '-- Formato Principal (Sin Padre) --')] + [(f.id, f.nombre) for f in formatos_padre]

    if form.validate_on_submit():
        padre_id_val = form.padre_id.data if form.padre_id.data != 0 else None
        nuevo_formato = Formato(nombre=form.nombre.data, padre_id=padre_id_val)
        db.session.add(nuevo_formato)
        db.session.commit()
        flash('Formato creado exitosamente.', 'success')
        return redirect(url_for('main.listar_formatos'))

    # Traer todos los formatos agrupados por jerarquía
    formatos = Formato.query.order_by(Formato.padre_id.asc().nullsfirst(), Formato.nombre.asc()).all()

    return render_template('formatos/listar.html', formatos=formatos, form=form, formatos_padre=formatos_padre)

@main_bp.route('/formatos/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_formato(id):
    formato = Formato.query.get_or_404(id)
    form = FormatoForm(obj=formato)

    formatos_padre = Formato.query.filter(Formato.padre_id.is_(None), Formato.id != id).order_by(Formato.nombre.asc()).all()
    form.padre_id.choices = [(0, '-- Formato Principal (Sin Padre) --')] + [(f.id, f.nombre) for f in formatos_padre]

    if request.method == 'GET':
        form.padre_id.data = formato.padre_id if formato.padre_id else 0

    if form.validate_on_submit():
        formato.nombre = form.nombre.data
        formato.padre_id = form.padre_id.data if form.padre_id.data != 0 else None
        db.session.commit()
        flash('Formato actualizado correctamente.', 'success')
        return redirect(url_for('main.listar_formatos'))

    return render_template('formatos/editar.html', form=form, formato=formato)

@main_bp.route('/formatos/eliminar/<int:id>', methods=['POST'])
@login_required
def eliminar_formato(id):
    formato = Formato.query.get_or_404(id)

    # Evitar borrar si tiene subformatos o discos vinculados
    if formato.subformatos and len(formato.subformatos) > 0:
        flash('No se puede eliminar porque tiene subformatos asignados.', 'danger')
        return redirect(url_for('main.listar_formatos'))

    db.session.delete(formato)
    db.session.commit()
    flash('Formato eliminado correctamente.', 'success')
    return redirect(url_for('main.listar_formatos'))

# ==========================================
# SECCIÓN: CARGAR MÁS ÁLBUMES (Paginación)
# ==========================================
@main_bp.route('/api/u/<string:username>/albumes')
def api_cargar_mas_albumes(username):
    usuario_dueno = Usuario.query.filter_by(username=username).first_or_404()
    es_dueno = current_user.is_authenticated and current_user.id == usuario_dueno.id

    page = request.args.get('page', 2, type=int)
    per_page = 24
    tipo_formato = request.args.get('tipo_formato', None)

    query = Album.query.filter_by(usuario_id=usuario_dueno.id).outerjoin(Album.banda)

    if not es_dueno:
        query = query.filter(Album.visible == True)

    if tipo_formato:
        formato_buscado = tipo_formato.lower()
        query = query.join(Album.formatos).filter(
            (func.lower(Formato.nombre) == formato_buscado) |
            (Formato.padre.has(func.lower(Formato.nombre) == formato_buscado))
        )

    pagination = query.order_by(Banda.nombre.asc(), Album.titulo.asc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    html_tarjetas = render_template(
        'partials/_tarjetas_albumes.html',
        albumes=pagination.items,
        es_dueno=es_dueno
    )

    return jsonify({
        'html': html_tarjetas,
        'has_next': pagination.has_next,
        'next_page': pagination.next_num
    })