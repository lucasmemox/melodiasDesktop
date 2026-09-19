import os
import threading
import webview
from flask import send_from_directory
from app import create_app

app = create_app()

# RUTA PARA SERVIR LAS PORTADAS GUARDADAS EN APPDATA
@app.route('/uploads/covers/<filename>')
def custom_uploads(filename):
    """Sirve las portadas directamente desde la carpeta persistente en AppData."""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


class DesktopApi:
    def guardar_archivo(self, contenido, nombre_sugerido):
        """Abre un diálogo nativo de Windows/Linux para guardar archivos (CSV, etc.)."""
        if not webview.windows:
            return False

        window = webview.windows[0]
        resultado = window.create_file_dialog(
            webview.SAVE_DIALOG,
            directory='',
            save_filename=nombre_sugerido,
            file_types=('Archivos CSV (*.csv)', 'Todos los archivos (*.*)')
        )

        if resultado:
            ruta_guardado = resultado if isinstance(resultado, str) else resultado[0]
            with open(ruta_guardado, 'w', encoding='utf-8-sig') as f:
                f.write(contenido)
            return True
        return False


def start_flask():
    """Ejecuta el servidor Flask en segundo plano."""
    app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)


if __name__ == '__main__':
    # 1. Iniciar servidor Flask en hilo secundario
    t = threading.Thread(target=start_flask, daemon=True)
    t.start()

    # 2. Instanciar API nativa para PyWebView
    api = DesktopApi()

    # 3. Lanzar la ventana nativa de escritorio
    webview.create_window(
        title='Melodías Metal Catálogo - Desktop',
        url='http://127.0.0.1:5000',
        width=1280,
        height=800,
        resizable=True,
        js_api=api
    )
    webview.start()