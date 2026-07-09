# Guia de datos sinteticos

Este documento especifica las tablas, esquemas, reglas de generacion y advertencias para producir los datos del Data Scientist Lead Assessment.

No incluye datos reales de clientes. Todo es sintetico. No incluye PII.

---

## Vision general

7 tablas relacionales, cada una disponible en CSV y Parquet. ~105 MB en total (~90 MB en Parquet, ~105 MB en CSV). Disenadas para que un candidato encuentre patrones realistas sin requerir acceso a servicios internos de Spot2.

```
leads       +---------+  inquiries   +---------+  availability_snapshot
            | lead_id |--------------->| lead_id |
            +---------+                +---------+
                 |                           |
                 v                           v
          outcomes              spots +---------+
          (oculto)              +---------+ | spot_id |
                                |         | +---------+
                                v         v
                      spot_attributes  |
                                        v
                              market_context
```

---

## Tabla: leads

**Filas:** ~5,000. **Periodo:** Enero 2025 - Junio 2026.

| Columna | Tipo | Descripcion | Detalles de generacion |
|---------|------|-------------|------------------------|
| `lead_id` | int (PK) | ID unico del lead | Entero secuencial, 1-5000 |
| `user_type` | string | Tipo de usuario | `broker` 35%, `tenant_direct` 40%, `investor` 20%, `developer` 5% |
| `company_size` | string | Tamano de la empresa | `small` (1-10 emp) 25%, `medium` (11-100) 35%, `large` (101-1000) 25%, `enterprise` (>1000) 15% |
| `industry` | string | Industria del lead | `technology` 20%, `retail` 25%, `manufacturing` 15%, `logistics` 10%, `financial` 10%, `healthcare` 10%, `other` 10% |
| `search_sector` | string | Sector de interes | `Industrial` 25%, `Office` 30%, `Retail` 30%, `Land` 15% |
| `search_modality` | string | Modalidad de interes | `rent` 50%, `sale` 30%, `both` 20% |
| `target_area_sqm` | float | Area objetivo en m2 | Distribucion log-normal, media 500, std 400, truncada [30, 10000] |
| `min_budget_mxn_rent_monthly` | float | Presupuesto minimo de renta mensual (MXN) | target_area_sqm x sector_rent_mean x uniform(0.7, 0.9). NULL para leads de venta. |
| `max_budget_mxn_rent_monthly` | float | Presupuesto maximo de renta mensual (MXN) | min_budget_rent x uniform(1.1, 1.5). Siempre >= min. NULL para leads de venta. |
| `min_budget_mxn_sale_total` | float | Presupuesto minimo de compra total (MXN) | target_area_sqm x sector_rent_mean x 180 x uniform(0.7, 0.9). NULL para leads de renta. |
| `max_budget_mxn_sale_total` | float | Presupuesto maximo de compra total (MXN) | min_budget_sale x uniform(1.1, 1.5). Siempre >= min. NULL para leads de renta. |
| `preferred_state` | string | Estado preferido | 5 estados: `CDMX`, `Mexico`, `NuevoLeon`, `Jalisco`, `Queretaro`. 40% concentrado en CDMX y Mexico. |
| `preferred_municipality` | string | Municipio preferido | ~20 municipios, distribuidos proporcionalmente al PIB industrial de cada zona |
| `preferred_corridor` | string | Corredor industrial/comercial | `industrial_vallejo`, `santa_fe`, `insurgentes`, `periferico`, `toreo`, `aeropuerto`, `ecatepec`, `tlaquepaque`, `apodaca`, `escobedo`, `queretaro_centro`, etc. |
| `source` | string | Canal de adquisicion | `organic` 30%, `referral` 20%, `paid` 25%, `social` 10%, `email` 10%, `event` 5% |
| `prior_searches` | int | Busquedas previas del lead | Distribucion: 35% 0, 30% 1-3, 20% 4-10, 15% >10 |
| `prior_inquiries` | int | Inquiries previos del lead | Distribucion: 45% 0, 30% 1-5, 15% 6-15, 10% >15 |
| `has_converted_before` | bool | Ha convertido en el pasado? | 10% true. Correlacionado con prior_inquiries y prior_searches. |
| `lead_score_internal` | float | Score interno de calidad del lead | **Columna leakage.** Correlacionada artificialmente con `converted`. No deberia estar en train. |
| `created_at` | datetime | Fecha de creacion del lead | Distribucion uniforme en el periodo. Mayor volumen en dias laborables. |

