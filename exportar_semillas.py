# exportar_semillas.py
import json
import sqlite3

DB_ACTUAL = 'melodias_local.db'  # Tu BD actual llena


def exportar_a_json():
  conn = sqlite3.connect(DB_ACTUAL)
  cursor = conn.cursor()

  data = {}
  tablas = ['pais', 'formato', 'genero', 'sello_discografico']

  for tabla in tablas:
    # Obtenemos nombres de columnas
    cursor.execute(f'PRAGMA table_info({tabla});')
    columnas = [col[1] for col in cursor.fetchall()]

    # Obtenemos los registros
    cursor.execute(f'SELECT * FROM {tabla};')
    filas = cursor.fetchall()

    # Convertimos cada fila a un diccionario {columna: valor}
    data[tabla] = [dict(zip(columnas, fila)) for fila in filas]

  with open('app/seeds.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

  print('¡`app/seeds.json` creado exitosamente!')
  conn.close()


if __name__ == '__main__':
  exportar_a_json()