# Data Scientist Lead - Technical Assessment

## Lead Opportunity Score: Prioriza los leads correctos

Spot2 conecta a empresas e inversionistas con inmuebles comerciales. Cada semana recibimos cientos de leads de brokers, inquilinos e inversionistas. Algunos convierten en visitas o cierres, otros no. Y aunque un lead quiera concretar, a veces el inmueble ya no esta disponible o no hay alternativas adecuadas.

Tu reto: construir un sistema que calcule el **Lead Opportunity Score** combinando dos modelos: que tan probable es que un lead convierta (Lead Quality) y que tan probable es que el inventario actual pueda atenderlo (Inventory Availability).

**Tiempo estimado:** 6-8 horas. No esperamos un sistema en produccion. Esperamos un analisis solido, bien comunicado y pensado para escalar.

---

## Contexto del negocio

Spot2 tiene dos lados del mercado:

- **Propietarios y brokers:** publican espacios comerciales con sector (Industrial, Oficinas, Retail, Terreno), precio por metro cuadrado, ubicacion y disponibilidad.
- **Empresas, inquilinos e inversionistas:** buscan donde establecerse. Cuando nos contactan o exploran un inmueble, generan un lead.

El equipo de Growth prioriza leads manualmente. Esto no escala. Necesitamos un modelo que automaticamente asigne un puntaje de oportunidad a cada lead, y cuando el inventario no alcance, sugiera alternativas viables en el mismo sector y corredor.

---

## Datos

Cada tabla esta disponible en ambos formatos, CSV y Parquet, desde el paquete de datos del candidato (`data/candidate/csv/` y `data/candidate/parquet/`).

| Archivo | Filas aprox | Formatos | Contenido |
|---------|-------------|----------|-----------|
| `leads` | ~5,000 | CSV / Parquet | Datos del lead: tipo de usuario, sector de interes, presupuesto, ubicacion preferida |
| `spots` | ~2,000-4,000 | CSV / Parquet | Catalogo de inmuebles: sector, precio por m2, area, ubicacion, modalidad |
| `spot_attributes` | ~2,000-4,000 | CSV / Parquet | Atributos del inmueble: luminosidad, cajones de estacionamiento, altura libre, amenities |
| `inquiries` | ~15,000-25,000 | CSV / Parquet | Historial de contactos lead-inmueble: canal, area solicitada, urgencia |
| `market_context` | ~500 | CSV / Parquet | Contexto por estado/municipio/corredor/sector/mes: absorcion, ocupacion |
| `availability_snapshot` | ~20,000-40,000 | CSV / Parquet | Estado de disponibilidad por inmueble al momento de cada consulta |
| `outcomes` | ~5,000 | CSV / Parquet | (OCULTO del candidato) Conversion real de cada lead |

El archivo `outcomes.*` (CSV y Parquet) no se entrega al candidato. Se usa solo para evaluacion.

Parte del reto consiste en definir y construir tu propio target o proxy de conversión a partir de los datos disponibles. Debes justificar qué evento consideras como éxito (¿visita agendada? ¿respuesta del broker? ¿cierre?), qué ventana temporal o punto de corte utilizas y cuáles son las limitaciones de tu definición.

El detalle de cada columna, sus unidades y cómo interpretarlas está en `feature_dictionary.md`.

---

## Entregables

### 1. Analisis exploratorio de datos (EDA)

Cuentanos que descubriste. No es un checklist de estadisticas descriptivas. Es una narrativa de negocios con datos.

**Que esperamos:**
- Distribucion de leads por sector (Industrial, Oficinas, Retail, Terreno), modalidad (renta, venta, ambas), tipo de usuario (broker, inquilino directo, inversionista).
- Tasas de conversion por segmento (si puedes inferirlas de los datos disponibles sin usar outcomes.csv).
- Estacionalidad y patrones temporales en la demanda.
- Dinamica de mercado por corredor y municipio: precios, absorcion, rotacion.
- Calidad de datos: valores faltantes, outliers, sesgos.
- Hipotesis iniciales sobre que factores predicen conversion.

### 2. One-pager ejecutivo

Una pagina (maximo), para una audiencia de Producto y C-Level. Sin codigo. Sin jerga tecnica.

**Que esperamos:**
- El problema en una frase.
- Tu enfoque para el Lead Opportunity Score.
- Resultados clave (reales o simulados).
- Impacto esperado en el negocio.
- Una visualizacion que resuma la historia.

### 3. Modelo de Calidad del Lead (Lead Quality Model)

Construye un modelo que estime P(conversión | lead) usando los datos de leads e inquiries. El score resultante es una estimación construida por ti, no una etiqueta de ground truth oculta.

