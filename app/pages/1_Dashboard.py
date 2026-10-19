"""Página automática de app/app.py; también funciona como entrada independiente."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import altair as alt
import pandas as pd
import streamlit as st

from src.dashboard_data import (
    business_summary, category_sales, filter_business, load_business,
    load_confidence, load_metrics, monthly_sales, product_sales,
    select_confidence, select_metrics,
)


LABELS = {
    "pop_global (baseline)": "Popularidad global",
    "pop_categoria": "Popularidad por categoría",
    "pop_reciente_30d": "Popularidad reciente (30 días)",
    "item2item_solo_cocompra": "Solo co-compra",
    "item2item_hibrido": "Híbrido",
    "svd_colaborativo": "SVD (4 factores)",
}
BLUE, ACCENT = "#176B87", "#D97706"


@st.cache_data(show_spinner=False)
def business_data(signature):
    return load_business(ROOT, allow_download=True)


def file_signature(paths):
    return tuple((str(p), p.stat().st_mtime_ns if p.exists() else None) for p in paths)


def money(value):
    return f"R$ {value:,.2f}"


def download(df, label, filename):
    st.download_button(label, df.to_csv(index=False).encode("utf-8-sig"),
                       filename, "text/csv")


def render_business():
    st.subheader("Ventas y catálogo")
    st.caption("Compras históricas válidas de Olist. Importes en reales brasileños (BRL), sin flete.")
    try:
        paths = [ROOT / "data/processed/interactions.parquet",
                 ROOT / "data/raw/olist_orders_dataset.csv",
                 ROOT / "data/raw/olist_customers_dataset.csv"]
        with st.spinner("Cargando Olist… La primera apertura puede tardar alrededor de un minuto."):
            df = business_data(file_signature(paths))
    except FileNotFoundError:
        st.info("Para explorar el negocio, coloca los CSV de Olist en data/raw/ y ejecuta "
                "python -m src.data.make_interactions. La comparación de modelos ya puede consultarse.")
        return
    except (ValueError, KeyError) as exc:
        st.error(f"No se pudo leer la tabla de negocio: {exc}")
        return
    if df.empty:
        st.info("La tabla de interacciones está vacía.")
        return

    st.caption("Fuente: [Olist · dataset público, versión 2](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce/versions/2). "
               "Limpieza aplicada con el pipeline del proyecto; no son datos en tiempo real.")
    first, last = df["purchase_ts"].min().date(), df["purchase_ts"].max().date()
    with st.expander("Filtros de negocio", expanded=True):
        dates = st.date_input("Periodo de compras", (first, last), min_value=first,
                              max_value=last, format="DD/MM/YYYY")
        left, right = st.columns(2)
        categories = left.multiselect("Categorías", sorted(df["category"].unique()),
                                      help="Vacío significa todas las categorías.")
        states = right.multiselect("Estado del cliente", sorted(df["customer_state"].unique()),
                                    help="Vacío significa todos los estados; es la ubicación del pedido.")
        if df["customer_state"].eq("Sin dato").all():
            st.caption("Ubicación no disponible: agrega los CSV de orders y customers para filtrar por estado.")
    if len(dates) != 2:
        st.info("Selecciona una fecha inicial y una final.")
        return
    filtered = filter_business(df, *dates, categories=categories or None, states=states or None)
    if filtered.empty:
        st.info("No hay compras para esta combinación de filtros. Prueba otro periodo o categoría.")
        return
    summary = business_summary(filtered)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Ventas de productos", money(summary["sales_brl"]))
    c2.metric("Pedidos con productos seleccionados", f"{summary['orders']:,}")
    c3.metric("Clientes únicos", f"{summary['customers']:,}")
    c4.metric("Productos distintos", f"{summary['products']:,}")
    st.caption(f"{summary['units']:,} unidades · Venta seleccionada por pedido: "
               f"{money(summary['sales_per_order_brl'])} · Clientes con más de un pedido "
               f"en esta selección: {summary['repeat_customers_pct']:.2f}%.")
    st.caption("Ventas = precio unitario medio × cantidad de cada interacción. No son pagos cobrados "
               "ni beneficio. Al filtrar categorías, el importe por pedido incluye solo sus productos.")

    monthly = monthly_sales(filtered)
    st.markdown("#### Evolución mensual de ventas")
    line = alt.Chart(monthly).mark_line(point=True, color=BLUE).encode(
        x=alt.X("month:T", title="Mes de compra"),
        y=alt.Y("sales_brl:Q", title="Ventas de productos (BRL)", scale=alt.Scale(zero=True)),
        tooltip=[alt.Tooltip("month:T", title="Mes", format="%Y-%m"),
                 alt.Tooltip("sales_brl:Q", title="Ventas (BRL)", format=",.2f"),
                 alt.Tooltip("orders:Q", title="Pedidos", format=",d")],
    ).properties(height=270).interactive()
    st.altair_chart(line, width="stretch")

    st.markdown("#### Categorías con más ventas")
    top_n = st.slider("Cantidad de categorías a mostrar", 5, 25, 10)
    ranking = category_sales(filtered)
    bars = alt.Chart(ranking.head(top_n)).mark_bar(color=BLUE).encode(
        y=alt.Y("category:N", sort="-x", title="Categoría"),
        x=alt.X("sales_brl:Q", title="Ventas de productos (BRL)", scale=alt.Scale(zero=True)),
        tooltip=[alt.Tooltip("category:N", title="Categoría"),
                 alt.Tooltip("sales_brl:Q", title="Ventas (BRL)", format=",.2f"),
                 alt.Tooltip("units:Q", title="Unidades", format=",d")],
    ).properties(height=max(240, top_n * 23))
    st.altair_chart(bars, width="stretch")
    download(ranking, "Descargar ventas por categoría", "dynamo_ventas_categorias.csv")

    st.markdown("#### Productos más vendidos por importe")
    products = product_sales(filtered).head(20).rename(columns={
        "product_id": "Producto", "category": "Categoría", "sales_brl": "Ventas (BRL)",
        "units": "Unidades", "buyers": "Compradores únicos",
    })
    st.dataframe(products, hide_index=True, width="stretch")
    download(monthly, "Descargar evolución mensual", "dynamo_ventas_mensuales.csv")


def metric_chart(selected, field, title):
    data = selected.assign(model_label=selected["model"].map(LABELS).fillna(selected["model"]))
    return alt.Chart(data).mark_bar().encode(
        y=alt.Y("model_label:N", sort="-x", title=None),
        x=alt.X(f"{field}:Q", title=title, axis=alt.Axis(format=".2%"),
                scale=alt.Scale(zero=True)),
        color=alt.condition(alt.datum.model == "item2item_hibrido", alt.value(ACCENT), alt.value(BLUE)),
        tooltip=[alt.Tooltip("model_label:N", title="Modelo"),
                 alt.Tooltip(f"{field}:Q", title=title, format=".3%"),
                 alt.Tooltip("n_users:Q", title="Usuarios evaluables", format=",d")],
    ).properties(height=260)


def render_models():
    st.subheader("Comparación de modelos")
    st.caption("Evaluación offline: test de junio a agosto de 2018. Los filtros de negocio no "
               "recalculan estos resultados. Las métricas provienen de los CSV del repositorio.")
    try:
        metrics = load_metrics(ROOT)
        intervals = load_confidence(ROOT)
    except FileNotFoundError:
        st.info("No hay reportes de modelos. Genera reports/model_comparison.csv con "
                "python -m src.models.train_compare.")
        return
    except ValueError as exc:
        st.error(str(exc))
        return
    if metrics.empty:
        st.info("El reporte de comparación no contiene resultados.")
        return

    left, right = st.columns(2)
    segments = list(metrics["segment"].drop_duplicates())
    segment = left.selectbox("Usuarios evaluados", segments,
                             format_func=lambda s: {"all": "Todos", "warm": "Con historial (warm)"}.get(s, s))
    ks = sorted(int(k) for k in metrics["k"].unique())
    k = right.selectbox("Top-K evaluado", ks, index=ks.index(10) if 10 in ks else 0)
    available = list(metrics.loc[(metrics["segment"] == segment) & (metrics["k"] == k), "model"])
    models = st.multiselect("Modelos a comparar", available, default=available,
                            format_func=lambda m: LABELS.get(m, m))
    if not models:
        st.info("Selecciona al menos un modelo para comparar.")
        return
    selected = select_metrics(metrics, segment, k, models)
    st.caption(f"{int(selected['n_users'].iloc[0]):,} usuarios evaluables. "
               "Warm significa que ya compraron en train; el resto no tiene historial conocido en train.")
    if segment == "warm":
        st.info("El segmento con historial es pequeño. Lee las diferencias junto con sus intervalos de confianza.")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"#### Acierto: HitRate@{k}")
        st.altair_chart(metric_chart(selected, "hit_rate@k", "Usuarios con al menos un acierto"),
                        width="stretch")
    with col2:
        st.markdown("#### Variedad: cobertura del catálogo")
        st.altair_chart(metric_chart(selected, "coverage", "Fracción del catálogo recomendado"),
                        width="stretch")

    table = selected[["model", "n_users", "precision@k", "recall@k", "hit_rate@k", "ndcg@k", "coverage"]].copy()
    table["model"] = table["model"].map(LABELS).fillna(table["model"])
    for field in ["precision@k", "recall@k", "hit_rate@k", "coverage"]:
        table[field] = table[field].map(lambda x: f"{x:.3%}")
    table = table.rename(columns={"model": "Modelo", "n_users": "Usuarios",
                                  "precision@k": f"Precision@{k}", "recall@k": f"Recall@{k}",
                                  "hit_rate@k": f"HitRate@{k}", "ndcg@k": f"NDCG@{k}",
                                  "coverage": "Cobertura"})
    st.dataframe(table, hide_index=True, width="stretch")
    st.caption("NDCG se expresa entre 0 y 1. Cobertura utiliza el catálogo del entrenamiento, "
               "también en warm. HitRate no es conversión ni aumento de ventas.")
    download(selected, "Descargar comparación seleccionada", "dynamo_comparacion_modelos.csv")

    ci = select_confidence(intervals, segment, k, models)
    st.markdown("#### Incertidumbre del acierto")
    if k != 10:
        st.caption("Los intervalos guardados solo corresponden a HitRate@10. Selecciona K=10 para verlos.")
    elif ci.empty:
        st.info("No hay intervalos guardados para esta selección.")
    else:
        chart_data = ci.assign(model_label=ci["comparacion"].map(LABELS).fillna(ci["comparacion"]))
        base = alt.Chart(chart_data).encode(y=alt.Y("model_label:N", title=None))
        rules = base.mark_rule(color=BLUE, strokeWidth=2).encode(
            x=alt.X("ic95_bajo:Q", title="HitRate@10 · IC 95%", axis=alt.Axis(format=".2%"),
                    scale=alt.Scale(zero=True)), x2="ic95_alto:Q")
        points = base.mark_point(color=BLUE, filled=True, size=70).encode(
            x="estimado:Q", tooltip=["model_label:N",
                                     alt.Tooltip("estimado:Q", format=".3%"),
                                     alt.Tooltip("ic95_bajo:Q", format=".3%"),
                                     alt.Tooltip("ic95_alto:Q", format=".3%")])
        st.altair_chart((rules + points).properties(height=230), width="stretch")
        differences = intervals.loc[(intervals["segment"] == segment)
                                    & intervals["comparacion"].str.contains(" - ")].copy()
        differences = differences.loc[differences["comparacion"].map(
            lambda pair: all(name in models for name in pair.split(" - ")))]
        if not differences.empty:
            comparison = st.selectbox("Diferencia pareada de HitRate@10", differences["comparacion"].tolist())
            row = differences.loc[differences["comparacion"] == comparison].iloc[0]
            st.write(f"Diferencia: **{row['estimado'] * 100:+.2f} pp** · "
                     f"IC 95% **[{row['ic95_bajo'] * 100:+.2f}; {row['ic95_alto'] * 100:+.2f}] pp**.")
            if row["ic95_bajo"] <= 0 <= row["ic95_alto"]:
                st.info("El intervalo incluye cero: no demuestra una diferencia de acierto al 95%.")
            else:
                st.write("El intervalo no incluye cero para esta comparación y este periodo de evaluación.")
        st.caption("Los intervalos son bootstrap por usuario. La significancia se evalúa con "
                   "diferencias pareadas, no por el solapamiento visual de intervalos individuales.")


def main():
    st.set_page_config(page_title="Dashboard | DYNAMO", page_icon="📊", layout="wide")
    st.title("DYNAMO · Dashboard de Olist")
    st.caption("Explora el negocio y la evidencia que sustenta la elección del recomendador.")
    business, models, methodology = st.tabs(["Negocio", "Modelos", "Cómo leer los datos"])
    with business:
        render_business()
    with models:
        render_models()
    with methodology:
        st.subheader("Alcance y decisiones")
        st.markdown("""
