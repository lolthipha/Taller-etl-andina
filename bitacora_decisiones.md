# Bitácora de decisiones ETL — Distribuidora Andina S.A.S.

**Versión de trabajo:** propuesta para validar con el docente y las áreas de Andina.  
**Periodo:** marzo de 2026.

> Los conteos de perfilamiento se calcularon sobre los archivos originales. Los cuadres finales y totales monetarios deben confirmarse ejecutando el ETL y PostgreSQL. No completar cifras finales con estimaciones.

## 1. Perfilamiento antes de transformar

| Hallazgo | Resultado original |
|---|---:|
| Filas del lote 1 | 5.059 |
| Duplicados exactos adicionales en lote 1 | 47 |
| Filas del lote 2 | 1.591 |
| Formatos de fecha | AAAA-MM-DD y DD/MM/AAAA |
| Fechas fuera de marzo en lote 1 | 12 |
| Formas distintas de código de tienda antes de normalizar | 13 |
| Tiendas después de quitar espacios y pasar a mayúsculas | 11 |
| Precios vacíos en lote 1 | 32 |
| Cantidad cero en lote 1 | 14 |
| Cantidades negativas entre ambos lotes | 71 |
| Cantidades superiores a 100 en lote 1 | 3 |
| SKU PRUEBA-* no catalogados en lote 1 | 18 |
| Filas con vendedor TEST | 18 |
| Filas del maestro de tiendas | 12 |
| Registros T05 en el maestro | 2 |
| Transacciones repetidas entre los dos lotes | 86 |
| Repetidas idénticas entre lotes | 80 |
| Repetidas con cambios entre lotes | 6 |

Las 12 fechas fuera de marzo son 10 de febrero y 2 de abril. Las cantidades atípicas identificadas son 1.500, 960 y 1.200 unidades.

## 2. Reglas de decisión

| # | Hallazgo | Decisión | Regla exacta | Justificación | Quién valida |
|---:|---|---|---|---|---|
| 1 | 47 duplicados exactos en lote 1 | Rechazar copia adicional | Conservar la primera copia y registrar las demás como DUPLICADO_EXACTO. | Evitar sumar dos veces una línea POS. | Finanzas y POS |
| 2 | Códigos con espacios o minúsculas | Corregir | Quitar espacios externos y usar mayúsculas antes de unir con dimensiones. | Evitar fragmentar una misma tienda o producto. | Operaciones |
| 3 | Fechas en dos formatos | Corregir | Parsear explícitamente AAAA-MM-DD y DD/MM/AAAA. No usar mixed ni dayfirst global. | Evitar interpretar mal día y mes. | POS |
| 4 | 12 transacciones fuera de marzo | Rechazar | Si el año no es 2026 o el mes no es marzo: FECHA_FUERA_DE_MARZO. | Las metas corresponden a marzo. | Finanzas |
| 5 | Cantidad cero | Rechazar | cantidad == 0 produce CANTIDAD_CERO. | No representa una venta ni devolución válida. | Finanzas |
| 6 | Cantidad negativa | Aceptar como devolución | es_devolucion = cantidad < 0; importes conservan el signo. | Las devoluciones deben restar de la venta neta y comisión. | Finanzas e inventario |
| 7 | Cantidades extremas | Cuarentena | abs(cantidad) > 100 produce CANTIDAD_ATIPICA_CUARENTENA. | No asumir que es real ni borrarla. El umbral 100 es provisional y requiere aprobación. | Gerencia comercial |
| 8 | 18 filas de prueba | Rechazar | vendedor TEST produce VENDEDOR_TEST. | No son transacciones comerciales y no deben comisionar. | POS y Finanzas |
| 9 | SKU no existe en catálogo | Rechazar | SKU_NO_CATALOGADO y guardar fila original en JSONB. | No inventar nombre o categoría de producto. | Compras |
| 10 | 32 precios vacíos | Corregir si es posible | Si el precio está vacío y el catálogo tiene precio positivo, imputar y marcar precio_imputado. Si no, PRECIO_INVALIDO. | Recuperar el valor usando una fuente maestra y dejar evidencia. | Compras y Finanzas |
| 11 | Descuento en escalas 0–1 y 0–100 | Corregir | Valores mayores que 1 se dividen por 100; validar rango final 0–1. | 5 significa 5 %, igual que 0.05. | Comercial |
| 12 | Medios de pago en muchas formas | Corregir | Consolidar en Efectivo, Tarjeta Débito, Tarjeta Crédito y Transferencia. Nequi se agrupa en Transferencia. | La plantilla Excel solicita cuatro categorías; Tesorería debe confirmar esta equivalencia. | Tesorería |
| 13 | T05 duplicada en maestro | Corregir | Conservar una fila por cod_tienda; T05 tiene atributos equivalentes tras limpiar espacios. | Evitar duplicar ventas en el merge. | Operaciones |
| 14 | T12 no aparece en maestro | Aceptar provisionalmente y retener comisión | Crear dimensión con es_provisional=TRUE y datos desconocidos explícitos. | No inventar administrador ni perder ventas. | Gerencia comercial |
| 15 | Transacción repetida con cambios en lote 2 | Actualizar | La versión más reciente sustituye a la anterior si supera las reglas de calidad. | El taller indica que lote 2 incluye correcciones. | POS y Finanzas |
| 16 | Transacción repetida sin cambios | Sin cambio | Upsert condicional con IS DISTINCT FROM. | Garantiza idempotencia. | Datos / DBA |
| 17 | Rechazos al repetir archivo | No duplicar rechazo | Clave única por lote, fila de origen y motivo; ON CONFLICT DO NOTHING. | Repetir el lote no debe aumentar rechazos artificialmente. | Datos / DBA |
| 18 | Categoría vacía en catálogo | Corregir | Asignar Sin categoría. | Hacer visible el dato faltante sin inventar una categoría. | Compras |

