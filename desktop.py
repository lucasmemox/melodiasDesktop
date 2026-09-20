import os
import sys
import time
import threading
import webbrowser
from app import create_app

# Inicializar la aplicación Flask
app = create_app()


def abrir_navegador():
    """Espera un instante a que Flask levante y abre la aplicación en el navegador predeterminado."""
    time.sleep(1.2)
    webbrowser.open('http://127.0.0.1:5000')


if __name__ == '__main__':
    # 1. Iniciar un hilo secundario para abrir el navegador (Chrome, Edge, Firefox, etc.)
    threading.Thread(target=abrir_navegador, daemon=True).start()

    # 2. Iniciar el servidor local Flask en el hilo principal
    app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)