**Que esperamos:**
- Feature engineering justificado (sector, ubicacion, presupuesto, tipo de usuario, historial).
- Seleccion y entrenamiento de modelo(s).
- Evaluacion con metricas apropiadas (log-loss, AUC-ROC, precision-recall).
- Validacion temporal (los datos tienen una dimension temporal, aprovechala).
- Threshold analysis: que punto de corte usarías y por que.
- Analisis de errores: donde falla el modelo y por que.
- Calibracion: que tan bien calibradas estan tus probabilidades.

### 4. Inventory Availability Model

Modelo o heuristica que prediga P(disponibilidad | lead, inventario actual).

**Que esperamos:**
- Definicion de disponibilidad: que significa que un lead pueda ser atendido? (el inmueble exacto esta disponible? alguno similar en el mismo corredor?)
- Enfoque: puede ser un modelo, una regla de negocio, o una combinacion.
- Consideracion de restricciones reales: sector, rango de precio por m2, area, ubicacion, modalidad.
- Manejo de casos donde el inventario es insuficiente o el inmueble solicitado ya no esta disponible.

### 5. Lead Opportunity Score + Fallback

Combina los dos modelos anteriores en un puntaje unico. Cuando el puntaje es alto pero el inventario no alcanza, sugiere alternativas.

**Que esperamos:**
- Formula de combinacion (multiplicacion, pesos, o reglas) justificada.
- Distribucion del score resultante en la poblacion de leads.
- Estrategia de fallback: como recomendar inmuebles similares disponibles (mismo sector, corredor, rango de precio/m2 y area) cuando el ideal no lo esta.
- Evaluacion del sistema combinado: cuantos leads bien priorizados ganamos?

### 6. Escalabilidad y produccion

Sin implementar, describenos como llevarías esto a produccion.

**Que esperamos:**
- Pipeline de entrenamiento y prediccion.
- Monitoreo: que metricas vigilarias en produccion?
- Deriva de datos: como detectas que el modelo se esta degradando?
- Actualizacion del modelo: cada cuando reentrenas?
- Consideraciones de latencia y volumen.

### 7. Uso de IA (obligatorio)

Usa un LLM (ChatGPT, Claude, el que prefieras) como parte de tu solucion. Explica que hiciste, que prompt usaste, que funciono y que no.

**Ideas de uso:**
- Asistencia en feature engineering o interpretacion de resultados.
- Generacion de hipotesis para el EDA.
- Evaluacion de calidad de recomendaciones fallback.
- Redaccion del one-pager ejecutivo.
- Analisis de sesgos en los datos.

### 8. Product vision

Escribenos maximo 2 parrafos sobre como ves el futuro de este sistema.

**Que esperamos:**
- Que harías con 3 meses mas de tiempo y datos?
- Como integras esto con el producto?
- Que datos adicionales pedirías? (ej. datos macroeconomicos, tendencias de construccion, tasas de interes)
- Como medirías el impacto real en el negocio (experimento, RCT, cuasi-experimento)?

---

## Formato de entrega

1. **Notebook** (ipynb o HTML renderizado) con todo el analisis reproducible.
2. **One-pager** (PDF) ejecutivo.
3. **Slides** (PDF, 5-8 slides) con los hallazgos clave para una presentacion de 15 minutos.
4. **Prompt de IA** usado, en un bloque de texto dentro del notebook.

---

## Que evaluamos

| Area | Peso |
|------|------|
| Fundamentos tecnicos (EDA, feature engineering, modelado) | 20% |
| Lead Quality Model (calibracion, validacion, threshold) | 20% |
| Inventory / Fallback (definicion de disponibilidad, alternativas) | 15% |
| Integracion del score (combinacion, evaluacion conjunta) | 15% |
| Comunicacion de negocio (one-pager, presentacion) | 15% |
| Pensamiento senior (tradeoffs, escalabilidad, producto, sesgos) | 15% |

Los criterios detallados arriba cubren las áreas de evaluación.

---

## Tips

- **Los datos son sinteticos**, disenados para que encuentres patrones realistas. No busques relaciones perfectas.
- **El tiempo es real.** No intentes hacer MLOps, pipelines en la nube ni dashboards interactivos. Un analisis solido en un notebook vale mas que una infraestructura incompleta.
- **Hay leakage traps disenados.** Parte de la evaluacion es que los identifiques.
- **Hay valores faltantes y outliers.** Decidí como manejarlos y justifica tu decision.
- **La pregunta de producto es tan importante como el modelo.** No la dejes para el final.
- **No necesitas outcomes.csv para todo.** Puedes inferir heuristicas de los datos disponibles.
- **Usa el LLM.** Es parte explicita de la evaluacion.
