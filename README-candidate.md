# Data Scientist — Evaluación Técnica

Gracias por aceptar este reto. Lo diseñamos para reflejar el tipo de problemas que resolverías día a día en Spot2.

## El reto

Construirás un **Lead Opportunity Score** para un marketplace de bienes raíces comerciales. El score combina dos preguntas:

1. **Lead Quality**: ¿qué tan probable es que este lead convierta?
2. **Inventory Availability**: ¿puede nuestro inventario actual atender sus necesidades?

El resultado es un número único por lead: **Lead Opportunity Score = Lead Quality × Inventory Availability**.

Cuando el inventario está limitado, tu sistema también debe sugerir inmuebles alternativos viables en el mismo sector y corredor.

## Los datos

Recibes 6 tablas relacionales. Cada una está disponible en formato CSV y Parquet dentro de `data/candidate/csv/` y `data/candidate/parquet/`.

| Tabla | Filas (aprox) | Contenido |
|-------|---------------|-----------|
| `leads` | ~5,000 | Datos del lead: tipo de usuario, sector objetivo, dos familias de presupuesto según la modalidad (renta mensual y compra total), ubicación preferida |
| `spots` | ~2,000–4,000 | Catálogo de inmuebles: sector, precio por m², área, ubicación, modalidad |
| `spot_attributes` | ~2,000–4,000 | Características del inmueble: iluminación, cajones de estacionamiento, altura, amenidades |
| `inquiries` | ~15,000–25,000 | Historial de contacto lead-inmueble: canal, área solicitada, urgencia |
| `market_context` | ~500 | Contexto de mercado por estado/municipio/corredor/sector/mes |
| `availability_snapshot` | ~20,000–40,000 | Estado de disponibilidad por inmueble en distintos momentos |

Consulta `feature_dictionary.md` para una guía de los campos principales, sus unidades, relaciones entre tablas y criterios de interpretación.

> Nota: algunas etiquetas usadas para evaluación (como los resultados de conversión) se omiten intencionalmente; tus modelos deben predecir o inferir las variables objetivo relevantes.

Parte del reto consiste en definir y construir tu propio target o proxy de conversión a partir de los datos disponibles. Debes justificar qué evento consideras como éxito, qué ventana temporal utilizas y cuáles son las limitaciones de tu definición.

### Cargar los datos

Ambos formatos están incluidos para que elijas el que mejor se adapte a tu flujo de trabajo.

**Pandas**

```python
import pandas as pd

# CSV
leads = pd.read_csv("data/candidate/csv/leads.csv")
spots = pd.read_csv("data/candidate/csv/spots.csv")

# Parquet (más rápido, más compacto)
leads = pd.read_parquet("data/candidate/parquet/leads.parquet")
spots = pd.read_parquet("data/candidate/parquet/spots.parquet")
```

**Polars**

```python
import polars as pl

# CSV
leads = pl.read_csv("data/candidate/csv/leads.csv")
spots = pl.read_csv("data/candidate/csv/spots.csv")

# Parquet (más rápido, más compacto)
leads = pl.read_parquet("data/candidate/parquet/leads.parquet")
spots = pl.read_parquet("data/candidate/parquet/spots.parquet")
```

### Calidad de los datos

Algunas columnas tienen valores faltantes y outliers. Esto es esperable en datos del mundo real. Decide cómo manejarlos y justifica tus decisiones. No existe una hoja de respuestas correcta para estas decisiones.

## Entregables

1. **Notebook** (.ipynb o HTML renderizado) con tu análisis completo y reproducible.
2. **One-pager** (PDF) con resumen ejecutivo para audiencias de Producto y C-Level.
3. **Slides** (PDF, 5–8 diapositivas) con hallazgos clave para una presentación de 15 minutos.
4. **Prompt de IA** que usaste, incluido como bloque de texto en el notebook.

## Tiempo

Esperamos que tome entre 6 y 8 horas. No esperamos infraestructura lista para producción. Sí esperamos un análisis sólido, bien comunicado y con visión de escalabilidad.

## Tips

- Los datos son sintéticos, diseñados para que encuentres patrones realistas. No busques relaciones perfectas.
- Hay valores faltantes y outliers colocados deliberadamente. Tus decisiones sobre cómo manejarlos son parte de la evaluación.
- Algunas columnas son trampas de leakage. Detectarlas es parte del ejercicio.
- La pregunta de producto importa tanto como el modelo. No la dejes para el final.
- Usa un LLM. El uso de IA es parte explícita de la evaluación.

Mucha suerte, y diviértete con el reto.
