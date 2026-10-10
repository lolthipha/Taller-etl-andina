"""
Taller Guiado ETL - Parte 2: Leer la bodega
Plantilla para estudiantes

Regla de esta parte: NO se leen los CSV. Todo sale de andina_dw,
la bodega que ustedes construyeron en la Parte 1.
"""
import pandas as pd
from sqlalchemy import create_engine

DB_URL = "postgresql+psycopg2://andina:andina@localhost:5432/andina_dw"
engine = create_engine(DB_URL)


def leer(sql):
    """Ejecuta una consulta contra la bodega y devuelve un DataFrame."""
    return pd.read_sql(sql, engine)


# ------------------------------------------------------------------ 1. EXTRACT desde la bodega
# TODO P1: lean la vista vw_ventas (o armen el JOIN de la estrella ustedes mismos).
ventas = None

# ------------------------------------------------------------------ 2. Preguntas de negocio
# TODO A1: venta neta por semana ISO. ¿Todas las semanas son comparables?
# TODO A2: promedio de venta neta por DÍA para días hábiles, fines de semana y el festivo del 23.
# TODO A3: participación de cada categoría en el neto (%).
# TODO A4: top 5 productos por venta neta.
# TODO A5: participación de cada medio de pago.
# TODO A6: tasa de devolución por tienda = valor devuelto / valor vendido.

# ------------------------------------------------------------------ 3. Liquidación de comisiones
# Reglas (ver guía):
#   R1. Base: 2 % del valor neto de la tienda en el mes (las devoluciones restan).
#   R2. Bono: 0,5 % adicional del neto si la tienda alcanza el 100 % de su meta (tabla meta_tienda).
#   R3. Tienda no registrada en el maestro: se calcula pero queda RETENIDA.
#   R4. Lo que está en etl_rechazos no comisiona.
# TODO C1: construyan la liquidación: tienda, administrador, neto, meta, % cumplimiento,
#          comisión base, bono, total y estado (Pagar / Retenida).
# TODO C2: exporten la liquidación a liquidacion_marzo.csv para la gerencia.

# ------------------------------------------------------------------ 4. ¿Y si hubieran usado los datos crudos?
# TODO C3: SOLO para esta comparación, lean los dos CSV crudos, sumen cantidad × precio_unitario
#          por tienda (normalizando solo cod_tienda) y calculen la comisión con las mismas reglas.
#          ¿Cuánto se habría pagado de más? ¿Qué tiendas cobrarían un bono que no ganaron?