**Negocio.** Usa `interactions.parquet`, generado por el pipeline del equipo. Excluye
pedidos cancelados, no disponibles y creados. Las ventas suman precio × cantidad;
no incluyen flete, pagos ni beneficios. La geografía se vincula al pedido, no a una
ubicación arbitraria del cliente. Los pedidos y clientes se cuentan sin duplicarlos.

**Modelos.** Usa `model_comparison.csv` y `confidence_intervals.csv`. El entrenamiento
termina antes del 1 de junio de 2018; el test abarca junio–agosto. La validación
marzo–mayo se usa para elegir hiperparámetros sin mirar el test. Los filtros de esta
página seleccionan resultados existentes y no vuelven a entrenar modelos.

**Decisión.** El equipo eligió el híbrido por sus resultados puntuales y mayor cobertura.
El acierto observado es bajo y sus diferencias no son concluyentes al 95% en los
reportes actuales. El SVD aporta una alternativa contrastada con el mismo protocolo.
La popularidad reciente explica gran parte del acierto global; la categoría aporta
en clientes con historial. El dataset tiene poca recompra y una matriz muy dispersa.

**Siguiente validación.** Medir impacto mediante una prueba A/B e incorporar señales
de navegación, búsquedas y carrito. Los resultados históricos no prueban un aumento
de ventas ni el rendimiento en producción.
""")
        st.markdown("[Repositorio del equipo](https://github.com/DynamoConsultoriaDataSolutions/dynamo-recsys-olist)")
        st.caption("La página funciona sin API y sin cargar el modelo; solo lee los datos y reportes locales.")


if __name__ == "__main__":
    main()
