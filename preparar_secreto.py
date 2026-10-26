"""Ejecutar localmente. No subir el archivo generado al repositorio."""
import json
import os
import argparse
from pathlib import Path
from seguimiento_envia import leer_excel

if os.environ.get('GUIAS_JSON'):
    raise SystemExit('Quita GUIAS_JSON del entorno para leer tu Excel local')
parser = argparse.ArgumentParser()
parser.add_argument('excel', nargs='?', default='guias.xlsx')
args = parser.parse_args()
guias = leer_excel(args.excel)
Path('guias.json').write_text(json.dumps(guias), encoding='utf-8')
print('Se creó guias.json. Copia su contenido al secreto GUIAS_JSON de GitHub.')
