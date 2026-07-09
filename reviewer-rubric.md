# Rubrica de evaluacion - Data Scientist Lead

Guia para evaluar el technical assessment. Cada candidato entrega: notebook, one-pager, slides, y prompt de IA usado.

---

## Criterios ponderados

| # | Criterio | Peso | Que evaluamos |
|---|----------|------|---------------|
| 1 | Fundamentos tecnicos | 20% | EDA solido, feature engineering justificado, modelado correcto, evaluacion completa |
| 2 | Lead Quality Model | 20% | Calibracion, validacion temporal, threshold analysis, feature selection |
| 3 | Inventory / Fallback | 15% | Definicion de disponibilidad, logica de alternativas, calidad de recomendaciones |
| 4 | Integracion del score | 15% | Combinacion de modelos, distribucion del score, evaluacion conjunta |
| 5 | Comunicacion de negocio | 15% | One-pager claro, slides efectivos, narrativa para audiencia no tecnica |
| 6 | Pensamiento senior | 15% | Tradeoffs, escalabilidad, sesgos, producto, monitoreo, LLM usage |

**Total:** 100 puntos. **Umbral sugerido para avanzar:** 70/100 con al menos 50% en cada criterio individual.

---

## Criterio 1: Fundamentos tecnicos (20 pts)

| Nivel | Puntos | Senales |
|-------|--------|---------|
| Sobresaliente | 18-20 | EDA narrativo con hipotesis de negocio. Feature engineering con justificacion causal. Validacion temporal correcta. Compara 2+ modelos con justificacion. |
| Solido | 14-17 | EDA completo pero descriptivo. Features relevantes sin justificacion profunda. Un modelo bien ejecutado. Validacion basica train/test. |
| Aceptable | 10-13 | EDA basico. Feature engineering minimo. Modelo simple sin comparacion. Errores menores en validacion. |
| Debil | <10 | EDA superficial o faltante. Features sin sentido. Modelo incorrecto para el problema. Sin validacion. |

### Checklist para el revisor

- [ ] El candidato detecto los patrones clave en los datos? (estacionalidad, sesgo por fuente, sectores calientes, dinamica por corredor)
- [ ] Uso metricas apropiadas (log-loss para probabilidades, AUC-ROC para ranking)?
- [ ] Reporto intervalos de confianza o variabilidad?
- [ ] Documento decisiones de manejo de datos faltantes y outliers?
- [ ] El codigo es reproducible y esta comentado?

---

## Criterio 2: Lead Quality Model (20 pts)

| Nivel | Puntos | Senales |
|-------|--------|---------|
| Sobresaliente | 18-20 | Modelo calibrado (calibration curve). Validacion temporal rigurosa. Threshold analysis con costo-beneficio. Feature importance con interpretacion de negocio. Deteccion de leakage. |
| Solido | 14-17 | Buen AUC-ROC. Validacion temporal. Threshold analysis basico. Reconoce leakage pero no lo resuelve del todo. |
| Aceptable | 10-13 | Modelo funcional. AUC-ROC aceptable (>0.7). Validacion train/test simple. Sin analisis de threshold. |
| Debil | <10 | AUC-ROC < 0.65 o no reportado. Sin validacion temporal. Overfitting evidente. No detecta leakage. |

### Senales de seniority

- Usa log-loss y Brier score, no solo accuracy.
- Analiza la calibracion con reliability diagrams.
- Prueba 2-3 algoritmos (logistic regression baseline + GBM + regularizado).
- Detecta el leak de `lead_score_internal` y explica por que es peligroso.
- Discute el tradeoff precision-recall en el contexto de negocio inmobiliario.

---

## Criterio 3: Inventory / Fallback (15 pts)

| Nivel | Puntos | Senales |
|-------|--------|---------|
| Sobresaliente | 14-15 | Definicion operativa de disponibilidad que considera sector, corredor, rango de precio/m2 y area. Modelo o heuristica bien justificada. Fallback recomienda inmuebles similares disponibles y evalua calidad de recomendaciones. |
| Solido | 11-13 | Definicion basica de disponibilidad. Heuristica simple de fallback. Considera al menos dos dimensiones de similitud (sector + corredor). |
| Aceptable | 8-10 | Disponibilidad = inmueble activo. Fallback = cualquier inmueble disponible. Sin evaluacion de calidad. |
| Debil | <8 | No define disponibilidad claramente. Fallback ausente o trivial. |

### Senales de seniority

- La definicion de disponibilidad considera el estado del mercado (absorcion, ocupacion) y no solo el flag booleano.
- El fallback usa similitud multidimensional (sector + corredor + rango precio/m2 + area) y no solo la misma ubicacion.
- Evalua el fallback con alguna metrica (precision@k, relevancia de recomendaciones).
- Discute el cold start: que hacer con inmuebles nuevos sin historial de inquiries.

---

## Criterio 4: Integracion del score (15 pts)

| Nivel | Puntos | Senales |
|-------|--------|---------|
| Sobresaliente | 14-15 | Formula de combinacion justificada (multiplicacion vs ponderacion). Analisis de distribucion del score. Evaluacion comparativa contra baseline (ej: solo Lead Quality). Simulacion de impacto de negocio. |
| Solido | 11-13 | Combinacion logica. Distribucion del score. Evaluacion contra baseline simple. |
| Aceptable | 8-10 | Combinacion basica (promedio o producto simple). Sin evaluacion comparativa. |
| Debil | <8 | Combinacion arbitraria o ausente. Sin justificacion. |

### Senales de seniority

- Compara 2+ estrategias de combinacion y explica tradeoffs.
- Simula el impacto en revenue o tasa de cierre del sistema combinado.
- Discute el umbral de accion: a que score un lead merece atencion prioritaria de un broker?
- Considera la frecuencia de actualizacion del score (cada cuanto cambia la disponibilidad de un inmueble?).

