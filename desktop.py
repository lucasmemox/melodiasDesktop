import os
import sys
import time
import threading
import webview
from app import create_app

# Inicializar la aplicación Flask
app = create_app()


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
            try:
                with open(ruta_guardado, 'w', encoding='utf-8-sig') as f:
                    f.write(contenido)
                return True
            except Exception as e:
                print(f"Error al guardar archivo: {e}")
                return False
        return False


def start_flask():
    """Ejecuta el servidor Flask en segundo plano."""
    app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)


if __name__ == '__main__':
    # 1. Iniciar servidor Flask en hilo secundario
    flask_thread = threading.Thread(target=start_flask, daemon=True)
    flask_thread.start()

    # Pequeño margen para asegurar que el socket local responda antes de abrir la ventana
    time.sleep(0.8)

    # 2. Instanciar API nativa para comunicación JavaScript <-> Python
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