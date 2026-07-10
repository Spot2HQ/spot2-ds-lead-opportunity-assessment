# Diccionario de variables

Este documento describe la granularidad, llaves de unión y unidades de las tablas entregadas.

## Llaves de unión y granularidad

- `lead_id`, `spot_id`, `inquiry_id` y `snapshot_id` son las llaves primarias de sus respectivas tablas.
- `leads`: una fila por lead.
- `spots`: una fila por inmueble.
- `spot_attributes`: una fila por inmueble; relación 1:1 con `spots` mediante `spot_id`.
- `inquiries`: una fila por interacción entre lead e inmueble.
- `market_context`: una fila por `(estado, municipio, corredor, sector, mes)`.
- `availability_snapshot`: una fila por snapshot de disponibilidad de un inmueble en el tiempo.

## Precios

- `price_sqm_mxn_rent`: renta mensual por metro cuadrado (MXN/m²/mes). Solo se puebla para inmuebles en renta o ambas modalidades (`rent`, `both`). Es nulo para venta pura (`sale`).
- `price_total_mxn_rent`: renta total mensual (MXN/mes) = `area_sqm × price_sqm_mxn_rent`. Sigue la misma regla de nulabilidad.
- `price_sqm_mxn_sale`: precio de venta por metro cuadrado en MXN/m². Solo se puebla para inmuebles en venta o ambas modalidades (`sale`, `both`). Es nulo para inmuebles de renta pura (`rent`).
- `price_total_mxn_sale`: precio de venta total (MXN) = `area_sqm × price_sqm_mxn_sale`. Sigue la misma regla de nulabilidad.
- `maintenance_cost_mxn`: costo de mantenimiento mensual (MXN/mes). Solo se puebla para inmuebles en renta o ambas modalidades. Es nulo para venta pura.

## Presupuestos

- `min_budget_mxn_rent_monthly` y `max_budget_mxn_rent_monthly`: presupuesto mensual de renta (MXN/mes). Son directamente comparables con `price_total_mxn_rent` de los spots. Se pueblan para leads con modalidad `rent` o `both`.
- `min_budget_mxn_sale_total` y `max_budget_mxn_sale_total`: presupuesto total de compra (MXN). Son directamente comparables con `price_total_mxn_sale`. Se pueblan para leads con modalidad `sale` o `both`.
- Para leads con `search_modality = both`, ambos pares de presupuestos están poblados.
- `requested_budget_mxn_rent_monthly` en `inquiries`: presupuesto de renta mencionado en la consulta. Es nulo si el lead no busca renta.
- `requested_budget_mxn_sale_total` en `inquiries`: presupuesto de compra mencionado en la consulta. Es nulo si el lead no busca compra.

## Modalidad

- `spots.modality`: `rent`, `sale` o `both`. Determina qué campos de precio y mantenimiento están poblados.
- `leads.search_modality`: `rent`, `sale` o `both`. Determina qué presupuestos están poblados.
- Los `inquiries` de un lead solo se generan contra spots con modalidad compatible: `rent` con `rent` o `both`, `sale` con `sale` o `both`, y `both` con cualquier spot.

## Geografía

- `municipality`: división administrativa del espacio. Los municipios forman una partición del territorio: cada ubicación pertenece a exactamente un municipio.
- `corridor`: polígono de interés comercial, por ejemplo `polanco` o `santa_fe`. Un corredor puede abarcar partes de uno o varios municipios y no necesariamente los cubre por completo.

Municipio y corredor no forman una jerarquía directa.

## Contexto de mercado

- `avg_price_sqm_mxn`: promedio de renta mensual por m² (MXN/m²/mes), calculado solo con inmuebles en renta o ambas modalidades; no incluye venta pura.
- `recent_occupancy_rate`: tasa de ocupación reciente (0–1) para ese corredor, sector y mes.
- `absorption_velocity_days`: días promedio para ocupar un inmueble en ese corredor y sector.

## Disponibilidad

- `is_available`: indica si el inmueble está disponible en esa fecha.
- `days_until_available`: días estimados hasta la disponibilidad; vale 0 si ya está disponible.

## Campos temporales

- `leads.created_at`, `spots.created_at` e `inquiries.inquiry_at`: datetime en UTC.
- `market_context.month` y `availability_snapshot.snapshot_date`: date; el primero corresponde al primer día del mes y el segundo a una fecha puntual.