---

## Criterio 5: Comunicacion de negocio (15 pts)

| Nivel | Puntos | Senales |
|-------|--------|---------|
| Sobresaliente | 14-15 | One-pager claro, con una visualizacion que cuenta la historia. Slides estructurados para audiencia mixta (Producto + C-Level). Sin jerga tecnica innecesaria. Recomendaciones accionables. |
| Solido | 11-13 | One-pager completo. Slides claros. Algo de jerga tecnica. Recomendaciones generales. |
| Aceptable | 8-10 | One-pager funcional pero denso. Slides con mucho texto. Recomendaciones vagas. |
| Debil | <8 | Sin one-pager o incomprensible para no tecnicos. Slides desorganizados. |

### Checklist para el revisor

- [ ] El one-pager se entiende sin leer el notebook?
- [ ] La visualizacion principal es informativa y limpia?
- [ ] Los slides tienen una estructura clara (problema -> enfoque -> resultado -> impacto)?
- [ ] Las recomendaciones son accionables por Producto/Growth en el contexto inmobiliario?
- [ ] El candidato evita jerga tecnica innecesaria?

---

## Criterio 6: Pensamiento senior (15 pts)

| Nivel | Puntos | Senales |
|-------|--------|---------|
| Sobresaliente | 14-15 | Discute tradeoffs explicitamente. Identifica sesgos y limitaciones. Propone monitoreo en produccion. Plan de experimento para medir impacto real. Uso sofisticado de IA. Vision de producto con 3 meses de horizonte. |
| Solido | 11-13 | Menciona tradeoffs. Algun sesgo identificado. Idea de monitoreo. Uso basico de IA. Vision de producto general. |
| Aceptable | 8-10 | Tradeoffs superficiales. Sin discusion de sesgos. Sin plan de monitoreo. IA usada pero sin reflexion. |
| Debil | <8 | Sin discusion de tradeoffs. Sin consciencia de sesgos. Sin plan de produccion. IA no usada o irrelevante. |

### Senales de seniority especificas

| Senal | Que buscar |
|-------|------------|
| Validacion temporal | Usa split por fecha, no aleatorio. Discute deriva temporal en el mercado inmobiliario. |
| Threshold analysis | Analiza costo de falsos positivos vs falsos negativos en contexto de comisiones y tiempo de brokers. |
| Calibracion | No solo AUC, tambien reliability diagram, Brier score. |
| Feature leakage awareness | Detecta `lead_score_internal`, discute `has_converted_before`. |
| Fallback recommendation quality | No solo recomienda, evalua si la recomendacion es relevante para el lead. |
| Production monitoring | Que metricas, que alertas, cada cuanto reentrenar. Considera estacionalidad del sector CRE. |
| LLM usage | Describe prompt, evalua calidad, identifica limitaciones. |

---

## Escala de calificacion final

| Puntaje | Decision | Accion |
|---------|----------|--------|
| 85-100 | Contratar sin reservas | Avanzar a entrevista final con equipo |
| 70-84 | Contratar con objeciones menores | Avanzar, preparar preguntas especificas para entrevista |
| 50-69 | No contratar ahora | Archivar, posiblemente reconsiderar en 6 meses |
| <50 | Rechazar | Feedback constructivo si aplica |

---

## Guia para el revisor

### Antes de evaluar

1. Lee `assessment.md` para entender el contexto completo.
2. Revisa `synthetic-data-guide.md` para conocer los leaks y patrones incorporados.
3. Prepara los outcomes reales para verificar metricas del candidato.

### Durante la evaluacion

1. Corre el notebook del candidato (o al menos verifica que es reproducible).
2. No penalices por errores de sintaxis o librerias faltantes si la logica es correcta.
3. El candidato no tenia acceso al archivo de outcomes (CSV/Parquet). No penalices por no conocer la tasa de conversion real.
4. Premia la Honestidad Intelectual: si el candidato dice "esto no lo se" o "esto lo simplifico porque", es mejor que inventar.

### Despues de evaluar

1. Completa la tabla de puntuacion (abajo).
2. Escribe un parrafo de resumen con la decision y las 2-3 razones principales.
3. Si aplica, prepara preguntas para la siguiente entrevista basadas en las areas debiles.

### Tabla de puntuacion

| Criterio | Peso | Puntos | Peso x Puntos | Notas |
|----------|------|--------|---------------|-------|
| 1. Fundamentos tecnicos | 20% | /20 | | |
| 2. Lead Quality Model | 20% | /20 | | |
| 3. Inventory / Fallback | 15% | /15 | | |
| 4. Integracion del score | 15% | /15 | | |
| 5. Comunicacion de negocio | 15% | /15 | | |
| 6. Pensamiento senior | 15% | /15 | | |
| **Total** | **100%** | | **/100** | |

---

## Preguntas para entrevista oral (si aplica)

Si el candidato avanza, estas preguntas profundizan en areas que el assessment no cubre:

1. **MLOps:** Como monitorearias este sistema en produccion? Que metricas de data drift usarias en el contexto de bienes raices comerciales?
2. **Experimento:** Disena un experimento para medir el impacto del Lead Opportunity Score en comisiones cerradas.
3. **Cold start:** Como manejas leads sin historial o inmuebles nuevos sin datos de mercado?
4. **Etica:** Que sesgos potenciales tiene este sistema (ej. sesgo hacia ciertos sectores o zonas) y como los mitigarias?
5. **Arquitectura:** Como disenarias el servicio de scoring para manejar 10x el volumen actual de leads e inmuebles?
6. **LLM como juez:** Como usarias un LLM para evaluar la calidad de las recomendaciones fallback de inmuebles similares?
