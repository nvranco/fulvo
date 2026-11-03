import csv
from pathlib import Path

# El CSV vive dentro del paquete `fulvo/` y no en `docs/`: así viaja con el
# código al contenedor y al deploy sin depender de una carpeta de documentos.
RUTA_CSV = Path(__file__).resolve().parent / 'datos' / 'complejos.csv'


def leer_filas(ruta: Path = RUTA_CSV) -> list[dict[str, str]]:
    """Lee el CSV de complejos y devuelve una fila por complejo.

    Es el único lugar que sabe dónde está el archivo y cómo se abre. De acá
    parten las dos listas en memoria (zonas y complejos), así los dos
    módulos de rutas no repiten la ruta ni la lectura.

    Se abre con `utf-8-sig` porque Excel guarda el CSV UTF-8 con una marca
    (BOM) al principio. Con `utf-8` a secas esa marca se pegaría al nombre
    de la primera columna y el arranque fallaría con un KeyError.
    """
    with ruta.open(encoding='utf-8-sig', newline='') as archivo:
        return list(csv.DictReader(archivo))
