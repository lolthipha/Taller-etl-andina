"""
Parte 2 — Análisis desde PostgreSQL, comisiones y comparación cruda.
Solo C3 lee los CSV; A1-A6 y la liquidación salen de la bodega.
"""
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]
DB_URL = "postgresql+psycopg2://andina:andina@localhost:5432/andina_dw"
engine = create_engine(DB_URL, future=True)
OUT = ROOT / "liquidacion_marzo.csv"


def leer(sql):
    return pd.read_sql(text(sql), engine)


def crear_vista_comisiones():
    with engine.begin() as con:
        con.exec_driver_sql("""
        CREATE OR REPLACE VIEW vw_comisiones AS
        WITH ventas AS (
          SELECT t.cod_tienda,t.nombre_tienda,t.administrador,t.es_provisional,
                 COALESCE(SUM(f.valor_neto),0)::NUMERIC(18,2) AS neto
          FROM dim_tienda t
          LEFT JOIN fact_ventas f ON f.tienda_key=t.tienda_key
          LEFT JOIN dim_fecha d ON d.fecha_key=f.fecha_key
          WHERE d.fecha IS NULL OR (d.anio=2026 AND d.mes=3)
          GROUP BY t.cod_tienda,t.nombre_tienda,t.administrador,t.es_provisional
        )
        SELECT v.cod_tienda,v.nombre_tienda,v.administrador,v.neto,m.meta_neta,
               CASE WHEN m.meta_neta>0 THEN v.neto/m.meta_neta ELSE NULL END AS cumplimiento,
               ROUND(v.neto*0.02,2) AS comision_base,
               CASE WHEN m.meta_neta IS NOT NULL AND v.neto>=m.meta_neta
                    THEN ROUND(v.neto*0.005,2) ELSE 0::NUMERIC END AS bono,
               ROUND(v.neto*0.02,2)+
               CASE WHEN m.meta_neta IS NOT NULL AND v.neto>=m.meta_neta
                    THEN ROUND(v.neto*0.005,2) ELSE 0::NUMERIC END AS total,
               CASE WHEN v.es_provisional OR m.meta_neta IS NULL
                    THEN 'Retenida' ELSE 'Pagar' END AS estado,
               v.es_provisional
        FROM ventas v
        LEFT JOIN meta_tienda m ON m.cod_tienda=v.cod_tienda
          AND m.anio=2026 AND m.mes=3
        """)


def analizar_bodega():
    ventas = leer("SELECT * FROM vw_ventas WHERE anio=2026 AND mes=3")
    if ventas.empty:
        raise RuntimeError("No hay ventas. Ejecute los lotes ETL primero.")
    total_vista = round(float(ventas["valor_neto"].sum()), 2)
    total_fact = float(leer("""
      SELECT COALESCE(SUM(f.valor_neto),0) AS neto
      FROM fact_ventas f JOIN dim_fecha d USING(fecha_key)
      WHERE d.anio=2026 AND d.mes=3
    """).iloc[0]["neto"])
    if abs(total_vista-total_fact) > 0.01:
        raise AssertionError("vw_ventas no cuadra con fact_ventas")
    print("\\nTotal neto validado: $" + format(total_vista, ",.2f") + " COP")

    consultas = {
      "A1 — Venta neta por semana ISO": """
        SELECT anio,semana_iso,MIN(fecha) AS desde,MAX(fecha) AS hasta,
               COUNT(DISTINCT fecha) AS dias_con_ventas,SUM(valor_neto) AS venta_neta
        FROM vw_ventas WHERE anio=2026 AND mes=3
        GROUP BY anio,semana_iso ORDER BY anio,semana_iso
      """,
      "A2 — Promedio por día calendario": """
        WITH dias AS (
          SELECT d.fecha,d.es_fin_semana,d.es_festivo,COALESCE(SUM(f.valor_neto),0) AS neto_dia
          FROM dim_fecha d LEFT JOIN fact_ventas f ON f.fecha_key=d.fecha_key
          WHERE d.anio=2026 AND d.mes=3 GROUP BY d.fecha,d.es_fin_semana,d.es_festivo
        )
        SELECT CASE WHEN es_festivo THEN 'Festivo 23 de marzo'
                    WHEN es_fin_semana THEN 'Fin de semana' ELSE 'Día hábil' END AS tipo_dia,
               COUNT(*) AS dias,SUM(neto_dia) AS neto_total,
               ROUND(AVG(neto_dia),2) AS promedio_neto_por_dia
        FROM dias GROUP BY 1 ORDER BY 1
      """,
      "A3 — Participación por categoría": """
        SELECT categoria,SUM(valor_neto) AS venta_neta,
          ROUND(100.0*SUM(valor_neto)/NULLIF(SUM(SUM(valor_neto)) OVER(),0),2) AS participacion_pct
        FROM vw_ventas WHERE anio=2026 AND mes=3
        GROUP BY categoria ORDER BY venta_neta DESC
      """,
      "A4 — Top 5 productos": """
        SELECT sku,nombre_producto,SUM(valor_neto) AS venta_neta
        FROM vw_ventas WHERE anio=2026 AND mes=3
        GROUP BY sku,nombre_producto ORDER BY venta_neta DESC LIMIT 5
      """,
      "A5 — Participación por medio de pago": """
        SELECT medio_pago,SUM(valor_neto) AS venta_neta,
          ROUND(100.0*SUM(valor_neto)/NULLIF(SUM(SUM(valor_neto)) OVER(),0),2) AS participacion_pct
        FROM vw_ventas WHERE anio=2026 AND mes=3
        GROUP BY medio_pago ORDER BY venta_neta DESC
      """,
      "A6 — Tasa de devolución por tienda": """
        SELECT cod_tienda,nombre_tienda,
          SUM(CASE WHEN cantidad>0 THEN valor_neto ELSE 0 END) AS valor_vendido,
          ABS(SUM(CASE WHEN es_devolucion THEN valor_neto ELSE 0 END)) AS valor_devuelto,
          ROUND(100.0*ABS(SUM(CASE WHEN es_devolucion THEN valor_neto ELSE 0 END))/
            NULLIF(SUM(CASE WHEN cantidad>0 THEN valor_neto ELSE 0 END),0),2) AS tasa_devolucion_pct
        FROM vw_ventas WHERE anio=2026 AND mes=3
        GROUP BY cod_tienda,nombre_tienda ORDER BY tasa_devolucion_pct DESC NULLS LAST
      """
    }
    for titulo, sql in consultas.items():
        print("\\n" + titulo)
        print(leer(sql).to_string(index=False))