Para `search_modality = both`, los cuatro campos de presupuesto estan poblados. Los presupuestos de renta son directamente comparables con `spots.price_total_mxn_rent`; los de compra, con `spots.price_total_mxn_sale`.

### Leakage traps en leads

1. **`lead_score_internal`** tiene correlacion artificial con `converted`. Es un score interno que no existiria en produccion. Se evalua si el candidato lo detecta y lo excluye.
2. **`has_converted_before`** es un target leak disfrazado. Solo deberia usarse como feature si se justifica su disponibilidad en tiempo de prediccion (el dato existe para leads recurrentes, no para nuevos).

### Valores faltantes

- `company_size`: 5% faltante (MCAR)
- `industry`: 3% faltante
- `preferred_corridor`: 8% faltante (leads sin corredor especifico)
- `min_budget_mxn_rent_monthly`: 4% faltante entre leads de renta/both (MCAR).
- `min_budget_mxn_sale_total`: 4% faltante entre leads de venta/both (MCAR).

### Outliers

- `target_area_sqm`: 2% con valores > 5,000 m2 (grandes corporativos o naves industriales).
- `max_budget_mxn_rent_monthly`: 3% con valores > 3x IQR (proyectos institucionales de renta).
- `max_budget_mxn_sale_total`: 3% con valores > 3x IQR (proyectos institucionales de compra).
- `prior_inquiries`: 3% con valores > 50 (posibles bots/scrapers).

---

## Tabla: spots

**Filas:** ~2,000-4,000. **Periodo:** Catalogo actual (puede incluir inmuebles inactivos o vendidos).

`distributions.py` define `_PRICE_PER_SQM` como renta mensual por metro cuadrado: `# Monthly rent price per square meter in MXN (2025-2026 market ranges).` La tupla es `(media, desviacion_estandar, minimo, maximo)`.

| Sector | Media | Desviacion estandar | Minimo | Maximo |
|--------|-------|---------------------|--------|--------|
| Industrial | 150 | 66 | 94 | 563 |
| Office | 350 | 112 | 112 | 980 |
| Retail | 300 | 117 | 100 | 833 |
| Land | 50 | 30 | 15 | 200 |

