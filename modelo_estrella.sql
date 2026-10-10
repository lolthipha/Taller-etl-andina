-- =====================================================================
-- Bodega de datos Distribuidora Andina - Modelo estrella
-- Plantilla para estudiantes: completen los TODO
-- =====================================================================

-- Dimensión de fecha (entregada completa como referencia de estilo)
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
    es_festivo       BOOLEAN NOT NULL DEFAULT FALSE -- en marzo de 2026: el lunes 23 (San José)
);

-- TODO M1: dim_tienda
--   Llave sustituta (SERIAL) + llave natural cod_tienda (UNIQUE).
--   ¿Qué columna agregarían para distinguir una tienda que creó el ETL porque no estaba en el maestro?

-- TODO M2: dim_producto
--   Incluyan los datos del proveedor. ¿Van aquí o en una dimensión aparte? Justifiquen.

-- TODO M3: dim_medio_pago

-- TODO M4: fact_ventas
--   1. Escriban el GRANO de la tabla en una frase antes de definir columnas.
--   2. ¿Cuál es la llave primaria que permite cargar un lote dos veces sin duplicar?
--   3. Medidas: cantidad, valor_bruto, valor_descuento, valor_neto.
--   4. Banderas de calidad: es_devolucion, precio_imputado, lote_origen.

-- Tablas de control del ETL (entregadas completas)
CREATE TABLE IF NOT EXISTS etl_rechazos (
    id               SERIAL PRIMARY KEY,
    lote             VARCHAR(40) NOT NULL,
    id_transaccion   VARCHAR(20),
    motivo           VARCHAR(80) NOT NULL,
    registro         JSONB NOT NULL,              -- la fila original tal como llegó
    registrado_en    TIMESTAMP NOT NULL DEFAULT now()
);

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
