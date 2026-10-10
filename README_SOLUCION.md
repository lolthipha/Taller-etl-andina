# Taller ETL Andina — guía de ejecución

Esta rama contiene la solución de trabajo del taller. Las reglas marcadas como provisionales deben validarse con el docente antes de entregar.

## 1. Requisitos
- Python 3.10 o superior.
- Docker Desktop en ejecución.
- DBeaver.
- Power BI Desktop.

## 2. Descargar y preparar

En PowerShell:

    git clone https://github.com/lolthipha/Taller-etl-andina.git
    cd Taller-etl-andina
    git checkout solution/etl-andina-completo
    py -3 -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install --upgrade pip
    pip install -r requirements.txt

Si PowerShell bloquea la activación, ejecuta en esa terminal:

    Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
    .\.venv\Scripts\Activate.ps1

## 3. Iniciar PostgreSQL

Desde la raíz del repositorio:

    docker compose up -d
    docker compose ps
    docker compose logs -f postgres

Conexión en DBeaver:
- Host: localhost
- Puerto: 5432
- Base: andina_dw
- Usuario: andina
- Contraseña: andina

## 4. Crear el modelo y ejecutar los lotes

Abre modelo_estrella.sql en DBeaver, selecciona la base andina_dw y ejecuta el script. El ETL también ejecuta este DDL al iniciar la carga.

En PowerShell, desde la raíz del repositorio:

    python etl_andina.py datos/ventas_2026-03_lote1.csv
    python etl_andina.py datos/ventas_2026-03_lote2.csv
    python etl_andina.py datos/ventas_2026-03_lote2.csv

Guarda capturas de las tres salidas. La tercera ejecución prueba la idempotencia.

## 5. Consultas de validación en DBeaver

Ejecuta cada consulta por separado.

Conteo y neto:

    SELECT COUNT(*) AS filas, SUM(valor_neto) AS venta_neta
    FROM fact_ventas;

Hechos sin dimensión tienda:

    SELECT COUNT(*) AS hechos_sin_tienda
    FROM fact_ventas f LEFT JOIN dim_tienda t ON t.tienda_key=f.tienda_key
    WHERE t.tienda_key IS NULL;

Hechos sin dimensión producto:

    SELECT COUNT(*) AS hechos_sin_producto
    FROM fact_ventas f LEFT JOIN dim_producto p ON p.producto_key=f.producto_key
    WHERE p.producto_key IS NULL;

Venta neta por tienda:

    SELECT t.cod_tienda,t.nombre_tienda,SUM(f.valor_neto) AS neto
    FROM fact_ventas f
    JOIN dim_tienda t USING(tienda_key)
    JOIN dim_fecha d USING(fecha_key)
    WHERE d.anio=2026 AND d.mes=3
    GROUP BY t.cod_tienda,t.nombre_tienda ORDER BY t.cod_tienda;

Rechazos por motivo:

    SELECT lote,motivo,COUNT(*) AS filas
    FROM etl_rechazos GROUP BY lote,motivo ORDER BY lote,filas DESC;

Log de ejecuciones:

    SELECT lote,inicio,fin,filas_leidas,filas_rechazadas,
           filas_insertadas,filas_actualizadas,filas_sin_cambio
    FROM etl_log ORDER BY id;

Comprobar que no hay transacciones duplicadas en hechos:

    SELECT id_transaccion,COUNT(*)
    FROM fact_ventas GROUP BY id_transaccion HAVING COUNT(*)>1;

La última consulta debe devolver cero filas. Guarda capturas de las consultas y del log.

## 6. Ejecutar Parte 2

Después de cargar los dos lotes:

    python parte2/analisis_andina.py

El script ejecuta las metas, imprime A1–A6, crea la vista vw_comisiones, genera liquidacion_marzo.csv en la raíz y compara las comisiones con los CSV crudos únicamente en el paso C3.

## 7. Power BI

1. Abre Power BI Desktop.
2. Selecciona Obtener datos → PostgreSQL.
3. Servidor: localhost:5432. Base de datos: andina_dw.
4. Usa Importar y las credenciales locales de PostgreSQL.
5. Importa vw_ventas, vw_comisiones y dim_fecha.
6. Relaciona dim_fecha[fecha] con vw_ventas[fecha] (uno a muchos). Si prefieres las llaves, relaciona fecha_key.
7. Guarda el archivo como Dashboard_Andina_Marzo.pbix.

Medidas DAX mínimas:

    Venta Neta = SUM(vw_ventas[valor_neto])

    Devoluciones =
    CALCULATE(
        [Venta Neta],
        vw_ventas[es_devolucion] = TRUE()
    )

    % Cumplimiento =
    DIVIDE(
        SUM(vw_comisiones[neto]),
        SUM(vw_comisiones[meta_neta])
    )

Medidas recomendadas:

    Total Comisión = SUM(vw_comisiones[total])

    Comisión a Pagar =
    CALCULATE([Total Comisión], vw_comisiones[estado] = "Pagar")

    Comisión Retenida =
    CALCULATE([Total Comisión], vw_comisiones[estado] = "Retenida")

Da formato COP a los importes y porcentaje a Cumplimiento.

### Página 1 — Ventas de marzo
- Tarjetas: Venta Neta y Devoluciones.
- Línea: venta neta por fecha.
- Barras: venta neta por categoría y por tienda.
- Segmentador de ciudad.
- Filtro de página: año 2026, marzo.

### Página 2 — Comisiones
- Tabla: tienda, administrador, neto, meta, cumplimiento, comisión base, bono, total y estado.
- Gráfico de cumplimiento por tienda.
- Tarjetas: comisión a pagar y comisión retenida.
- No ocultes T12: debe aparecer como Retenida.

## 8. Entregables del ZIP
- etl_andina.py completo.
- modelo_estrella.sql.
- bitacora_decisiones.md con cuadres reales y respuestas de cierre.
- parte2/analisis_andina.py y parte2/metas_marzo.sql.
- liquidacion_marzo.csv generado.
- Dashboard_Andina_Marzo.pbix.
- Capturas de validaciones SQL y etl_log.
- Salida de consola de lote 1, primera carga de lote 2 y repetición de lote 2.

## 9. Lista final de comprobación
- Filas leídas = aceptadas + rechazadas en cada lote.
- Los rechazos guardan registro original y motivo.
- No hay hechos sin dimensiones ni IDs duplicados en fact_ventas.
- La repetición del lote 2 no cambia el conteo ni el neto.
- El total de vw_ventas coincide con fact_ventas.
- La vista de comisiones respeta base 2 %, bono 0,5 % al cumplir meta y retención de tienda provisional.
- Se entregan el PBIX y las capturas requeridas.

Validar con el docente el umbral provisional de 100 unidades para cuarentena y con Tesorería la clasificación de Nequi como Transferencia.
