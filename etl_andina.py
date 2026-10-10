"""
ETL reproducible — Distribuidora Andina S.A.S.
Python 3.10+; PostgreSQL 16.

Uso:
  python etl_andina.py datos/ventas_2026-03_lote1.csv
  python etl_andina.py datos/ventas_2026-03_lote2.csv

Decisiones de negocio documentadas en bitacora_decisiones.md.
"""
import json
import re
import sys
import unicodedata
from datetime import datetime, date, time
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

DATOS = Path(__file__).resolve().parent / "datos"
DB_URL = "postgresql+psycopg2://andina:andina@localhost:5432/andina_dw"
FESTIVOS = {date(2026, 3, 23)}
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
         "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def quitar_tildes(valor):
    return "".join(c for c in unicodedata.normalize("NFD", str(valor))
                   if unicodedata.category(c) != "Mn")


def normalizar_codigo(valor):
    return str(valor or "").strip().upper()


def numero(valor):
    """Convierte precios en formatos 5200, '3.400', '$ 4.100' y números."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return float("nan")
    s = str(valor).strip().replace("$", "").replace(" ", "")
    if not s:
        return float("nan")
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    elif "." in s and s.split(".")[-1].isdigit() and len(s.split(".")[-1]) == 3:
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return float("nan")


def extraer_tiendas():
    ruta = DATOS / "tiendas.csv"
    # El maestro exportado desde Excel utiliza ; y UTF-8.
    return pd.read_csv(ruta, sep=";", encoding="utf-8-sig", dtype=str,
                       keep_default_na=False)


def extraer_productos():
    with (DATOS / "productos.json").open(encoding="utf-8") as archivo:
        contenido = json.load(archivo)
    productos = pd.json_normalize(contenido["productos"], sep="_")
    return productos


def extraer_ventas(ruta):
    # Texto conserva la evidencia cruda; las conversiones se hacen explícitamente.
    return pd.read_csv(ruta, dtype=str, keep_default_na=False,
                       encoding="utf-8-sig")


def perfilar(df, nombre):
    print(f"\n--- Perfil: {nombre} ---")
    print(f"Filas: {len(df)} | Columnas: {len(df.columns)}")
    print("Nulos/vacíos por columna:")
    print(df.replace(r"^\s*$", pd.NA, regex=True).isna().sum().to_string())
    print(f"Duplicados exactos adicionales: {int(df.duplicated().sum())}")
    for col in ("cod_tienda", "medio_pago"):
        if col in df.columns:
            valores = df[col].astype(str).str.strip().replace("", pd.NA).dropna()
            print(f"Valores distintos de {col}: {valores.nunique()}")
            print(valores.value_counts().to_string())
    if "fecha" in df.columns:
        fechas = df["fecha"].astype(str).str.strip()
        print("Formatos de fecha:")
        print(pd.Series({
            "AAAA-MM-DD": fechas.str.fullmatch(r"\d{4}-\d{2}-\d{2}").sum(),
            "DD/MM/AAAA": fechas.str.fullmatch(r"\d{2}/\d{2}/\d{4}").sum(),
            "otros": (~(fechas.str.fullmatch(r"\d{4}-\d{2}-\d{2}") |
                        fechas.str.fullmatch(r"\d{2}/\d{2}/\d{4}"))).sum()
        }).to_string())


def transformar_tiendas(df):
    tiendas = df.copy()
    for c in ["cod_tienda", "nombre_tienda", "ciudad", "departamento", "administrador"]:
        tiendas[c] = tiendas[c].astype(str).str.strip()
    tiendas["cod_tienda"] = tiendas["cod_tienda"].map(normalizar_codigo)
    tiendas["ciudad"] = tiendas["ciudad"].map(
        lambda x: {"BOGOTA": "Bogotá", "BOGOTA D.C.": "Bogotá D.C.",
                   "MEDELLIN": "Medellín"}.get(quitar_tildes(x).upper(), x.title()))
    tiendas["departamento"] = tiendas["departamento"].str.title()
    tiendas["activa"] = tiendas["activa"].str.strip().str.upper().isin(["S", "SI", "1", "TRUE"])
    tiendas["fecha_apertura"] = pd.to_datetime(tiendas["fecha_apertura"], format="%Y-%m-%d",
                                                errors="coerce").dt.date
    # El duplicado T05 tiene la misma información de negocio; mantener una sola dimensión.
    tiendas = tiendas.drop_duplicates(subset=["cod_tienda"], keep="first")
    return tiendas


def transformar_productos(df):
    p = df.copy()
    p["sku"] = p["sku"].astype(str).str.strip().str.upper()
    p["nombre"] = p["nombre"].astype(str).str.strip()
    p["categoria"] = p["categoria"].fillna("").astype(str).str.strip()
    p.loc[p["categoria"].eq(""), "categoria"] = "Sin categoría"
    p["marca"] = p["marca"].fillna("").astype(str).str.strip()
    p["precio_lista"] = p["precio_lista"].map(numero)
    p["activo"] = p["activo"].astype(str).str.lower().eq("true")
    p["proveedor_nit"] = p.get("proveedor_nit", pd.Series("", index=p.index)).fillna("").astype(str)
    p["proveedor_razon_social"] = p.get(
        "proveedor_razon_social", pd.Series("", index=p.index)).fillna("").astype(str)
    return p.drop_duplicates(subset=["sku"], keep="first")


def parsear_fecha(valor):
    valor = str(valor).strip()
    for formato in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(valor, formato).date()
        except ValueError:
            pass
    return None


def normalizar_pago(valor):
    k = quitar_tildes(str(valor).strip()).upper()
    mapa = {
        "EFECTIVO": "Efectivo",
        "TD": "Tarjeta Débito", "DEBITO": "Tarjeta Débito",
        "TARJETA DEBITO": "Tarjeta Débito",
        "TC": "Tarjeta Crédito", "CREDITO": "Tarjeta Crédito",
        "TARJETA CREDITO": "Tarjeta Crédito",
        "TRANSFERENCIA": "Transferencia", "NEQUI": "Transferencia",
    }
    return mapa.get(k)


def transformar_ventas(df, productos, lote):
    original = df.copy().fillna("")
    original["_fila_origen"] = range(2, len(original) + 2)
    rechazos = []
    aceptadas = []
    vistos = set()
    pmap = productos.set_index("sku").to_dict(orient="index")

    for _, fila in original.iterrows():
        registro = {k: (None if pd.isna(v) else v) for k, v in fila.items()
                    if k != "_fila_origen"}
        fila_origen = int(fila["_fila_origen"])
        firma = json.dumps(registro, ensure_ascii=False, sort_keys=True)
        if firma in vistos:
            rechazos.append({**registro, "motivo": "DUPLICADO_EXACTO",
                             "_fila_origen": fila_origen})
            continue
        vistos.add(firma)

        transaccion = str(fila["id_transaccion"]).strip()
        sku = normalizar_codigo(fila["sku"])
        tienda = normalizar_codigo(fila["cod_tienda"])
        fecha = parsear_fecha(fila["fecha"])
        try:
            cantidad = float(str(fila["cantidad"]).strip())
        except (ValueError, TypeError):
            cantidad = float("nan")
        descuento_raw = numero(fila["descuento"])
        descuento = descuento_raw / 100 if descuento_raw > 1 else descuento_raw
        motivo = None

        if not re.fullmatch(r"V\d{4}-\d{6}", transaccion):
            motivo = "ID_TRANSACCION_INVALIDO"
        elif fecha is None:
            motivo = "FECHA_INVALIDA"
        elif fecha.year != 2026 or fecha.month != 3:
            motivo = "FECHA_FUERA_DE_MARZO"
        elif not pd.notna(cantidad):
            motivo = "CANTIDAD_INVALIDA"
        elif cantidad == 0:
            motivo = "CANTIDAD_CERO"
        elif abs(cantidad) > 100:
            motivo = "CANTIDAD_ATIPICA_CUARENTENA"
        elif str(fila["vendedor"]).strip().upper() == "TEST":
            motivo = "VENDEDOR_TEST"
        elif sku not in pmap:
            motivo = "SKU_NO_CATALOGADO"
        elif not pd.notna(descuento) or descuento < 0 or descuento > 1:
            motivo = "DESCUENTO_INVALIDO"

        precio = numero(fila["precio_unitario"])
        precio_imputado = False
        if motivo is None and (not pd.notna(precio) or precio <= 0):
            precio_catalogo = numero(pmap[sku].get("precio_lista"))
            if not str(fila["precio_unitario"]).strip() and pd.notna(precio_catalogo) and precio_catalogo > 0:
                precio = precio_catalogo
                precio_imputado = True
            else:
                motivo = "PRECIO_INVALIDO"

        pago = normalizar_pago(fila["medio_pago"])
        if motivo is None and pago is None:
            motivo = "MEDIO_PAGO_NO_RECONOCIDO"

        if motivo:
            rechazos.append({**registro, "motivo": motivo, "_fila_origen": fila_origen})
            continue

        prod = pmap[sku]
        bruto = round(cantidad * precio, 2)
        valor_descuento = round(bruto * descuento, 2)
        aceptadas.append({
            "id_transaccion": transaccion,
            "fecha": fecha,
            "fecha_key": int(fecha.strftime("%Y%m%d")),
            "hora": str(fila["hora"]).strip(),
            "cod_tienda": tienda,
            "sku": sku,
            "cantidad": cantidad,
            "precio_unitario": round(precio, 2),
            "descuento_pct": descuento,
            "medio_pago": pago,
            "vendedor": str(fila["vendedor"]).strip(),
            "valor_bruto": bruto,
            "valor_descuento": valor_descuento,
            "valor_neto": round(bruto - valor_descuento, 2),
            "es_devolucion": cantidad < 0,
            "precio_imputado": precio_imputado,
            "lote_origen": lote,
            "fila_origen": fila_origen,
        })

    ventas = pd.DataFrame(aceptadas)
    columnas_rechazo = list(original.columns) + ["motivo"]
    rechazo_df = pd.DataFrame(rechazos)
    if rechazo_df.empty:
        rechazo_df = pd.DataFrame(columns=columnas_rechazo)
    return ventas, rechazo_df


def construir_fechas(fechas):
    resultado = []
    for f in sorted(set(fechas)):
        resultado.append({
            "fecha_key": int(f.strftime("%Y%m%d")),
            "fecha": f,
            "anio": f.year,
            "mes": f.month,
            "nombre_mes": MESES[f.month - 1],
            "dia": f.day,
            "dia_semana": f.isoweekday(),
            "nombre_dia": DIAS[f.weekday()],
            "semana_iso": f.isocalendar().week,
            "quincena": 1 if f.day <= 15 else 2,
            "es_fin_semana": f.weekday() >= 5,
            "es_festivo": f in FESTIVOS,
        })
    return resultado


def cargar(ventas, rechazos, tiendas, productos, lote, filas_leidas, inicio):
    engine = create_engine(DB_URL, future=True)
    fin = datetime.now()
    with engine.begin() as con:
        # Modelo y vistas se mantienen en el archivo SQL entregado.
        ddl = (Path(__file__).resolve().parent / "modelo_estrella.sql").read_text(encoding="utf-8")
        con.exec_driver_sql(ddl)

        for r in tiendas.to_dict(orient="records"):
            con.execute(text("""
                INSERT INTO dim_tienda
                    (cod_tienda,nombre_tienda,ciudad,departamento,administrador,fecha_apertura,activa,es_provisional)
                VALUES (:cod_tienda,:nombre_tienda,:ciudad,:departamento,:administrador,:fecha_apertura,:activa,FALSE)
                ON CONFLICT (cod_tienda) DO UPDATE SET
                    nombre_tienda=EXCLUDED.nombre_tienda, ciudad=EXCLUDED.ciudad,
                    departamento=EXCLUDED.departamento, administrador=EXCLUDED.administrador,
                    fecha_apertura=EXCLUDED.fecha_apertura, activa=EXCLUDED.activa
            """), r)

        # T12 se conserva con datos desconocidos explícitos; nunca se inventa un administrador.
        codigos = set(tiendas["cod_tienda"])
        codigos_en_ventas = set(ventas["cod_tienda"]) if not ventas.empty else set()
        for cod in sorted(codigos_en_ventas - codigos):
            con.execute(text("""
                INSERT INTO dim_tienda
                    (cod_tienda,nombre_tienda,ciudad,departamento,administrador,activa,es_provisional)
                VALUES (:cod,:nombre,'Desconocida','Desconocido','Pendiente de registro',TRUE,TRUE)
                ON CONFLICT (cod_tienda) DO NOTHING
            """), {"cod": cod, "nombre": f"Tienda provisional {cod}"})

        for r in productos.to_dict(orient="records"):
            con.execute(text("""
                INSERT INTO dim_producto
                    (sku,nombre,categoria,marca,precio_lista,activo,proveedor_nit,proveedor_razon_social)
                VALUES (:sku,:nombre,:categoria,:marca,:precio_lista,:activo,:proveedor_nit,:proveedor_razon_social)
                ON CONFLICT (sku) DO UPDATE SET
                    nombre=EXCLUDED.nombre,categoria=EXCLUDED.categoria,marca=EXCLUDED.marca,
                    precio_lista=EXCLUDED.precio_lista,activo=EXCLUDED.activo,
                    proveedor_nit=EXCLUDED.proveedor_nit,
                    proveedor_razon_social=EXCLUDED.proveedor_razon_social
            """), {**r, "precio_lista": None if pd.isna(r["precio_lista"]) else r["precio_lista"]})

        pagos = ["Efectivo", "Tarjeta Débito", "Tarjeta Crédito", "Transferencia"]
        for pago in pagos:
            con.execute(text("""
                INSERT INTO dim_medio_pago(medio_pago) VALUES (:pago)
                ON CONFLICT (medio_pago) DO NOTHING
            """), {"pago": pago})

        if not ventas.empty:
            fechas = construir_fechas(ventas["fecha"].tolist())
            for r in fechas:
                con.execute(text("""
                    INSERT INTO dim_fecha
                    (fecha_key,fecha,anio,mes,nombre_mes,dia,dia_semana,nombre_dia,
                     semana_iso,quincena,es_fin_semana,es_festivo)
                    VALUES (:fecha_key,:fecha,:anio,:mes,:nombre_mes,:dia,:dia_semana,:nombre_dia,
                            :semana_iso,:quincena,:es_fin_semana,:es_festivo)
                    ON CONFLICT (fecha_key) DO UPDATE SET
                      es_festivo=EXCLUDED.es_festivo
                """), r)

            stg = ventas.copy()
            stg.to_sql("stg_ventas", con, if_exists="replace", index=False, method="multi",
                       chunksize=500)
            # Conteo previo para informar insert/update/sin cambio de forma determinista.
            existentes = {}
            ids = stg["id_transaccion"].tolist()
            for start in range(0, len(ids), 500):
                chunk = ids[start:start+500]
                rows = con.execute(text("""
                    SELECT f.id_transaccion, d.fecha, t.cod_tienda, p.sku, mp.medio_pago,
                           f.hora, f.vendedor, f.cantidad, f.precio_unitario, f.descuento_pct,
                           f.valor_bruto, f.valor_descuento, f.valor_neto, f.es_devolucion,
                           f.precio_imputado
                    FROM fact_ventas f
                    JOIN dim_fecha d ON d.fecha_key=f.fecha_key
                    JOIN dim_tienda t ON t.tienda_key=f.tienda_key
                    JOIN dim_producto p ON p.producto_key=f.producto_key
                    JOIN dim_medio_pago mp ON mp.medio_pago_key=f.medio_pago_key
                    WHERE f.id_transaccion = ANY(:ids)
                """), {"ids": chunk}).mappings()
                existentes.update({x["id_transaccion"]: dict(x) for x in rows})

            insertadas = actualizadas = sin_cambio = 0
            for r in ventas.to_dict(orient="records"):
                anterior = existentes.get(r["id_transaccion"])
                if anterior is None:
                    insertadas += 1
                else:
                    compara = {
                        "fecha": r["fecha"], "cod_tienda": r["cod_tienda"], "sku": r["sku"],
                        "medio_pago": r["medio_pago"], "hora": r["hora"], "vendedor": r["vendedor"],
                        "cantidad": r["cantidad"], "precio_unitario": r["precio_unitario"],
                        "descuento_pct": r["descuento_pct"], "valor_bruto": r["valor_bruto"],
                        "valor_descuento": r["valor_descuento"], "valor_neto": r["valor_neto"],
                        "es_devolucion": r["es_devolucion"], "precio_imputado": r["precio_imputado"]
                    }
                    iguales = True
                    for k, v in compara.items():
                        av = anterior[k]
                        if isinstance(v, float):
                            if av is None or abs(float(av) - v) > 0.00001:
                                iguales = False
                        elif av != v:
                            iguales = False
                    if iguales:
                        sin_cambio += 1
                    else:
                        actualizadas += 1

            con.execute(text("""
                INSERT INTO fact_ventas
                (id_transaccion,fecha_key,tienda_key,producto_key,medio_pago_key,hora,vendedor,
                 cantidad,precio_unitario,descuento_pct,valor_bruto,valor_descuento,valor_neto,
                 es_devolucion,precio_imputado,lote_origen,actualizado_en)
                SELECT s.id_transaccion,s.fecha_key,t.tienda_key,p.producto_key,m.medio_pago_key,
                       s.hora::time,s.vendedor,s.cantidad,s.precio_unitario,s.descuento_pct,
                       s.valor_bruto,s.valor_descuento,s.valor_neto,s.es_devolucion,s.precio_imputado,
                       s.lote_origen,now()
                FROM stg_ventas s
                JOIN dim_tienda t ON t.cod_tienda=s.cod_tienda
                JOIN dim_producto p ON p.sku=s.sku
                JOIN dim_medio_pago m ON m.medio_pago=s.medio_pago
                ON CONFLICT (id_transaccion) DO UPDATE SET
                    fecha_key=EXCLUDED.fecha_key,tienda_key=EXCLUDED.tienda_key,
                    producto_key=EXCLUDED.producto_key,medio_pago_key=EXCLUDED.medio_pago_key,
                    hora=EXCLUDED.hora,vendedor=EXCLUDED.vendedor,cantidad=EXCLUDED.cantidad,
                    precio_unitario=EXCLUDED.precio_unitario,descuento_pct=EXCLUDED.descuento_pct,
                    valor_bruto=EXCLUDED.valor_bruto,valor_descuento=EXCLUDED.valor_descuento,
                    valor_neto=EXCLUDED.valor_neto,es_devolucion=EXCLUDED.es_devolucion,
                    precio_imputado=EXCLUDED.precio_imputado,lote_origen=EXCLUDED.lote_origen,
                    actualizado_en=now()
                WHERE (fact_ventas.fecha_key,fact_ventas.tienda_key,fact_ventas.producto_key,
                       fact_ventas.medio_pago_key,fact_ventas.hora,fact_ventas.vendedor,
                       fact_ventas.cantidad,fact_ventas.precio_unitario,fact_ventas.descuento_pct,
                       fact_ventas.valor_bruto,fact_ventas.valor_descuento,fact_ventas.valor_neto,
                       fact_ventas.es_devolucion,fact_ventas.precio_imputado)
                  IS DISTINCT FROM
                      (EXCLUDED.fecha_key,EXCLUDED.tienda_key,EXCLUDED.producto_key,
                       EXCLUDED.medio_pago_key,EXCLUDED.hora,EXCLUDED.vendedor,
                       EXCLUDED.cantidad,EXCLUDED.precio_unitario,EXCLUDED.descuento_pct,
                       EXCLUDED.valor_bruto,EXCLUDED.valor_descuento,EXCLUDED.valor_neto,
                       EXCLUDED.es_devolucion,EXCLUDED.precio_imputado)
            """))

        for r in rechazos.to_dict(orient="records"):
            fila_origen = r.get("_fila_origen")
            motivo = r.get("motivo", "NO_ESPECIFICADO")
            original = {k: v for k, v in r.items() if k not in ("motivo", "_fila_origen")}
            con.execute(text("""
                INSERT INTO etl_rechazos(lote,fila_origen,id_transaccion,motivo,registro)
                VALUES (:lote,:fila_origen,:id_transaccion,:motivo,CAST(:registro AS JSONB))
                ON CONFLICT (lote,fila_origen,motivo) WHERE fila_origen IS NOT NULL DO NOTHING
            """), {"lote": lote, "fila_origen": fila_origen,
                   "id_transaccion": original.get("id_transaccion") or None,
                   "motivo": motivo, "registro": json.dumps(original, ensure_ascii=False, default=str)})

        con.execute(text("""
            INSERT INTO etl_log
            (lote,inicio,fin,filas_leidas,filas_rechazadas,filas_insertadas,filas_actualizadas,filas_sin_cambio)
            VALUES (:lote,:inicio,:fin,:leidas,:rechazadas,:insertadas,:actualizadas,:sin_cambio)
        """), {"lote": lote, "inicio": inicio, "fin": fin, "leidas": filas_leidas,
               "rechazadas": len(rechazos), "insertadas": locals().get("insertadas", 0),
               "actualizadas": locals().get("actualizadas", 0),
               "sin_cambio": locals().get("sin_cambio", 0)})

        con.execute(text("DROP TABLE IF EXISTS stg_ventas"))
    engine.dispose()


def main(ruta):
    inicio = datetime.now()
    ruta = Path(ruta)
    lote = ruta.stem
    if not ruta.is_absolute():
        ruta = Path(__file__).resolve().parent / ruta
    if not ruta.exists():
        raise FileNotFoundError(f"No existe el archivo: {ruta}")

    tiendas = transformar_tiendas(extraer_tiendas())
    productos = transformar_productos(extraer_productos())
    crudo = extraer_ventas(ruta)
    perfilar(crudo, lote)
    ventas, rechazos = transformar_ventas(crudo.copy(), productos, lote)

    assert len(ventas) + len(rechazos) == len(crudo), (
        f"Cuadre incorrecto: leídas={len(crudo)}, cargadas={len(ventas)}, rechazadas={len(rechazos)}"
    )
    cargar(ventas, rechazos, tiendas, productos, lote, len(crudo), inicio)
    print(f"\n{lote}: leídas {len(crudo)}, aceptadas {len(ventas)}, "
          f"rechazadas {len(rechazos)}")
    if not rechazos.empty:
        print("Rechazos por motivo:")
        print(rechazos["motivo"].value_counts().to_string())


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(DATOS / "ventas_2026-03_lote1.csv"))
