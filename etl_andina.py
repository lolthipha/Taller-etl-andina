"""
Taller Guiado ETL - Distribuidora Andina S.A.S.
Plantilla para estudiantes

Integrantes:
    1.
    2.

Uso:
    python etl_andina.py datos/ventas_2026-03_lote1.csv

Reglas del taller:
    - Cada decisión que tome el código (rechazar, corregir, imputar) debe quedar
      registrada en la bitácora de decisiones con su justificación de negocio.
    - Nada se borra en silencio: todo lo que no se carga va a etl_rechazos con un motivo.
    - El script debe poder correrse dos veces sobre el mismo archivo sin cambiar los totales.
"""
import sys, json
from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

DATOS = Path(__file__).resolve().parent / "datos"
DB_URL = "postgresql+psycopg2://andina:andina@localhost:5432/andina_dw"


# =========================================================== 1. EXTRACT
def extraer_tiendas():
    # TODO E1: el archivo viene de un Excel viejo. Ábranlo primero en un editor de texto.
    #          ¿Qué separador usa? ¿Qué pasa si lo leen con la codificación por defecto?
    ...

def extraer_productos():
    # TODO E2: el JSON no es una lista plana. ¿Dónde están los productos?
    #          'proveedor' es un objeto anidado: investiguen pd.json_normalize.
    ...

def extraer_ventas(ruta):
    # TODO E3: lean TODO como texto (dtype=str). ¿Por qué conviene no dejar que pandas adivine los tipos?
    ...


def perfilar(df, nombre):
    """TODO E4: imprimir un perfil rápido de un DataFrame:
    filas, columnas, nulos por columna, duplicados exactos y valores distintos
    de las columnas categóricas (cod_tienda, medio_pago)."""
    ...


# ========================================================= 2. TRANSFORM
def transformar_tiendas(df):
    # TODO T1: limpiar espacios, estandarizar la ciudad y eliminar tiendas repetidas.
    #          Pregunta: ¿qué le pasa a las ventas de una tienda si su fila aparece dos veces
    #          en la dimensión y ustedes hacen un merge?
    ...

def transformar_productos(df):
    # TODO T2: sku en mayúscula, precio_lista a número, categoría faltante.
    ...

def transformar_ventas(df, productos, lote):
    """Devuelve (ventas_limpias, rechazos).
    rechazos es un DataFrame con las filas originales + una columna 'motivo'."""
    rechazos = []

    # TODO T3: duplicados exactos
    # TODO T4: normalizar cod_tienda y sku
    # TODO T5: fechas -> hay DOS formatos. Usen formatos explícitos (format=...), no inferencia.
    #          Verifiquen: después de convertir, ¿cuántas fechas quedaron fuera de marzo?
    # TODO T6: cantidad y precio a número
    # TODO T7: reglas de rechazo (definan cada una en la bitácora antes de programarla)
    # TODO T8: correcciones: precio nulo, descuento en dos escalas, medio de pago
    # TODO T9: columnas derivadas: es_devolucion, valor_bruto, valor_descuento, valor_neto, fecha_key

    ...


# ============================================================== 3. LOAD
def cargar(ventas, rechazos, tiendas, productos, lote, filas_leidas, inicio):
    engine = create_engine(DB_URL)
    with engine.begin() as con:
        # TODO L1: crear las tablas del modelo estrella (modelo_estrella.sql)
        # TODO L2: cargar dimensiones (dim_fecha, dim_tienda, dim_producto, dim_medio_pago)
        # TODO L3: ¿qué hacen con la tienda T12, que vende pero no está en el maestro?
        # TODO L4: cargar fact_ventas SIN duplicar si el lote se corre dos veces
        #          (pista: tabla staging + INSERT ... ON CONFLICT (id_transaccion) DO UPDATE)
        # TODO L5: guardar rechazos en etl_rechazos y una fila en etl_log
        ...


# ============================================================== MAIN
def main(ruta):
    inicio = datetime.now()
    ruta = Path(ruta)
    lote = ruta.stem

    tiendas = transformar_tiendas(extraer_tiendas())
    productos = transformar_productos(extraer_productos())
    crudo = extraer_ventas(ruta)
    perfilar(crudo, lote)

    ventas, rechazos = transformar_ventas(crudo.copy(), productos, lote)

    # Control de cuadre: ninguna fila se pierde sin explicación
    assert len(ventas) + len(rechazos) == len(crudo), "¡Hay filas que desaparecieron sin quedar en rechazos!"

    cargar(ventas, rechazos, tiendas, productos, lote, len(crudo), inicio)
    print(f"{lote}: leídas {len(crudo)}, cargadas {len(ventas)}, rechazadas {len(rechazos)}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else DATOS / "ventas_2026-03_lote1.csv")
