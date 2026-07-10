# Data Scientist - Opportunity Assessment

Assessment tecnico para candidatos a Data Scientist en Spot2. Centrado en el **Lead Opportunity Score**: un modelo que predice no solo si un lead va a convertir, sino si el inventario actual de inmuebles comerciales puede atenderlo.

## Que incluye este paquete

| Archivo | Que es | Para quien |
|---------|--------|------------|
| `assessment.md` | Enunciado del challenge, instrucciones y entregables | Candidatos |
| `synthetic-data-guide.md` | Esquema detallado de datos sinteticos (CSV+Parquet), generacion y advertencias | Ingenieros de datos / revisores |
| `reviewer-rubric.md` | Rubrica de evaluacion con criterios ponderados y senales de seniority | Revisores |

## Flujo de uso

1. El equipo de People entrega `assessment.md` al candidato junto con los datos sinteticos generados a partir de `synthetic-data-guide.md`.
2. El candidato trabaja 6-8 horas y entrega: notebook, one-pager, presentacion y producto vision.
3. Los revisores evaluan con `reviewer-rubric.md`.

## Como generar los datos sinteticos

Sigue `synthetic-data-guide.md`. El script de generacion (`generate_assessment_data.py`) debe producir las tablas relacionales (~5k leads, ~2-4k spots, ~15-25k inquiries) tanto en CSV como en Parquet, con los esquemas y reglas ahi especificados. Ambos formatos se guardan bajo `data/`:

- `data/candidate/csv/` — tablas para el candidato en CSV
- `data/candidate/parquet/` — las mismas tablas en Parquet
- `data/evaluation/csv/` — tabla oculta de outcomes en CSV
- `data/evaluation/parquet/` — la misma en Parquet

Para generar el bundle completo del candidato: `python generate_assessment_data.py --output-dir data/`

No incluyas datos reales de clientes.

## Stack esperado del candidato

Python (pandas, scikit-learn, matplotlib/seaborn, plotly). SQL es un plus. El challenge no requiere MLOps ni infraestructura en produccion.

## Contexto del producto

Spot2 es un marketplace de inmuebles comerciales. Corredores, propietarios e instituciones publican espacios en renta o venta — Industriales, Oficinas, Retail, Terrenos — y empresas, inquilinos o inversionistas los buscan para establecerse. El equipo de Data Science busca construir un sistema que priorice leads de alta oportunidad: leads con alta probabilidad de conversion Y con inventario disponible para atenderlos.

## Contacto

Para dudas sobre el assessment, contacta al equipo de People/Data de Spot2 por el canal interno definido para el proceso.