| Columna | Tipo | Descripcion | Detalles de generacion |
|---------|------|-------------|------------------------|
| `spot_id` | int (PK) | ID unico del inmueble | Entero secuencial |
| `broker_id` | int | ID del broker/propietario | ~300 brokers unicos. 70% tiene 1-5 inmuebles, 30% tiene 6+ |
| `sector_name` | string | Sector del inmueble | `Industrial`, `Office`, `Retail`, `Land`. Distribucion: Industrial 30%, Office 30%, Retail 25%, Land 15% |
| `type_name` | string | Tipo de espacio | `Single` (espacio individual) 70%, `Subspace` (subdivision) 30%. Excluir `Complex`. |
| `state` | string | Estado | Mismos 5 estados que leads |
| `municipality` | string | Municipio | ~20 municipios |
| `settlement` | string | Colonia/fraccionamiento | ~100 nombres sinteticos |
| `corridor` | string | Corredor | Mismos corredores que leads. Cada corredor tiene 5-50 inmuebles. |
| `region` | string | Region geografica | `norte`, `centro`, `occidente`, `sur` |
| `lat` | float | Latitud | Generada con ruido gaussiano alrededor de coordenadas reales de cada municipio |
| `lon` | float | Longitud | Generada con ruido gaussiano |
| `title` | string | Titulo del inmueble | Plantilla: `"{type_name} {sector} en {corridor}, {municipality}"` |
| `description` | string | Descripcion del inmueble | Texto sintetico de 1-3 frases sobre caracteristicas |
| `area_sqm` | float | Area total en m2 | Distribucion log-normal, media 350, std 300, truncada [20, 8000]. Menor para Office, mayor para Industrial/Land. |
| `price_sqm_mxn_rent` | float | Precio de renta mensual por m2 (MXN) | Poblado para `rent`/`both`; NULL para `sale`. |
| `price_sqm_mxn_sale` | float | Precio de venta por m2 (MXN) | `price_sqm_mxn_rent x 180 x random(0.8, 1.2)`. Poblado para `sale`/`both`; NULL para `rent`. |
| `price_total_mxn_rent` | float | Renta total mensual (MXN) | `area_sqm x price_sqm_mxn_rent`. Poblado para `rent`/`both`; NULL para `sale`. |
| `price_total_mxn_sale` | float | Precio de venta total (MXN) | `area_sqm x price_sqm_mxn_sale`. Poblado para `sale`/`both`; NULL para `rent`. |
| `maintenance_cost_mxn` | float | Costo de mantenimiento mensual (MXN) | `price_total_mxn_rent x uniform(0.05, 0.15)`. Poblado para `rent`/`both`; NULL para `sale`. |
| `modality` | string | Modalidad disponible | `rent` 40%, `sale` 25%, `both` 35%. Determina la nulabilidad de los precios y del mantenimiento: renta/mantenimiento para `rent`/`both`; venta para `sale`/`both`. |
| `days_on_market` | int | Dias publicado en la plataforma | Distribucion exponencial, media 90 dias. Max 730. |
| `total_inquiries` | int | Total de inquiries recibidos | Correlacionado con days_on_market y sector caliente. |
| `total_views` | int | Vistas totales del inmueble | `total_inquiries * uniform(10, 30)` |
| `is_active` | bool | Inmueble actualmente activo? | 88% true. Inactivos aparecen en datos historicos pero no en prediccion de disponibilidad. |
| `created_at` | datetime | Fecha de publicacion | Distribucion uniforme 2024-2026 |

### Relaciones clave

- spots -> spot_attributes: 1:1 (cada inmueble tiene un registro de atributos).
- spots -> availability_snapshot: 1:N (varios snapshots en el tiempo por inquiry).
- spots -> inquiries: 1:N.

---

## Tabla: spot_attributes

**Filas:** ~2,000-4,000 (1:1 con spots).

| Columna | Tipo | Descripcion | Detalles de generacion |
|---------|------|-------------|------------------------|
| `spot_id` | int (FK) | Referencia a spots | 1:1 |
| `natural_light` | bool | Tiene luz natural? | 70% true (excepto ciertos Inmuebles industriales) |
| `luminaires` | int | Cantidad de luminarias | Distribucion: 40% 0, 30% 1-5, 20% 6-15, 10% >15 |
| `charging_ports` | int | Puertos de carga electrica | 80% 0, 15% 1-5, 5% >5 |
| `security_type` | string | Tipo de seguridad | `none` 15%, `basic` 40%, `cctv` 30%, `full` (cctv+guard) 15% |
| `floor_level` | int | Nivel del piso | 50% 0 (planta baja), 25% 1-3, 15% 4-10, 10% >10 |
| `elevators` | int | Numero de elevadores | Correlacionado con floor_level y area_sqm |
| `vertical_height_m` | float | Altura libre en metros | Industrial: media 8m, Office: media 3m, Retail: media 4m, Land: 0 |
| `parking_spaces` | int | Cajones de estacionamiento del inmueble | Correlacionado con area_sqm. Office: 1/20m2, Retail: 1/30m2, Industrial: 1/50m2 |
| `building_status` | string | Estado de la construccion | `new` 20%, `good` 45%, `fair` 25%, `needs_renovation` 10% |
| `floor_material` | string | Material del piso | `concrete` 35%, `ceramic` 25%, `polished_concrete` 20%, `wood` 10%, `carpet` 10% |
| `amenities` | string (JSON) | Amenidades adicionales | Ej: `["reception","cafeteria","meeting_rooms","gym"]`. 60% tiene al menos 1 amenidad. |

