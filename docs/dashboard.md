# Dashboard interactivo de DYNAMO

Página de Streamlit para explorar ventas históricas y comparar recomendadores con los reportes del equipo. Funciona sin API y sin cargar el bundle del modelo.

## Ejecutar

Desde la raíz del repositorio:

```bash
pip install -r requirements.txt
streamlit run app/pages/1_Dashboard.py
```

La comparación de modelos funciona con los CSV que ya están versionados en `reports/`. Para explorar negocio, preparar los datos locales:

```bash
# Copiar los 9 CSV de Olist a data/raw/, o usar el descargador del equipo:
python -m src.data.download_data
python -m src.data.make_interactions
```

Con el PR #11 de Nicolás integrado, ejecutar `streamlit run app/app.py`: Streamlit descubre automáticamente la página `Dashboard` en `app/pages/`. No es necesario cambiar la interfaz ni la API de Nicolás. La API solo es necesaria para usar el recomendador, no para este dashboard.

## Interacciones

- Negocio: rango de fechas inclusivo, categoría, estado del cliente y cantidad de categorías del ranking. KPIs, serie mensual, ranking por ventas, productos y descargas CSV.
- Modelos: seleccionar segmento (`all`/`warm`), K y modelos; comparar HitRate, cobertura y tabla completa; inspeccionar intervalos de HitRate@10 y diferencias pareadas, y descargar los resultados seleccionados.
- Metodología: definiciones, decisiones del modelo y limitaciones de la evaluación.

## Definiciones

- **Ventas de productos:** `price * quantity`, porque el pipeline agrega el precio unitario medio de productos repetidos en un pedido. No incluye flete, pagos cobrados ni beneficio.
- **Pedidos:** identificadores distintos con productos en la selección. Si se filtra por categoría, la venta por pedido incluye solo sus productos.
- **Clientes que recompran:** clientes con más de un pedido distinto en la selección; no equivale a usuarios con más de una fila de interacción ni a cold start temporal.
- **Estado:** geografía del pedido mediante `customer_id` transaccional. Si faltan los CSV de orders/customers, se muestra `Sin dato`; los demás análisis siguen disponibles.
- **Modelos:** métricas guardadas sobre el test histórico; los filtros de negocio no las recalculan. Los intervalos guardados solo corresponden a HitRate@10. NDCG está entre 0 y 1; las demás métricas se presentan como porcentaje.
- **Incertidumbre:** usar diferencias pareadas para evaluar acierto. No inferir significancia por el solapamiento de intervalos individuales ni afirmar aumento de ventas a partir de HitRate.

## Verificar

```bash
python -m pytest -q
```

Los tests cubren cantidades, conteo único de pedidos/clientes, filtros inclusivos, geografía por pedido, selección vacía, ausencia de geografía, duplicados que multiplicarían las ventas y separación de K/segmentos/intervalos.

## Compartir

La entrada de despliegue independiente en Streamlit Community Cloud es `app/pages/1_Dashboard.py`. Sin datos locales, la app ofrece la comparación de modelos y explica cómo habilitar negocio. Los CSV y parquet no se suben automáticamente: para publicar también negocio, definir con el equipo una fuente de datos reproducible. No se incluyen datos ni credenciales en este cambio.


### Despliegue público

https://dynamo-olist-dashboard.streamlit.app/

La instancia usa el fork `Palmereitor/dynamo-recsys-olist`, rama
`feature/dashboard-interactivo`. Si no encuentra el parquet local, descarga
la versión 2 del dataset público de Olist desde Kaggle, lee solamente los seis
CSV necesarios y aplica `build_interactions`. No requiere credenciales ni
versionar los datos. La tabla resultante se guarda en la caché de Streamlit;
la primera apertura después de un reinicio puede tardar aproximadamente un minuto.
Las aperturas siguientes reutilizan la caché. Si Kaggle no responde se muestra
un error y la comparación de modelos sigue disponible.

La carga local sigue siendo preferente. La red se habilita explícitamente con
`load_business(root, allow_download=True)` solo en la página de Streamlit.
