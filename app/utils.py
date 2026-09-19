import os, re, uuid, io, requests
from werkzeug.utils import secure_filename
from PIL import Image
from flask import current_app
from app.models import Pais


ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}

def extension_permitida(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def guardar_logo_banda(file_storage=None, discogs_url=None):
    img = None

    # 1. Opción A: Archivo local subido desde la PC (Prioridad)
    if file_storage and file_storage.filename != '' and extension_permitida(file_storage.filename):
        try:
            img = Image.open(file_storage)
        except Exception as e:
            print(f"Error al abrir la imagen subida: {e}")
            return None

    # 2. Opción B: Descarga desde la URL de Discogs
    elif discogs_url and discogs_url.strip() != '':
        try:
            # User-Agent completo para evitar bloqueo 403 de la CDN de Discogs
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            response = requests.get(discogs_url, headers=headers, timeout=10)

            if response.status_code == 200:
                img_bytes = io.BytesIO(response.content)
                img = Image.open(img_bytes)
            else:
                print(f"Error HTTP al descargar de Discogs: {response.status_code}")
                return None
        except Exception as e:
            print(f"Error al descargar imagen desde Discogs: {e}")
            return None

    # 3. Si no hay imagen válida de ninguna fuente, retornamos None
    if img is None:
        return None

    # 4. Procesamiento común con Pillow (Conversión a WebP, Resize y Guardado)
    try:
        nombre_unico = f"banda_{uuid.uuid4().hex[:8]}.webp"

        upload_path = os.path.join(current_app.root_path, 'static', 'uploads', 'covers')
        os.makedirs(upload_path, exist_ok=True)
        full_path = os.path.join(upload_path, nombre_unico)

        # Mantenemos canal Alfa para transparencias
        if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
            img = img.convert('RGBA')
        else:
            img = img.convert('RGB')

        # Redimensionamos a un máximo de 600px
        img.thumbnail((600, 600), Image.Resampling.LANCZOS)
        img.save(full_path, 'WEBP', quality=85, optimize=True)

        return nombre_unico
    except Exception as e:
        print(f"Error al optimizar y guardar la imagen: {e}")
        return None

def guardar_portada_album(file_obj=None, url_remota=None):
    img = None

    # 1. Intentar cargar desde archivo subido localmente
    if file_obj and file_obj.filename != '':
        ext = os.path.splitext(file_obj.filename)[1].lower()
        if ext in ['.jpg', '.jpeg', '.png', '.webp']:
            try:
                img = Image.open(file_obj)
            except Exception as e:
                current_app.logger.error(f"Error al abrir la imagen local: {e}")

    # 2. Si no hay archivo local, intentar descargar desde la URL remota de Discogs
    if img is None and url_remota:
        try:
            headers = {
                'User-Agent': current_app.config.get('DISCOGS_USER_AGENT', 'MelodiasMetalCatalog/1.0')
            }
            res = requests.get(url_remota, headers=headers, timeout=10)
            if res.status_code == 200:
                img = Image.open(io.BytesIO(res.content))
        except Exception as e:
            current_app.logger.error(f"Error descargando imagen de Discogs: {e}")

    # Si no se pudo obtener ninguna imagen válida, retornamos None
    if img is None:
        return None

    # 3. Procesar y optimizar con Pillow (Aplica para ambas fuentes)
    nombre_archivo = f"cover_{uuid.uuid4().hex}.webp"
    folder = os.path.join(current_app.static_folder, 'uploads', 'covers')
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, nombre_archivo)

    # Convertir a RGB si viene en otro formato (ej: PNG RGBA o Paleta) para guardar en WEBP
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    img.thumbnail((800, 800))
    img.save(path, 'WEBP', quality=85)

    return f"uploads/covers/{nombre_archivo}"

