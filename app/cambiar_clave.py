#!/usr/bin/env python3
# cambiar_clave.py - Script para actualizar contraseña de 'cuervo'

import sys
import os
from werkzeug.security import generate_password_hash

# Agregar la carpeta raíz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Ahora podés importar desde la raíz
from app import create_app, db
from app.models import Usuario

def main():
    app = create_app()

    with app.app_context():
        try:
            user = Usuario.query.filter_by(username='memox').first()

            if user:
                user.password_hash = generate_password_hash('Memox2026+')
                db.session.commit()
                print("✅ ¡Contraseña de 'memox' actualizada con éxito!")
                print(f"   Usuario: {user.username}")
            else:
                print("❌ No se encontró el usuario 'memox'")
                print("   Usuarios disponibles:")
                for u in Usuario.query.all():
                    print(f"   - {u.username}")

        except Exception as e:
            db.session.rollback()
            print(f"❌ Error: {e}")
            sys.exit(1)

if __name__ == "__main__":
    main()