### Experimento obligatorio del merge de T05

Si T05 aparece dos veces en el maestro, un merge antes de deduplicar puede duplicar las ventas de esa tienda y aumentar las comisiones. Por eso se elimina el duplicado del maestro antes de cargar la dimensión.

### Regla de transacciones corregidas

Si una transacción vuelve en lote 2 con otra cantidad y supera las reglas de calidad, gana la versión más reciente. Si no cambió ningún atributo de negocio, no se modifica la fila.

## 3. Cuadres tras ejecutar

### Lote 1

| Concepto | Valor |
|---|---:|
| Filas leídas | Pendiente de ejecución |
| Filas aceptadas | Pendiente de ejecución |
| Filas rechazadas | Pendiente de ejecución |
| ¿Leídas = aceptadas + rechazadas? | Debe ser Sí |

### Lote 2, primera ejecución

| Concepto | Valor |
|---|---:|
| Filas leídas | Pendiente de ejecución |
| Filas rechazadas | Pendiente de ejecución |
| Insertadas | Pendiente de ejecución |
| Actualizadas | Pendiente de ejecución |
| Sin cambio | Pendiente de ejecución |

### Lote 2, repetición

| Control | Resultado esperado |
|---|---|
| COUNT(*) en fact_ventas | Igual antes y después |
| SUM(valor_neto) | Igual antes y después |
| Nuevos rechazos del lote | 0 |
| Insertadas | 0 |
| Actualizadas | 0 |
| Sin cambio | Igual al número de filas aceptadas del lote |

## 4. Preguntas de cierre

1. Comparar la suma cruda de cantidad × precio con el neto ETL. Explicar duplicados, fechas fuera de marzo, filas TEST, cantidades extremas, devoluciones, descuentos y precios imputados.
2. Identificar la regla de mayor impacto en comisiones y argumentarla con las cifras reales.
3. Si una tienda confirma una cantidad en cuarentena, documentar la resolución y reingresar la fila con trazabilidad; nunca borrar la evidencia original.
4. Para 500 tiendas y cinco millones de filas diarias, evaluar carga fila por fila, memoria de pandas, staging, particiones, COPY, índices, orquestación y monitoreo.

## 5. Decisiones que requieren aprobación

- El umbral de 100 unidades es una propuesta de taller basada en los tres valores extremos observados; el docente/Andina debe aprobarlo.
- La equivalencia Nequi → Transferencia sigue la plantilla de cuatro categorías y debe validarla Tesorería.
- T12 no tiene administrador ni meta suministrados. No se inventan: la comisión se calcula y queda retenida.
- La liquidación final se considera lista cuando los scripts se ejecutan y los resultados se comprueban en PostgreSQL.