def comparar_crudos():
    # Únicamente esta comparación lee los CSV. Se normaliza cod_tienda, como pide la guía.
    piezas = []
    for nombre in ["ventas_2026-03_lote1.csv", "ventas_2026-03_lote2.csv"]:
        df = pd.read_csv(ROOT / "datos" / nombre, dtype=str, keep_default_na=False)
        df["cod_tienda"] = df["cod_tienda"].astype(str).str.strip().str.upper()
        df["cantidad_num"] = pd.to_numeric(df["cantidad"], errors="coerce")
        df["precio_num"] = pd.to_numeric(df["precio_unitario"], errors="coerce")
        df["neto_crudo_csv"] = df["cantidad_num"] * df["precio_num"]
        piezas.append(df)
    raw = pd.concat(piezas, ignore_index=True).groupby("cod_tienda", as_index=False)["neto_crudo_csv"].sum()
    tiendas = leer("SELECT cod_tienda,administrador,es_provisional FROM dim_tienda")
    metas = leer("SELECT cod_tienda,meta_neta FROM meta_tienda WHERE anio=2026 AND mes=3")
    raw = raw.merge(tiendas, on="cod_tienda", how="left").merge(metas, on="cod_tienda", how="left")
    raw["comision_base_cruda"] = (raw["neto_crudo_csv"]*0.02).round(2)
    raw["bono_crudo"] = (
        (raw["meta_neta"].notna()) & (raw["neto_crudo_csv"]>=raw["meta_neta"])
    ) * (raw["neto_crudo_csv"]*0.005).round(2)
    raw["comision_total_cruda"] = raw["comision_base_cruda"] + raw["bono_crudo"]
    raw["estado_crudo"] = raw.apply(
        lambda r: "Retenida" if bool(r["es_provisional"]) or pd.isna(r["meta_neta"]) else "Pagar",
        axis=1)
    etl = leer("SELECT cod_tienda,neto,comision_base,bono,total,estado FROM vw_comisiones")
    comp = etl.merge(raw, on="cod_tienda", how="outer")
    comp["diferencia_crudo_menos_etl"] = (
        comp["comision_total_cruda"].fillna(0)-comp["total"].fillna(0)).round(2)
    print("\\nC3 — Comisión con datos crudos frente a ETL")
    print(comp[["cod_tienda","administrador","neto","neto_crudo_csv","total",
                "comision_total_cruda","diferencia_crudo_menos_etl"]].to_string(index=False))
    pagable_etl = comp.loc[comp["estado"]=="Pagar","total"].sum()
    pagable_crudo = comp.loc[comp["estado_crudo"]=="Pagar","comision_total_cruda"].sum()
    print("Pagable ETL: $" + format(pagable_etl,",.2f"))
    print("Pagable crudo: $" + format(pagable_crudo,",.2f"))
    print("Diferencia crudo menos ETL: $" + format(pagable_crudo-pagable_etl,",.2f"))
    falsas = comp.loc[(comp["bono_crudo"]>0)&(comp["bono"].fillna(0)==0),"cod_tienda"].astype(str).tolist()
    print("Bono crudo sin bono ETL: " + (", ".join(falsas) if falsas else "Ninguna"))


def main():
    ejecutar = (ROOT / "parte2" / "metas_marzo.sql").read_text(encoding="utf-8")
    with engine.begin() as con:
        con.exec_driver_sql(ejecutar)
    crear_vista_comisiones()
    analizar_bodega()
    comisiones = leer("SELECT * FROM vw_comisiones ORDER BY cod_tienda")
    comisiones.to_csv(OUT, index=False, encoding="utf-8-sig", float_format="%.2f")
    print("\\nLiquidación exportada: " + str(OUT))
    comparar_crudos()
    engine.dispose()


if __name__ == "__main__":
    main()