### Valores faltantes

- `vertical_height_m`: 15% faltante (especialmente en terrenos).
- `floor_material`: 8% faltante.
- `charging_ports`: 20% faltante (no reportado).

---

## Tabla: inquiries

**Filas:** ~15,000-25,000. **Periodo:** Enero 2025 - Junio 2026. Relacion leads:inquiries = 1:3 a 1:5.

| Columna | Tipo | Descripcion | Detalles de generacion |
|---------|------|-------------|------------------------|
| `inquiry_id` | int (PK) | ID unico | Entero secuencial |
| `lead_id` | int (FK) | Referencia a leads | Cada lead tiene 1-8 inquiries |
| `spot_id` | int (FK) | Referencia al inmueble consultado | Seleccion compatible con modalidad: leads `rent` eligen spots `rent`/`both`; leads `sale`, spots `sale`/`both`; leads `both` pueden elegir cualquier spot. Dentro del pool, 60% mismo corredor/sector y 40% otros. |
| `inquiry_at` | datetime | Fecha del inquiry | Correlacionado con `leads.created_at`, dentro de 1-14 dias post-lead |
| `channel` | string | Canal del inquiry | `web` 30%, `app` 25%, `whatsapp` 25%, `email` 15%, `phone` 5% |
| `message_length` | int | Longitud del mensaje del lead | Distribucion log-normal media 200 caracteres |
| `requested_area_sqm` | float | Area solicitada por el lead | Consistente con `leads.target_area_sqm`. Ruido gaussiano std 15%. |
| `requested_budget_mxn_rent_monthly` | float | Presupuesto de renta mensual solicitado (MXN) | max(0, max_budget_mxn_rent_monthly x uniform(0.7, 1.1)), acotado al maximo. NULL si el lead no busca renta. |
| `requested_budget_mxn_sale_total` | float | Presupuesto de compra total solicitado (MXN) | max(0, max_budget_mxn_sale_total x uniform(0.7, 1.1)), acotado al maximo. NULL si el lead no busca compra. |
| `urgency_days` | int | Urgencia expresada en dias | 30% sin especificar. Del resto: 20% < 30 dias, 40% 30-90, 40% >90. |
| `asked_visit` | bool | Solicito visita al inmueble? | 25% true. Correlacionado positivamente con conversion. |
| `broker_response` | string | Respuesta del broker | `accepted` 45%, `rejected` 15%, `no_response` 20%, `scheduled_visit` 20% |
| `broker_response_hours` | float | Tiempo de respuesta del broker (horas) | Distribucion exponencial, media 12h. 15% sin respuesta (>168h = null). |

### Relaciones importantes

- `broker_response` esta correlacionado con `converted`, pero NO es un leak: es informacion disponible antes de la prediccion.
- Inquiries con `broker_response = rejected` tienen menor P(conversion).
- Inquiries con `broker_response_hours` largo tienen menor P(conversion).
- `asked_visit` es un predictor fuerte de conversion.

---

## Tabla: market_context

**Filas:** ~500 (5 estados x ~5 municipios x ~20 meses). **Periodo:** Enero 2024 - Junio 2026.