PAISES_DISCOGS_MAP = {
    # Norteamérica y Caribe
    'UNITED STATES': 'Estados Unidos',
    'USA': 'Estados Unidos',
    'US': 'Estados Unidos',
    'AMERICAN': 'Estados Unidos',
    'CANADA': 'Canadá',
    'CANADIAN': 'Canadá',
    'MEXICO': 'México',
    'MEXICAN': 'México',

    # Europa Central y Occidental
    'UNITED KINGDOM': 'Reino Unido',
    'GREAT BRITAIN': 'Reino Unido',
    'ENGLAND': 'Reino Unido',
    'SCOTLAND': 'Reino Unido',
    'WALES': 'Reino Unido',
    'BRITISH': 'Reino Unido',
    'ENGLISH': 'Reino Unido',
    'UK': 'Reino Unido',
    'GERMANY': 'Alemania',
    'WEST GERMANY': 'Alemania',
    'GERMAN': 'Alemania',
    'THE NETHERLANDS': 'Holanda',
    'NETHERLANDS': 'Holanda',
    'HOLLAND': 'Holanda',
    'DUTCH': 'Holanda',
    'BELGIUM': 'Bélgica',
    'BELGIAN': 'Bélgica',
    'FRANCE': 'Francia',
    'FRENCH': 'Francia',
    'SPAIN': 'España',
    'SPANISH': 'España',
    'ITALY': 'Italia',
    'ITALIAN': 'Italia',
    'SWITZERLAND': 'Suiza',
    'SWISS': 'Suiza',
    'AUSTRIA': 'Austria',
    'AUSTRIAN': 'Austria',

    # Escandinavia
    'SWEDEN': 'Suecia',
    'SWEDISH': 'Suecia',
    'NORWAY': 'Noruega',
    'NORWEGIAN': 'Noruega',
    'FINLAND': 'Finlandia',
    'FINNISH': 'Finlandia',
    'DENMARK': 'Dinarmarca',  # Mantiene la ortografía de tu DB
    'DANISH': 'Dinarmarca',

    # Europa del Este
    'POLAND': 'Polonia',
    'POLISH': 'Polonia',
    'RUSSIAN FEDERATION': 'Rusia',
    'RUSSIA': 'Rusia',
    'RUSSIAN': 'Rusia',
    'CZECH REPUBLIC': 'República Checa',
    'CZECHIA': 'República Checa',
    'CZECH': 'República Checa',
    'SLOVAKIA': 'Eslovaquia',
    'HUNGARY': 'Hungría',
    'HUNGARIAN': 'Hungría',
    'GREECE': 'Grecia',
    'GREEK': 'Grecia',
    'ROMANIA': 'Rumania',
    'ROMANIAN': 'Rumania',
    'UKRAINE': 'Ucrania',
    'UKRAINIAN': 'Ucrania',

    # Sudamérica
    'ARGENTINA': 'Argentina',
    'ARGENTINIAN': 'Argentina',
    'BRAZIL': 'Brasil',
    'BRAZILIAN': 'Brasil',
    'CHILE': 'Chile',
    'CHILEAN': 'Chile',
    'PERU': 'Perú',
    'PERUVIAN': 'Perú',
    'COLOMBIA': 'Colombia',
    'COLOMBIAN': 'Colombia',
    'URUGUAY': 'Uruguay',

    # Asia y Oceanía
    'JAPÓN': 'Japón',
    'JAPAN': 'Japón',
    'JAPANESE': 'Japón',
    'AUSTRALIA': 'Australia',
    'AUSTRALIAN': 'Australia',
    'NEW ZEALAND': 'Nueva Zelanda',
}


def obtener_pais_id(texto_o_pais):
    if not texto_o_pais:
        return None

    try:
        # Cache de países en DB
        paises_db = {p.nombre.strip().upper(): p.id for p in Pais.query.all()}

        # 1. Limpiar marcado de Discogs [b], [a=...], etc.
        texto_limpio = re.sub(r'\[.*?\]', ' ', str(texto_o_pais))
        texto_upper = texto_limpio.upper()

        # 2. Coincidencia directa exacta
        if texto_upper in PAISES_DISCOGS_MAP:
            nombre_bd = PAISES_DISCOGS_MAP[texto_upper].upper()
            if nombre_bd in paises_db:
                return paises_db[nombre_bd]

        # 3. Escaneo por orden de longitud de clave
        claves_ordenadas = sorted(PAISES_DISCOGS_MAP.keys(), key=len, reverse=True)
        for clave_discogs in claves_ordenadas:
            patron = rf'\b{re.escape(clave_discogs)}\b'
            if re.search(patron, texto_upper):
                nombre_traducido = PAISES_DISCOGS_MAP[clave_discogs].upper()
                if nombre_traducido in paises_db:
                    return paises_db[nombre_traducido]

        # 4. Fallback: buscar directamente el nombre del país en español dentro del texto
        for nombre_pais, id_pais in paises_db.items():
            if re.search(rf'\b{re.escape(nombre_pais)}\b', texto_upper):
                return id_pais

    except Exception as e:
        print(f"Error en obtener_pais_id: {e}")

    return None


def obtener_pais_desde_releases(artist_object, client_discogs):
    try:
        releases = artist_object.releases
        if releases and len(releases) > 0:
            for rel in releases[:3]:  # Evaluamos los primeros 3 lanzamientos
                release_detail = client_discogs.release(rel.id)
                if hasattr(release_detail, 'country') and release_detail.country:
                    pais_id = obtener_pais_id(release_detail.country)
                    if pais_id:
                        return pais_id
    except Exception:
        pass
    return None