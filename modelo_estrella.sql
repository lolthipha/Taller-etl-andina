-- =====================================================================
-- Bodega de datos Distribuidora Andina S.A.S. — Modelo estrella
-- Ejecutable más de una vez. Parte de la guía del taller, sin borrar datos.
--
-- Grano de fact_ventas:
-- Una fila por id_transaccion único aceptado por las reglas de calidad.
-- La clave natural es id_transaccion; se usa como PK para hacer el ETL idempotente.
--
-- El proveedor queda como atributos de dim_producto porque el catálogo entregado
-- relaciona un único proveedor con cada SKU; no hay requisito de una dimensión
-- independiente de proveedores en las fuentes.
-- =====================================================================

CREATE TABLE IF NOT EXISTS dim_fecha (
    fecha_key        INTEGER PRIMARY KEY,          -- AAAAMMDD, p. ej. 20260323
    fecha            DATE NOT NULL UNIQUE,
    anio             SMALLINT NOT NULL,
    mes              SMALLINT NOT NULL,
    nombre_mes       VARCHAR(12) NOT NULL,
    dia              SMALLINT NOT NULL,
    dia_semana       SMALLINT NOT NULL,            -- 1 = lunes ... 7 = domingo
    nombre_dia       VARCHAR(10) NOT NULL,
    semana_iso       SMALLINT NOT NULL,
    quincena         SMALLINT NOT NULL,
    es_fin_semana    BOOLEAN NOT NULL,
    es_festivo       BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS dim_tienda (
    tienda_key       SERIAL PRIMARY KEY,
    cod_tienda       VARCHAR(10) NOT NULL UNIQUE,  -- llave natural
    nombre_tienda    VARCHAR(100) NOT NULL,
    ciudad           VARCHAR(80) NOT NULL,
    departamento     VARCHAR(80),
    administrador    VARCHAR(100),
    fecha_apertura   DATE,
    activa           BOOLEAN NOT NULL DEFAULT TRUE,
    es_provisional   BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS dim_producto (
    producto_key             SERIAL PRIMARY KEY,
    sku                      VARCHAR(30) NOT NULL UNIQUE, -- llave natural
    nombre                   VARCHAR(150) NOT NULL,
    categoria                VARCHAR(80) NOT NULL,
    marca                    VARCHAR(80),
    precio_lista             NUMERIC(14,2),
    activo                   BOOLEAN NOT NULL DEFAULT TRUE,
    proveedor_nit            VARCHAR(30),
    proveedor_razon_social   VARCHAR(150)
);

CREATE TABLE IF NOT EXISTS dim_medio_pago (
    medio_pago_key   SERIAL PRIMARY KEY,
    medio_pago       VARCHAR(40) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS fact_ventas (
    id_transaccion   VARCHAR(20) PRIMARY KEY,      -- llave natural para upsert
    fecha_key        INTEGER NOT NULL REFERENCES dim_fecha(fecha_key),
    tienda_key       INTEGER NOT NULL REFERENCES dim_tienda(tienda_key),
    producto_key     INTEGER NOT NULL REFERENCES dim_producto(producto_key),
    medio_pago_key   INTEGER NOT NULL REFERENCES dim_medio_pago(medio_pago_key),
    hora             TIME NOT NULL,
    vendedor         VARCHAR(40) NOT NULL,
    cantidad         NUMERIC(12,2) NOT NULL,
    precio_unitario  NUMERIC(14,2) NOT NULL,
    descuento_pct    NUMERIC(7,4) NOT NULL DEFAULT 0
                     CHECK (descuento_pct >= 0 AND descuento_pct <= 1),
    valor_bruto      NUMERIC(18,2) NOT NULL,
    valor_descuento  NUMERIC(18,2) NOT NULL,
    valor_neto       NUMERIC(18,2) NOT NULL,
    es_devolucion    BOOLEAN NOT NULL DEFAULT FALSE,
    precio_imputado  BOOLEAN NOT NULL DEFAULT FALSE,
    lote_origen      VARCHAR(40) NOT NULL,
    actualizado_en   TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_fact_ventas_fecha
    ON fact_ventas (fecha_key);
CREATE INDEX IF NOT EXISTS ix_fact_ventas_tienda_fecha
    ON fact_ventas (tienda_key, fecha_key);
CREATE INDEX IF NOT EXISTS ix_fact_ventas_producto
    ON fact_ventas (producto_key);

-- Nada se descarta en silencio: se conserva el registro original en JSONB.
-- fila_origen permite identificar la misma línea física cuando se vuelve a
-- ejecutar un archivo. Es auxiliar de auditoría, no forma parte del JSON original.
CREATE TABLE IF NOT EXISTS etl_rechazos (
    id               SERIAL PRIMARY KEY,
    lote             VARCHAR(40) NOT NULL,
    fila_origen      INTEGER,
    id_transaccion   VARCHAR(20),
    motivo           VARCHAR(80) NOT NULL,
    registro         JSONB NOT NULL,
    registrado_en    TIMESTAMP NOT NULL DEFAULT now()
);

-- Compatibilidad si ya existía la tabla de la plantilla sin fila_origen.
ALTER TABLE etl_rechazos
    ADD COLUMN IF NOT EXISTS fila_origen INTEGER;

-- Al repetir el mismo archivo, no crece la tabla por la misma línea rechazada.
CREATE UNIQUE INDEX IF NOT EXISTS uq_etl_rechazos_lote_fila_motivo
    ON etl_rechazos (lote, fila_origen, motivo)
    WHERE fila_origen IS NOT NULL;

CREATE TABLE IF NOT EXISTS etl_log (
    id                 SERIAL PRIMARY KEY,
    lote               VARCHAR(40) NOT NULL,
    inicio             TIMESTAMP NOT NULL,
    fin                TIMESTAMP NOT NULL,
    filas_leidas       INTEGER NOT NULL,
    filas_rechazadas   INTEGER NOT NULL,
    filas_insertadas   INTEGER NOT NULL,
    filas_actualizadas INTEGER NOT NULL,
    filas_sin_cambio   INTEGER NOT NULL
);

-- Vista que utilizarán el script de análisis y Power BI.
CREATE OR REPLACE VIEW vw_ventas AS
SELECT
    f.id_transaccion,
    d.fecha,
    d.anio,
    d.mes,
    d.nombre_mes,
    d.dia,
    d.dia_semana,
    d.nombre_dia,
    d.semana_iso,
    d.quincena,
    d.es_fin_semana,
    d.es_festivo,
    t.cod_tienda,
    t.nombre_tienda,
    t.ciudad,
    t.departamento,
    t.administrador,
    t.activa AS tienda_activa,
    t.es_provisional,
    p.sku,
    p.nombre AS nombre_producto,
    p.categoria,
    p.marca,
    p.precio_lista,
    p.activo AS producto_activo,
    p.proveedor_nit,
    p.proveedor_razon_social,
    mp.medio_pago,
    f.hora,
    f.vendedor,
    f.cantidad,
    f.precio_unitario,
    f.descuento_pct,
    f.valor_bruto,
    f.valor_descuento,
    f.valor_neto,
    f.es_devolucion,
    f.precio_imputado,
    f.lote_origen
FROM fact_ventas AS f
JOIN dim_fecha AS d       ON d.fecha_key = f.fecha_key
JOIN dim_tienda AS t      ON t.tienda_key = f.tienda_key
JOIN dim_producto AS p    ON p.producto_key = f.producto_key
JOIN dim_medio_pago AS mp ON mp.medio_pago_key = f.medio_pago_key;