| Columna | Tipo | Descripcion | Detalles de generacion |
|---------|------|-------------|------------------------|
| `state` | string | Estado | 5 estados |
| `municipality` | string | Municipio | ~20 municipios |
| `corridor` | string | Corredor | ~12 corredores. Puede ser null si no aplica. |
| `sector` | string | Sector | `Industrial`, `Office`, `Retail`, `Land` |
| `month` | date | Primer dia del mes | Mensual |
| `similar_available_spots` | int | Inmuebles similares disponibles en la zona | Dinamico: 10-200. Correlacionado negativamente con demanda. |
| `avg_price_sqm_mxn` | float | Precio promedio mensual de renta por m2 por sector | Se deriva solo de inventario rentable (`rent`/`both`); los spots solo de venta se excluyen. Con tendencia: +3% anual. Con estacionalidad: picos en Q1. |
| `recent_occupancy_rate` | float | Tasa de ocupacion reciente (0-1) | Office: 0.75-0.90, Industrial: 0.80-0.95, Retail: 0.70-0.85, Land: 0.50-0.70 |
| `absorption_velocity_days` | float | Velocidad de absorcion (dias para ocupar) | Office: 60-180, Industrial: 90-240, Retail: 45-150, Land: 120-365 |
| `recent_inquiry_volume` | int | Volumen de inquiries en el periodo | Normalizado por mes/sector. 50-500. |

### Patrones incorporados

- Corredores con alta absorcion (baja velocity) tienen menos inmuebles disponibles y precios mas altos.
- Sector Industrial tiene ocupacion mas estable; Retail es mas volatil.
- Hay una correlacion debil pero real entre `absorption_velocity_days` baja y alta probabilidad de conversion.

---

## Tabla: availability_snapshot

**Filas:** ~20,000-40,000 (snapshots en el tiempo, no diarios). Representa el estado de disponibilidad de un inmueble al momento de cada consulta o en puntos de control.

| Columna | Tipo | Descripcion | Detalles de generacion |
|---------|------|-------------|------------------------|
| `snapshot_id` | int (PK) | ID unico del registro | Entero secuencial |
| `spot_id` | int (FK) | Referencia al inmueble | Solo inmuebles activos |
| `snapshot_date` | date | Fecha del snapshot | Distribucion irregular: mas snapshots cuando hay actividad (inquiries, cambios de precio) |
| `is_available` | bool | Esta disponible para renta/venta? | 65% disponible, 35% no disponible |
| `days_until_available` | int | Dias estimados hasta que este disponible (si no lo esta) | Para no disponibles: distribucion exponencial media 60 dias. Para disponibles: 0. |
| `competing_inquiries_30d` | int | Inquiries competidores en los ultimos 30 dias | Correlacionado con demanda del inmueble. 0-20. |

### Logica de disponibilidad

- Un inmueble ocupado/ vendido aparece como no disponible en los snapshots posteriores a la fecha de ocupacion.
- Inmuebles en zonas de alta demanda tienen menor proporcion de disponibles.
- Inmuebles con `building_status = needs_renovation` tienen 20% mas probabilidad de estar disponibles.
- La disponibilidad se actualiza en el snapshot cuando ocurre un inquiry o un cambio de estado.

---

## Tabla: outcomes (OCULTA)

**No se entrega al candidato.** Solo para evaluacion. Un registro por lead.

| Columna | Tipo | Descripcion | Regla de generacion |
|---------|------|-------------|---------------------|
| `lead_id` | int (PK) | Referencia a leads | 1:1 con leads |
| `converted_to_visit` | bool | El lead concreto una visita? | ~22% del total (1100/5000) |
| `converted_to_closure` | bool | El lead llego a cierre/renta? | ~10% del total (500/5000). Solo si `converted_to_visit = true`. |
| `conversion_date` | datetime | Fecha de conversion | Dentro de 7-60 dias post-creacion del lead |
| `final_spot_id` | int | Que inmueble tomo? (si convirtio) | Generalmente el spot del inquiry con visita aceptada |
| `spot_available_for_lead` | bool | El inmueble solicitado estaba disponible? | Basado en availability_snapshot al momento del inquiry |
| `opportunity_label` | string | Etiqueta de oportunidad real | `high_quality_available`, `high_quality_unavailable`, `low_quality`, `converted` |
| `lead_quality_true` | float | Probabilidad real de conversion (simulada) | Feature para evaluar calibracion del modelo del candidato |

