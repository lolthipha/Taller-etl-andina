-- Metas de venta neta de marzo 2026 por tienda (fuente: Gerencia Comercial)
-- Ejecutar una sola vez sobre andina_dw, después de cargar los lotes 1 y 2.
CREATE TABLE IF NOT EXISTS meta_tienda (
    cod_tienda   VARCHAR(10) NOT NULL,
    anio         SMALLINT NOT NULL,
    mes          SMALLINT NOT NULL,
    meta_neta    NUMERIC(14,2) NOT NULL,
    PRIMARY KEY (cod_tienda, anio, mes)
);

INSERT INTO meta_tienda (cod_tienda, anio, mes, meta_neta) VALUES
    ('T01', 2026, 3, 25000000),
    ('T02', 2026, 3, 22000000),
    ('T03', 2026, 3, 24000000),
    ('T04', 2026, 3, 17000000),
    ('T05', 2026, 3, 20000000),
    ('T06', 2026, 3, 15000000),
    ('T07', 2026, 3, 16000000),
    ('T08', 2026, 3, 15000000),
    ('T09', 2026, 3, 13000000),
    ('T10', 2026, 3, 11000000)
ON CONFLICT (cod_tienda, anio, mes) DO UPDATE SET meta_neta = EXCLUDED.meta_neta;
