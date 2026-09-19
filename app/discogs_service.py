import discogs_client, re
from flask import current_app
from app.utils import obtener_pais_id, obtener_pais_desde_releases

def buscar_disco_discogs(query_texto):
    user_agent = current_app.config.get('DISCOGS_USER_AGENT', 'MelodiasMetalCatalog/1.0')
    token = current_app.config.get('DISCOGS_TOKEN')

    d = discogs_client.Client(user_agent, user_token=token)

    digitos = ''.join(filter(str.isdigit, query_texto))

    try:
        if len(digitos) >= 8 and len(digitos) <= 13:
            results = d.search(barcode=digitos, type='release')
            if len(results) == 0:
                results = d.search(query_texto, type='release')
        else:
            results = d.search(query_texto, type='release')

        lista_resultados = []
        contador = 0
        for release in results:
            if contador >= 8:
                break

            sello_nombre = ''
            catno = ''
            if hasattr(release, 'labels') and release.labels:
                sello_nombre = release.labels[0].name
                catno = getattr(release.labels[0], 'catno', '')

            # Extraer los formatos devueltos por Discogs (ej: 'CD', 'Vinyl', 'Cassette')
            formatos_list = []
            if hasattr(release, 'formats') and release.formats:
                for fmt in release.formats:
                    if isinstance(fmt, dict) and 'name' in fmt:
                        formatos_list.append(fmt['name'])
                    elif hasattr(fmt, 'name'):
                        formatos_list.append(fmt.name)

            portada_hd = ''
            if hasattr(release, 'images') and release.images:
                portada_hd = release.images[0].get('resource_url', '')
            if not portada_hd:
                portada_hd = getattr(release, 'thumb', '')

            lista_resultados.append({
                'id': release.id,
                'titulo': release.title,
                'ano': getattr(release, 'year', None),
                'sello': sello_nombre,
                'portada': getattr(release, 'thumb', ''),
                'portada': portada_hd,
                'catno': catno,
                'formatos': formatos_list # Contiene ej: ['CD', 'Album'] o ['Vinyl']
            })
            contador += 1

        return lista_resultados

    except Exception as e:
        print(f"Error parseando resultados de Discogs: {e}")
        return []


def get_discogs_client():
    user_agent = current_app.config.get('DISCOGS_USER_AGENT', 'MelodiasMetalCatalog/1.0')
    token = current_app.config.get('DISCOGS_TOKEN')
    return discogs_client.Client(user_agent, user_token=token)

def buscar_banda_discogs(query_texto):
    """Búsqueda inicial limpia de artistas sin sobrecargar la API."""
    d = get_discogs_client()

    try:
        results = d.search(query_texto, type='artist')
        lista_resultados = []

        for artist in results:
            if len(lista_resultados) >= 8:
                break

            # Obtenemos los atributos básicos que Discogs sí incluye en el resultado de búsqueda
            nombre_original = getattr(artist, 'name', '')

            # Portada/Thumb básico
            portada = getattr(artist, 'thumb', '')
            if 'spacer.gif' in portada:
                portada = ''

            # Extraemos el sufijo de Discogs tipo "(2)" para mostrar como contexto
            match_sufijo = re.search(r'\s*(\(\d+\))$', nombre_original)
            sufijo = match_sufijo.group(1) if match_sufijo else ''

            lista_resultados.append({
                'id': artist.id,
                'nombre_original': nombre_original,
                'portada': portada,
                'perfil_corto': f"Artista de Discogs {sufijo}".strip()
            })

        return lista_resultados

    except Exception as e:
        print(f"--> Error en buscar_banda_discogs ({query_texto}): {e}")
        return []

def obtener_detalle_banda_discogs(artist_id):
    """Obtiene el detalle completo de la banda (país, foto HD, biografía) al seleccionar una."""
    d = get_discogs_client()

    try:
        artist = d.artist(artist_id)
        perfil = getattr(artist, 'profile', '')

        # 1. Resolver país
        country_raw = getattr(artist, 'country', '')
        pais_id = obtener_pais_id(country_raw) if country_raw else None

        if not pais_id and perfil:
            pais_id = obtener_pais_id(perfil)

        if not pais_id:
            pais_id = obtener_pais_desde_releases(artist, d)

        # 2. Resolver imagen de alta calidad
        images = getattr(artist, 'images', [])
        portada_hd = images[0].get('resource_url', '') if images else getattr(artist, 'thumb', '')
        if 'spacer.gif' in portada_hd:
            portada_hd = ''

        nombre_limpio = re.sub(r'\s*\(\d+\)$', '', artist.name)

        return {
            'id': artist.id,
            'nombre_original': artist.name,
            'nombre_limpio': nombre_limpio,
            'perfil': perfil,
            'portada': portada_hd,
            'pais_id': int(pais_id) if pais_id is not None else None,
            'urls': getattr(artist, 'urls', [])
        }

    except Exception as e:
        print(f"--> Error obteniendo detalle de artista {artist_id}: {e}")
        return None