### Reglas de generacion de outcomes

La variable `converted_to_visit` se genera con esta funcion logistica subyacente:

```
P(conversion) = sigmoid(
    0.7 * (source == referral) +
    0.5 * (search_sector == Office) +
    0.4 * (user_type == tenant_direct) +
    0.3 * (max(rent_affordability, sale_affordability) > median_affordability) +
    0.4 * (1 < prior_inquiries <= 5) +
    0.2 * (broker_response == accepted) +
    0.5 * (asked_visit == true) -
    0.5 * (broker_response == no_response) -
    0.3 * (absorption_velocity_days > 180) -
    0.4 * (spot_available_for_lead == false)
    + noise N(0, 0.3)
)
```

El componente de presupuesto usa asequibilidad normalizada para comparar renta y compra en la misma escala:

```
rent_affordability = max_budget_rent / (area x sector_rent_reference)
sale_affordability = max_budget_sale / (area x sector_sale_reference)
```

La senal usa `max(rent_affordability, sale_affordability) > median_affordability`. Para una modalidad no aplicable, su presupuesto no contribuye a la comparacion.

`converted_to_closure` se genera como subconjunto de `converted_to_visit` con probabilidad adicional del 45%.

Los coeficientes no se revelan al candidato. El candidato debe inferir patrones.

---

## Split temporal recomendado

| Conjunto | Rango de fechas | Leads |
|----------|----------------|-------|
| Entrenamiento | Enero 2025 - Marzo 2026 | ~4,000 |
| Validacion | Abril 2026 - Mayo 2026 | ~500 |
| Prueba | Junio 2026 | ~500 |

Este split fuerza al candidato a validar temporalmente, no solo con muestreo aleatorio.

---

## Advertencias y leakage traps

### Leakage traps disenados

1. **`lead_score_internal`** en leads: correlacion artificial con conversion. No disponible en produccion.
2. **`has_converted_before`**: disponible solo si el lead es recurrente, pero facil de malinterpretar como target.
3. **`outcomes`** (CSV y Parquet): no debe usarse en entrenamiento (esta oculto del candidato, pero si por error lo incluyen, se evalua negativamente).

### Datos faltantes

| Columna | % faltante | Mecanismo |
|---------|-----------|-----------|
| leads.company_size | 5% | MCAR |
| leads.industry | 3% | MCAR |
| leads.preferred_corridor | 8% | MCAR |
| leads.min_budget_mxn_rent_monthly | 4% entre leads de renta/both | MCAR |
| leads.min_budget_mxn_sale_total | 4% entre leads de venta/both | MCAR |
| spot_attributes.vertical_height_m | 15% | MAR (terrenos no tienen altura) |
| spot_attributes.floor_material | 8% | MCAR |
| spot_attributes.charging_ports | 20% | MAR (inmuebles antiguos no reportan) |
| inquiries.urgency_days | 30% | MNAR (leads sin urgencia no lo especifican) |
| inquiries.broker_response_hours | 15% | MNAR (brokers que nunca responden) |

### Outliers esperados

- `leads.target_area_sqm` > 5000: grandes corporativos o naves industriales. 2% de los datos.
- `leads.max_budget_mxn_rent_monthly` > 3x IQR: proyectos institucionales de renta. 3% de los datos.
- `leads.max_budget_mxn_sale_total` > 3x IQR: proyectos institucionales de compra. 3% de los datos.
- `spots.area_sqm` < 30: subspaces muy pequenos. 1% de los datos.
- `spots.price_sqm_mxn_rent` por sector: > 3x la media del mismo sector. 2%.

El candidato debe detectar, documentar y decidir como manejarlos.

---

## Como generar los datos

Escribe un script en Python (`generate_assessment_data.py`) que:

1. Use `numpy` y `pandas`.
2. Fije una semilla (`np.random.seed(42)`) para reproducibilidad.
3. Genere las 7 tablas en orden de dependencias (leads -> spots -> spot_attributes -> inquiries -> market_context -> availability_snapshot -> outcomes).
4. Aplique missingness segun las reglas.
5. Inyecte outliers segun las reglas.
6. Guarde cada tabla como CSV en `data/candidate/csv/` y como Parquet en `data/candidate/parquet/`.
7. Guarde `outcomes.csv` (y `outcomes.parquet`) en `data/evaluation/csv/` y `data/evaluation/parquet/`.
8. NO incluya la carpeta `evaluation/` en el paquete que recibe el candidato.

**Output esperado:**

```
data/
  candidate/
    csv/
      leads.csv
      spots.csv
      spot_attributes.csv
      inquiries.csv
      market_context.csv
      availability_snapshot.csv
    parquet/
      leads.parquet
      spots.parquet
      spot_attributes.parquet
      inquiries.parquet
      market_context.parquet
      availability_snapshot.parquet
  evaluation/
    csv/
      outcomes.csv
    parquet/
      outcomes.parquet
```

---

## Consistencia geoespacial

Las columnas de ubicacion (`state`, `municipality`, `settlement`, `region`, `corridor`, `lat`, `lon`) deben cumplir esta regla:

1. **Tuplas ancla validadas.** Cada combinacion state-municipality-settlement tiene un centroide realista definido como par (lat, lon) de referencia. Usa centros urbanos o industriales conocidos de cada municipio (no coordenadas arbitrarias ni generadas aleatoriamente).

2. **Jitter acotado.** Las coordenadas individuales se generan aplicando ruido gaussiano alrededor del centroide, con una desviacion estandar que garantiza que el 95% de los puntos caigan dentro de 2.5 km del ancla. Esto evita clusters imposibles (todos los puntos exactamente iguales) y outliers irreales (puntos en el oceano o en estados distintos).

3. **Consistencia jerarquica.** Cada corredor pertenece a un municipio, cada municipio a un estado. No deben generarse combinaciones invalidas (ej. un corredor de Nuevo Leon con coordenadas en Jalisco).

4. **Sin datos reales.** Las coordenadas ancla se derivan de centros poblacionales publicos (cabeceras municipales), no de inmuebles reales de Spot2 ni de coordenadas de produccion.

---

## Mapeo de referencia interna (ClickHouse)

Spot2 mantiene dos capas de datos en ClickHouse que reflejan la arquitectura del sistema:

- **`datalake`**: almacena tablas de origen Postgres (geospot/warehouse). Incluye datos de mercado agregados, inventario historico, y snapshots de disponibilidad. Las tablas en `datalake` tienen un esquema cercano a `market_context` y `availability_snapshot`.
- **`platform`**: almacena tablas de origen MySQL (spot2_service/transaccional). Incluye leads, spots, inquiries, y datos de usuario. Las tablas en `platform` informan el esquema de `leads`, `spots`, `spot_attributes`, e `inquiries`.

> [!NOTE]
> Esta referencia es solo para que el generador de datos sinteticos entienda la forma y relacion de las tablas reales. No conectes el script de generacion a ClickHouse ni extraigas datos de produccion. Los datos sinteticos no deben copiar valores reales, solo replicar la forma y cardinalidad de las relaciones.

No se requiere acceso a ClickHouse para generar los datos sinteticos. Todo se genera proceduralmente con numpy/pandas. Las tablas de referencia en ClickHouse solo informan cardinalidades y distribuciones aproximadas, no valores concretos.

## Notas finales

- No uses datos reales de clientes. Todo debe ser generado.
- No incluyas PII en ninguna tabla.
- Los nombres de columnas estan en ingles (consistente con la base real).
- La documentacion y el challenge estan en espanol (consistente con el equipo).
- El script de generacion puede entregarse al candidato como parte del entorno o ejecutarse antes. Si se entrega, el candidato puede modificar la semilla y explorar robustez.
