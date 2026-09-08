#!/usr/bin/env python3
"""
generate_sales_charts.py
========================
Script automatizado de generación de gráficos visuales en alta resolución (PNG)
basado en analyze_sales.py y las tablas del Data Warehouse.

Genera 10 visualizaciones ejecutivas orientadas a sustentar la problemática
operativa, logística y financiera de la demanda concentrada por promociones:

 1. 01_distribucion_semanal_global.png       - Facturas, Unidades y Recaudación Semanal.
 2. 02_indice_estres_pico_vs_valle.png        - Ratios de disparidad extrema (Martes vs Jueves).
 3. 03_economia_ticket_aov_upt.png           - Valor promedio (AOV) y saturación de carritos (UPT).
 4. 04_segmentacion_mayoristas_vs_privados.png - Canibalización de promociones por mayoristas.
 5. 05_curva_carga_vs_capacidad_optima.png   - Curva de demanda vs capacidad (Demand Smoothing).
 6. 06_concentracion_top_categorias.png       - Sobredemanda en categorías clave en días promo.
 7. 07_costo_financiero_margen_resignado.png  - Descuentos otorgados y dinero dejado sobre la mesa.
 8. 08_dispersion_tickets_boxplot.png         - Dispersión y asimetría de montos por factura.
 9. 09_heatmap_semaforo_operativo.png        - Matriz ejecutiva de calor y estrés operativo.
10. 10_serie_temporal_patron_recurrente.png   - Demostración de persistencia semana a semana.
"""

import os
import sys
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")  # Backend headless sin necesidad de display gráfico
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

# Configuración de directorio base y datos
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_DIR = os.path.join(BASE_DIR, "dataset")
OUTPUT_DIR = os.path.join(BASE_DIR, "charts")
os.makedirs(OUTPUT_DIR, exist_ok=True)

PURCHASES_FILE = os.path.join(DATASET_DIR, "purchases.csv")
INVOICE_ITEMS_FILE = os.path.join(DATASET_DIR, "invoice_items.csv")
PRODUCTS_FILE = os.path.join(DATASET_DIR, "products.csv")
CUSTOMERS_FILE = os.path.join(DATASET_DIR, "customers.csv")
DISCOUNTS_FILE = os.path.join(DATASET_DIR, "discounts.csv")

DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DAY_LABELS = [
    "Lunes",
    "Martes\n(30% OFF)",
    "Miércoles",
    "Jueves",
    "Viernes\n(25% OFF)",
    "Sábado",
    "Domingo"
]
DAY_LABELS_SHORT = ["Lun", "Mar\n(30%)", "Mié", "Jue", "Vie\n(25%)", "Sáb", "Dom"]

# Paleta corporativa armónica
COLOR_PROMO_TUE = "#E63946"  # Rojo intenso / alerta
COLOR_PROMO_FRI = "#F4A261"  # Naranja promocional
COLOR_REGULAR   = "#2A9D8F"  # Verde azulado / normal
COLOR_VALLEY    = "#6C757D"  # Gris apagado / valle ocioso
COLOR_WHOLESALE = "#1D3557"  # Azul marino profundo
COLOR_PRIVATE   = "#457B9D"  # Celeste azulado

DAY_COLORS = [
    COLOR_REGULAR,    # Lunes
    COLOR_PROMO_TUE,  # Martes
    COLOR_VALLEY,     # Miércoles
    "#9A031E",        # Jueves (valle extremo)
    COLOR_PROMO_FRI,  # Viernes
    COLOR_REGULAR,    # Sábado
    COLOR_REGULAR     # Domingo
]


def load_data():
    """Carga y unifica las entidades del Data Warehouse."""
    print("-> Cargando datasets...")
    purchases = pd.read_csv(PURCHASES_FILE)
    items = pd.read_csv(INVOICE_ITEMS_FILE)
    products = pd.read_csv(PRODUCTS_FILE)
    customers = pd.read_csv(CUSTOMERS_FILE)

    purchases["date"] = pd.to_datetime(purchases["date"])
    purchases["day_name"] = purchases["date"].dt.day_name()

    df = purchases.copy()
    df["price"] = items["price"]
    df["line_total"] = items["line_total"]

    # Enriquecer con categorías, precios base y tipo de cliente
    df = df.merge(
        products[["product_id", "category", "price"]].rename(columns={"price": "base_price"}),
        on="product_id",
        how="left"
    )
    df = df.merge(customers[["CustomerID", "customer_type"]], on="CustomerID", how="left")

    df["day_order"] = df["day_name"].apply(lambda d: DAY_ORDER.index(d) if d in DAY_ORDER else 99)

    # Cálculo de importe teórico sin descuento y descuento otorgado
    df["theoretical_total"] = df["quantity"] * df["base_price"].fillna(df["price"])
    df["discount_amount"] = (df["theoretical_total"] - df["line_total"]).clip(lower=0)

    print(f"-> Datos integrados: {len(df):,} registros unificados.")
    return df


def style_figure(fig, ax_list):
    """Aplica estética limpia y moderna a los ejes."""
    for ax in ax_list:
        ax.set_facecolor("#FAFAFC")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color("#BDC3C7")
        ax.spines["bottom"].set_color("#BDC3C7")
        ax.grid(axis="y", linestyle="--", alpha=0.4, color="#95A5A6")
    fig.patch.set_facecolor("#FFFFFF")


# ==============================================================================
# 1. DISTRIBUCIÓN SEMANAL GLOBAL (FACTURAS, UNIDADES Y RECAUDACIÓN)
# ==============================================================================
def plot_01_weekly_distribution(df):
    daily = df.groupby(["day_order", "day_name"]).agg(
        invoices=("InvoiceID", "nunique"),
        units=("quantity", "sum"),
        revenue=("line_total", "sum")
    ).reset_index().sort_values("day_order")

    fig, axes = plt.subplots(1, 3, figsize=(18, 5.5), sharex=False)
    style_figure(fig, axes)

    metrics = [
        ("invoices", "Afluencia de Clientes (Facturas)", axes[0], "{:,.0f}"),
        ("units", "Volumen Despachado (Unidades)", axes[1], "{:,.0f}"),
        ("revenue", "Recaudación Total ($ USD)", axes[2], "${:,.0f}")
    ]

    for col, title, ax, fmt in metrics:
        bars = ax.bar(DAY_LABELS, daily[col], color=DAY_COLORS, edgecolor="black", linewidth=0.6, width=0.65)
        ax.set_title(title, fontsize=13, fontweight="bold", pad=12, color="#1D3557")
        ax.tick_params(axis="x", labelsize=9.5)
        ax.tick_params(axis="y", labelsize=9)

        # Anotaciones en cada barra
        max_val = daily[col].max()
        for bar in bars:
            yval = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                yval + (max_val * 0.02),
                fmt.format(yval),
                ha="center",
                va="bottom",
                fontsize=8.5,
                fontweight="semibold",
                color="#212529"
            )
        ax.set_ylim(0, max_val * 1.15)

    fig.suptitle(
        "DISTRIBUCIÓN SEMANAL: DESBALANCE EN AFLUENCIA, VOLUMEN Y RECAUDACIÓN\n"
        "Martes y Viernes concentran el 41.1% de facturación y 49.0% del volumen físico, generando asfixia operativa.",
        fontsize=14, fontweight="bold", color="#0B132B", y=1.03
    )

    out_path = os.path.join(OUTPUT_DIR, "01_distribucion_semanal_global.png")
    plt.tight_layout()
    plt.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"  [OK] Guardado: {out_path}")


# ==============================================================================
# 2. ÍNDICE DE ESTRÉS PICO VS. VALLE (MARTES PROMO VS JUEVES VACÍO)
# ==============================================================================
def plot_02_bottleneck_ratios(df):
    daily = df.groupby(["day_order", "day_name"]).agg(
        invoices=("InvoiceID", "nunique"),
        units=("quantity", "sum"),
        revenue=("line_total", "sum")
    ).reset_index().sort_values("day_order")

    weekdays = daily[daily["day_name"].isin(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])]
    max_day = weekdays.loc[weekdays["revenue"].idxmax()]  # Martes
    min_day = weekdays.loc[weekdays["revenue"].idxmin()]  # Jueves

    ratios = {
        "Recaudación ($)": (max_day["revenue"] / min_day["revenue"], "$2.29M vs $61.5K"),
        "Afluencia (Facturas)": (max_day["invoices"] / min_day["invoices"], "6,869 vs 2,188 facturas"),
        "Carga Logística (Unidades)": (max_day["units"] / min_day["units"], "1.72M vs 14.1K unidades")
    }

    fig, ax = plt.subplots(figsize=(10.5, 5.2))
    style_figure(fig, [ax])

    categories = list(ratios.keys())
    values = [ratios[c][0] for c in categories]
    subtitles = [ratios[c][1] for c in categories]
    colors = ["#E76F51", "#2A9D8F", "#E63946"]

    bars = ax.barh(categories, values, color=colors, edgecolor="black", linewidth=0.8, height=0.55)

    for bar, val, sub in zip(bars, values, subtitles):
        ax.text(
            val + 1.5,
            bar.get_y() + bar.get_height() / 2,
            f"{val:.1f}x veces más en el Pico\n({sub})",
            va="center",
            ha="left",
            fontsize=10.5,
            fontweight="bold",
            color="#1D3557"
        )

    ax.set_xlim(0, max(values) * 1.35)
    ax.set_xlabel("Ratio de Disparidad (Pico Hábil / Valle Hábil)", fontsize=11, fontweight="bold", color="#1D3557")
    ax.set_title(
        "EL ABISMO OPERATIVO: RATIO DE ESTRÉS PICO (MARTES) VS. VALLE (JUEVES)\n"
        "La empresa mantiene costos fijos diarios idénticos, pero atiende 122 veces más volumen los martes.",
        fontsize=13, fontweight="bold", color="#0B132B", pad=15
    )

    out_path = os.path.join(OUTPUT_DIR, "02_indice_estres_pico_vs_valle.png")
    plt.tight_layout()
    plt.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"  [OK] Guardado: {out_path}")


# ==============================================================================
# 3. ECONOMÍA DEL TICKET: TICKET PROMEDIO (AOV) Y UNIDADES POR CARRITO (UPT)
# ==============================================================================
def plot_03_ticket_economics(df):
    invoice_level = df.groupby(["InvoiceID", "day_order", "day_name"]).agg(
        invoice_revenue=("line_total", "sum"),
        invoice_units=("quantity", "sum")
    ).reset_index()

    ticket_stats = invoice_level.groupby(["day_order", "day_name"]).agg(
        aov=("invoice_revenue", "mean"),
        upt=("invoice_units", "mean")
    ).reset_index().sort_values("day_order")

    fig, ax1 = plt.subplots(figsize=(11, 5.5))
    ax2 = ax1.twinx()

    style_figure(fig, [ax1])
    ax2.spines["top"].set_visible(False)
    ax2.spines["left"].set_visible(False)

    x = np.arange(len(DAY_LABELS))
    width = 0.38

    bars = ax1.bar(x - width / 2, ticket_stats["aov"], width, label="Ticket Promedio (AOV $)", color="#1D3557", edgecolor="black", linewidth=0.6)
    lines = ax2.bar(x + width / 2, ticket_stats["upt"], width, label="Unidades / Ticket (UPT)", color="#E63946", edgecolor="black", linewidth=0.6)

    ax1.set_xticks(x)
    ax1.set_xticklabels(DAY_LABELS, fontsize=9.5)
    ax1.set_ylabel("Ticket Promedio AOV ($ USD)", fontsize=11, fontweight="bold", color="#1D3557")
    ax2.set_ylabel("Unidades por Carrito (UPT)", fontsize=11, fontweight="bold", color="#E63946")

    # Etiquetas sobre barras
    for bar in bars:
        h = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width() / 2, h + 8, f"${h:.0f}", ha="center", va="bottom", fontsize=8.5, fontweight="bold", color="#1D3557")
    for bar in lines:
        h = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width() / 2, h + 5, f"{h:.1f} u.", ha="center", va="bottom", fontsize=8.5, fontweight="bold", color="#E63946")

    ax1.set_ylim(0, ticket_stats["aov"].max() * 1.25)
    ax2.set_ylim(0, ticket_stats["upt"].max() * 1.25)

    # Unir leyendas
    lines_1, labels_1 = ax1.get_legend_handles_labels()
    lines_2, labels_2 = ax2.get_legend_handles_labels()
    ax1.legend(lines_1 + lines_2, labels_1 + labels_2, loc="upper left", frameon=True, facecolor="white", edgecolor="#D1D5DB")

    plt.title(
        "ANATOMÍA DEL CARRITO: IMPACTO DE LAS PROMOCIONES EN AOV Y UPT\n"
        "En días promocionales el UPT se dispara a ~250 unidades/ticket, saturando las líneas de caja y empaque.",
        fontsize=13, fontweight="bold", color="#0B132B", pad=15
    )

    out_path = os.path.join(OUTPUT_DIR, "03_economia_ticket_aov_upt.png")
    plt.tight_layout()
    plt.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"  [OK] Guardado: {out_path}")


# ==============================================================================
# 4. SEGMENTACIÓN DE CLIENTES: MAYORISTAS VS PARTICULARES
# ==============================================================================
def plot_04_customer_segmentation(df):
    seg = df.groupby(["day_order", "day_name", "customer_type"]).agg(
        revenue=("line_total", "sum")
    ).reset_index()

    piv = seg.pivot(index=["day_order", "day_name"], columns="customer_type", values="revenue").fillna(0)
    piv = piv.reindex([(i, DAY_ORDER[i]) for i in range(7)])

    fig, ax = plt.subplots(figsize=(11.5, 5.5))
    style_figure(fig, [ax])

    ind = np.arange(len(DAY_LABELS))
    whol = piv["wholesaler"].values
    priv = piv["private"].values

    p1 = ax.bar(ind, priv, label="Consumidores Particulares (Private)", color="#457B9D", edgecolor="black", linewidth=0.6, width=0.6)
    p2 = ax.bar(ind, whol, bottom=priv, label="Clientes Mayoristas (Wholesaler)", color="#1D3557", edgecolor="black", linewidth=0.6, width=0.6)

    # Anotar porcentaje mayorista sobre cada barra
    for i in range(len(ind)):
        total_day = priv[i] + whol[i]
        pct = (whol[i] / total_day * 100) if total_day > 0 else 0
        ax.text(
            ind[i],
            total_day + 40000,
            f"{pct:.1f}% Mayorista\nTotal: ${total_day/1000:,.0f}K",
            ha="center",
            va="bottom",
            fontsize=8.5,
            fontweight="bold",
            color="#1D3557"
        )

    ax.set_xticks(ind)
    ax.set_xticklabels(DAY_LABELS, fontsize=9.5)
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda y, _: f"${y*1e-6:.1f}M"))
    ax.set_ylabel("Recaudación Total ($ USD)", fontsize=11, fontweight="bold", color="#1D3557")
    ax.set_ylim(0, max(priv + whol) * 1.25)
    ax.legend(loc="upper left", frameon=True, facecolor="white", edgecolor="#D1D5DB", fontsize=10)

    plt.title(
        "SEGMENTACIÓN COMERCIAL: CANIBALIZACIÓN DE DESCUENTOS POR MAYORISTAS\n"
        "Los mayoristas generan más del 76% de las ventas los martes promo, mientras que los jueves se esfuman por completo.",
        fontsize=13, fontweight="bold", color="#0B132B", pad=15
    )

    out_path = os.path.join(OUTPUT_DIR, "04_segmentacion_mayoristas_vs_privados.png")
    plt.tight_layout()
    plt.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"  [OK] Guardado: {out_path}")


# ==============================================================================
# 5. DEMAND SMOOTHING: CURVA DE CARGA REAL VS. CAPACIDAD BALANCEADA
# ==============================================================================
def plot_05_load_smoothing(df):
    daily = df.groupby(["day_order", "day_name"]).agg(
        units=("quantity", "sum")
    ).reset_index().sort_values("day_order")

    units = daily["units"].values
    mean_units = units.mean()
    ind = np.arange(len(DAY_LABELS))

    fig, ax = plt.subplots(figsize=(12, 5.5))
    style_figure(fig, [ax])

    # Línea de demanda real
    ax.plot(ind, units, color="#E63946", marker="o", linewidth=2.8, markersize=8, label="Volumen Real Despachado (Unidades)", zorder=4)

    # Línea de capacidad balanceada promedio
    ax.axhline(mean_units, color="#2A9D8F", linestyle="--", linewidth=2.2, label=f"Capacidad Operativa Óptima Balanceada ({mean_units:,.0f} u.)", zorder=3)

    # Sombreado de sobrecarga vs capacidad ociosa
    ax.fill_between(ind, units, mean_units, where=(units >= mean_units), interpolate=True, color="#E63946", alpha=0.25, label="Zona de Sobrecarga / Horas Extra / Riesgo de Colapso")
    ax.fill_between(ind, units, mean_units, where=(units < mean_units), interpolate=True, color="#ADB5BD", alpha=0.30, label="Zona de Capacidad Ociosa / Desperdicio de Costo Fijo")

    for i, txt in enumerate(units):
        diff = txt - mean_units
        sign = "+" if diff > 0 else ""
        ax.annotate(
            f"{txt:,.0f}\n({sign}{diff/mean_units*100:.0f}%)",
            (ind[i], units[i]),
            textcoords="offset points",
            xytext=(0, 10 if diff > 0 else -25),
            ha="center",
            fontsize=8.5,
            fontweight="bold",
            color="#0B132B"
        )

    ax.set_xticks(ind)
    ax.set_xticklabels(DAY_LABELS, fontsize=10)
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda y, _: f"{y*1e-6:.2f}M u."))
    ax.set_ylabel("Volumen de Mercadería (Unidades)", fontsize=11, fontweight="bold", color="#1D3557")
    ax.set_ylim(0, units.max() * 1.25)
    ax.legend(loc="upper left", frameon=True, facecolor="white", edgecolor="#D1D5DB", fontsize=9.5)

    plt.title(
        "NIVELACIÓN DE DEMANDA (DEMAND SMOOTHING): DEMANDA REAL VS. CAPACIDAD BALANCEADA\n"
        "El 'efecto látigo' semanal genera un exceso de hasta +86% sobre capacidad un día y una caída de -98% dos días después.",
        fontsize=13, fontweight="bold", color="#0B132B", pad=15
    )

    out_path = os.path.join(OUTPUT_DIR, "05_curva_carga_vs_capacidad_optima.png")
    plt.tight_layout()
    plt.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"  [OK] Guardado: {out_path}")


# ==============================================================================
# 6. CONCENTRACIÓN POR TOP CATEGORÍAS (DÍAS PROMO VS REGULARES)
# ==============================================================================
def plot_06_top_categories(df):
    df["is_promo_day"] = df["day_name"].isin(["Tuesday", "Friday"])
    cat_summary = df.groupby(["category", "is_promo_day"])["line_total"].sum().unstack().fillna(0)
    cat_summary.columns = ["Sin Descuento", "Con Descuento"]
    cat_summary["Total"] = cat_summary.sum(axis=1)
    cat_summary["pct_promo"] = (cat_summary["Con Descuento"] / cat_summary["Total"]) * 100
    top10 = cat_summary.sort_values(by="Total", ascending=True).tail(10)

    fig, ax = plt.subplots(figsize=(12, 6.2))
    style_figure(fig, [ax])

    y_pos = np.arange(len(top10))
    p1 = ax.barh(y_pos, top10["Sin Descuento"], color="#457B9D", edgecolor="black", linewidth=0.5, height=0.6, label="Días Regulares Sin Promo (5 días)")
    p2 = ax.barh(y_pos, top10["Con Descuento"], left=top10["Sin Descuento"], color="#E63946", edgecolor="black", linewidth=0.5, height=0.6, label="Días Promocionales Mar/Vie (2 días)")

    for i, (idx, r) in enumerate(top10.iterrows()):
        total = r["Total"]
        pct = r["pct_promo"]
        ax.text(
            total + 25000,
            i,
            f"${total/1e6:.2f}M  ({pct:.1f}% en promo)",
            va="center",
            ha="left",
            fontsize=9,
            fontweight="bold",
            color="#1D3557"
        )

    ax.set_yticks(y_pos)
    ax.set_yticklabels(top10.index, fontsize=10)
    ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"${x*1e-6:.1f}M"))
    ax.set_xlabel("Recaudación Total ($ USD)", fontsize=11, fontweight="bold", color="#1D3557")
    ax.set_xlim(0, top10["Total"].max() * 1.30)
    ax.legend(loc="lower right", frameon=True, facecolor="white", edgecolor="#D1D5DB", fontsize=10)

    plt.title(
        "CONCENTRACIÓN POR CATEGORÍA: DÍAS DE PROMOCIÓN VS. DÍAS REGULARES\n"
        "Categorías de alto ticket (Hogar, Cocina, Jardín) concentran más del 40%-52% de su venta semanal en solo 2 días.",
        fontsize=13, fontweight="bold", color="#0B132B", pad=15
    )

    out_path = os.path.join(OUTPUT_DIR, "06_concentracion_top_categorias.png")
    plt.tight_layout()
    plt.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"  [OK] Guardado: {out_path}")


# ==============================================================================
# 7. EL COSTO DEL DESCUENTO: MARGEN RESIGNADO POR SEGMENTO
# ==============================================================================
def plot_07_discount_cost(df):
    tue_fri = df[df["day_name"].isin(["Tuesday", "Friday"])]
    disc_summary = tue_fri.groupby(["day_name", "customer_type"])["discount_amount"].sum().unstack()

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5))
    style_figure(fig, [ax1, ax2])

    # Subplot 1: Barras por Día y Segmento
    x = np.arange(2)
    labels = ["Martes (30% OFF)", "Viernes (25% OFF)"]
    whol_vals = [disc_summary.loc["Tuesday", "wholesaler"], disc_summary.loc["Friday", "wholesaler"]]
    priv_vals = [disc_summary.loc["Tuesday", "private"], disc_summary.loc["Friday", "private"]]

    b1 = ax1.bar(x, priv_vals, color="#457B9D", label="Beneficio a Particulares", edgecolor="black", linewidth=0.6, width=0.45)
    b2 = ax1.bar(x, whol_vals, bottom=priv_vals, color="#1D3557", label="Subsidio a Mayoristas", edgecolor="black", linewidth=0.6, width=0.45)

    for i in range(2):
        tot = whol_vals[i] + priv_vals[i]
        pct_w = (whol_vals[i] / tot) * 100
        ax1.text(x[i], tot + 20000, f"${tot/1000:,.0f}K\n({pct_w:.1f}% Mayorista)", ha="center", va="bottom", fontsize=9.5, fontweight="bold", color="#1D3557")

    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, fontsize=10.5)
    ax1.yaxis.set_major_formatter(ticker.FuncFormatter(lambda y, _: f"${y/1000:,.0f}K"))
    ax1.set_ylabel("Monto de Descuento Otorgado ($ USD)", fontsize=11, fontweight="bold", color="#1D3557")
    ax1.set_ylim(0, max([w + p for w, p in zip(whol_vals, priv_vals)]) * 1.25)
    ax1.legend(loc="upper left", frameon=True, facecolor="white", edgecolor="#D1D5DB")
    ax1.set_title("Volumen de Descuento Resignado por Día", fontsize=12, fontweight="bold", color="#1D3557")

    # Subplot 2: Dona Total
    total_whol = sum(whol_vals)
    total_priv = sum(priv_vals)
    total_disc = total_whol + total_priv

    wedges, texts, autotexts = ax2.pie(
        [total_whol, total_priv],
        labels=["Mayoristas\n(Wholesalers)", "Particulares\n(Privates)"],
        autopct="%1.1f%%",
        startangle=140,
        colors=["#1D3557", "#457B9D"],
        wedgeprops=dict(width=0.4, edgecolor="white", linewidth=2),
        textprops=dict(fontsize=10.5, fontweight="bold")
    )
    for at in autotexts:
        at.set_color("white")
        at.set_fontsize(11)

    ax2.text(0, 0, f"${total_disc/1e6:.2f}M\nTOTAL\nRESIGNADO", ha="center", va="center", fontsize=10, fontweight="bold", color="#0B132B")
    ax2.set_title("Distribución Global del Margen Cedido", fontsize=12, fontweight="bold", color="#1D3557")

    fig.suptitle(
        "EL COSTO OCULTO DE LA PROMOCIÓN: $1.67M USD DE MARGEN RESIGNADO\n"
        "El 71.9% del descuento fue capturado por intermediarios mayoristas que revenden la mercadería.",
        fontsize=13, fontweight="bold", color="#0B132B", y=1.03
    )

    out_path = os.path.join(OUTPUT_DIR, "07_costo_financiero_margen_resignado.png")
    plt.tight_layout()
    plt.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"  [OK] Guardado: {out_path}")


# ==============================================================================
# 8. DISPERSIÓN DE FACTURAS (BOXPLOT EN ESCALA LOGARÍTMICA)
# ==============================================================================
def plot_08_invoice_dispersion(df):
    inv_totals = df.groupby(["InvoiceID", "day_order", "day_name"])["line_total"].sum().reset_index()

    data_by_day = [
        inv_totals[inv_totals["day_name"] == day]["line_total"].values
        for day in DAY_ORDER
    ]

    fig, ax = plt.subplots(figsize=(11.5, 5.8))
    style_figure(fig, [ax])

    bp = ax.boxplot(
        data_by_day,
        patch_artist=True,
        tick_labels=DAY_LABELS_SHORT,
        showmeans=True,
        meanline=True,
        flierprops=dict(marker=".", markerfacecolor="#E63946", markersize=3, alpha=0.35, markeredgecolor="none"),
        medianprops=dict(color="#0B132B", linewidth=1.5),
        meanprops=dict(color="#2A9D8F", linewidth=1.8, linestyle="--")
    )

    for patch, color in zip(bp["boxes"], DAY_COLORS):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
        patch.set_edgecolor("black")

    ax.set_yscale("log")
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda y, _: f"${int(y):,}"))
    ax.set_ylabel("Monto Facturado por Ticket ($ USD, Escala Log)", fontsize=11, fontweight="bold", color="#1D3557")

    # Leyenda indicativa
    ax.plot([], [], color="#0B132B", linewidth=1.5, label="Mediana")
    ax.plot([], [], color="#2A9D8F", linewidth=1.8, linestyle="--", label="Media (Promedio)")
    ax.legend(loc="upper right", frameon=True, facecolor="white", edgecolor="#D1D5DB")

    plt.title(
        "VARIABILIDAD Y DISPERSIÓN DEL GASTO POR TICKET (ESCALA LOGARÍTMICA)\n"
        "En días promo coexisten tickets masivos de mayoristas (> $10,000) con compras habituales, complicando la logística.",
        fontsize=13, fontweight="bold", color="#0B132B", pad=15
    )

    out_path = os.path.join(OUTPUT_DIR, "08_dispersion_tickets_boxplot.png")
    plt.tight_layout()
    plt.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"  [OK] Guardado: {out_path}")


# ==============================================================================
# 9. HEATMAP / SEMÁFORO EJECUTIVO DE ESTRÉS OPERATIVO
# ==============================================================================
def plot_09_heatmap_matrix(df):
    invoice_level = df.groupby(["InvoiceID", "day_order", "day_name", "customer_type"]).agg(
        line_total=("line_total", "sum"),
        quantity=("quantity", "sum")
    ).reset_index()

    daily = df.groupby(["day_order", "day_name"]).agg(
        invoices=("InvoiceID", "nunique"),
        units=("quantity", "sum"),
        revenue=("line_total", "sum"),
        discounts=("discount_amount", "sum")
    ).reset_index().sort_values("day_order")

    aov_upt = invoice_level.groupby(["day_order", "day_name"]).agg(
        aov=("line_total", "mean"),
        upt=("quantity", "mean")
    ).reset_index()

    whol_pct = df.groupby(["day_order", "day_name", "customer_type"])["line_total"].sum().unstack().fillna(0)
    whol_ratio = (whol_pct["wholesaler"] / whol_pct.sum(axis=1) * 100).values

    matrix_df = pd.DataFrame({
        "Afluencia (Facturas)": daily["invoices"],
        "Volumen (Unidades)": daily["units"],
        "Recaudación ($)": daily["revenue"],
        "Carga en Cajas (UPT)": aov_upt["upt"],
        "Margen Cedido ($)": daily["discounts"],
        "% Mayoristas": whol_ratio
    }, index=[d.replace("\n", " ") for d in DAY_LABELS])

    # Normalizar columnas entre 0 y 100 para mapa de calor
    norm_matrix = (matrix_df - matrix_df.min()) / (matrix_df.max() - matrix_df.min()) * 100

    fig, ax = plt.subplots(figsize=(12, 6.2))
    cax = ax.imshow(norm_matrix.T, cmap="YlOrRd", aspect="auto")

    ax.set_xticks(np.arange(len(DAY_LABELS)))
    ax.set_xticklabels([d.replace("\n", " ") for d in DAY_LABELS], fontsize=10, fontweight="bold")
    ax.set_yticks(np.arange(len(matrix_df.columns)))
    ax.set_yticklabels(matrix_df.columns, fontsize=11, fontweight="bold", color="#1D3557")

    # Imprimir valores reales dentro de cada celda
    for i in range(len(DAY_LABELS)):
        for j in range(len(matrix_df.columns)):
            val = matrix_df.iloc[i, j]
            col_name = matrix_df.columns[j]
            if "$" in col_name or "Margen" in col_name or "Recaudación" in col_name:
                txt = f"${val/1000:,.0f}K" if val >= 1000 else f"${val:.1f}"
            elif "%" in col_name:
                txt = f"{val:.1f}%"
            elif "UPT" in col_name:
                txt = f"{val:.1f} u."
            else:
                txt = f"{val:,.0f}"

            # Contraste de texto según el calor
            norm_val = norm_matrix.iloc[i, j]
            text_color = "white" if norm_val > 60 else "#0B132B"
            ax.text(i, j, txt, ha="center", va="center", fontsize=9.5, fontweight="bold", color=text_color)

    cbar = fig.colorbar(cax, ax=ax, orientation="vertical", pad=0.02)
    cbar.set_label("Índice de Estrés Operativo Relativo (0: Mínimo Valle / 100: Máximo Pico)", fontsize=10, fontweight="bold")

    plt.title(
        "SEMÁFORO EJECUTIVO DE ESTRÉS OPERATIVO Y COMERCIAL POR DÍA\n"
        "Evaluación multidimensional: Martes y Viernes en alerta roja permanente; Miércoles y Jueves en desaprovechamiento.",
        fontsize=13, fontweight="bold", color="#0B132B", pad=15
    )

    out_path = os.path.join(OUTPUT_DIR, "09_heatmap_semaforo_operativo.png")
    plt.tight_layout()
    plt.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"  [OK] Guardado: {out_path}")


# ==============================================================================
# 10. SERIE TEMPORAL: PERSISTENCIA DEL PATRÓN A LO LARGO DEL TIEMPO
# ==============================================================================
def plot_10_timeline_consistency(df):
    # Agrupamos por semana y día; tomamos 12 semanas representativas del período de operación plena (2015)
    df["year_week"] = df["date"].dt.to_period("W")
    weeks = df["year_week"].drop_duplicates().sort_values().reset_index(drop=True)
    sample_weeks = weeks[70:82]  # Período consolidado con canal mayorista y promociones en pleno funcionamiento

    df_sample = df[df["year_week"].isin(sample_weeks)].copy()
    daily_timeline = df_sample.groupby("date").agg(
        revenue=("line_total", "sum"),
        day_name=("day_name", "first")
    ).reset_index().sort_values("date")

    fig, ax = plt.subplots(figsize=(14, 5.5))
    style_figure(fig, [ax])

    ax.plot(daily_timeline["date"], daily_timeline["revenue"], color="#1D3557", linewidth=1.5, alpha=0.8, label="Ventas Diarias ($)")

    # Marcar picos y valles con puntos y triángulos de color
    tue_pts = daily_timeline[daily_timeline["day_name"] == "Tuesday"]
    fri_pts = daily_timeline[daily_timeline["day_name"] == "Friday"]
    wed_pts = daily_timeline[daily_timeline["day_name"] == "Wednesday"]
    thu_pts = daily_timeline[daily_timeline["day_name"] == "Thursday"]

    ax.scatter(tue_pts["date"], tue_pts["revenue"], color="#E63946", s=60, label="Martes (30% OFF - Pico)", zorder=5)
    ax.scatter(fri_pts["date"], fri_pts["revenue"], color="#F4A261", s=50, label="Viernes (25% OFF - Pico)", zorder=5)
    ax.scatter(wed_pts["date"], wed_pts["revenue"], color="#2A9D8F", marker="v", s=55, label="Miércoles (Valle)", zorder=5)
    ax.scatter(thu_pts["date"], thu_pts["revenue"], color="#9A031E", marker="v", s=45, label="Jueves (Valle Extremo)", zorder=5)

    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda y, _: f"${y/1000:,.0f}K"))
    ax.set_ylim(0, daily_timeline["revenue"].max() * 1.15)
    ax.set_ylabel("Recaudación Diaria ($ USD)", fontsize=11, fontweight="bold", color="#1D3557")
    ax.set_xlabel("Fecha (Muestra Continua de 12 Semanas)", fontsize=11, fontweight="bold", color="#1D3557")
    ax.legend(loc="upper right", frameon=True, facecolor="white", edgecolor="#D1D5DB", fontsize=9.5)

    plt.title(
        "CONSISTENCIA TEMPORAL: EL PATRÓN SERRUCHO ES SISTÉMICO Y RECURRENTE\n"
        "La oscilación no es una anomalía estacional; se repite de forma ininterrumpida cada semana del año.",
        fontsize=13, fontweight="bold", color="#0B132B", pad=15
    )

    out_path = os.path.join(OUTPUT_DIR, "10_serie_temporal_patron_recurrente.png")
    plt.tight_layout()
    plt.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"  [OK] Guardado: {out_path}")


def main():
    print("=" * 80)
    print(" INICIANDO GENERACIÓN DE GRÁFICOS VISUALES PARA PRESENTACIÓN COMERCIAL ")
    print("=" * 80)
    df = load_data()

    print("\nGenerando gráficos...")
    plot_01_weekly_distribution(df)
    plot_02_bottleneck_ratios(df)
    plot_03_ticket_economics(df)
    plot_04_customer_segmentation(df)
    plot_05_load_smoothing(df)
    plot_06_top_categories(df)
    plot_07_discount_cost(df)
    plot_08_invoice_dispersion(df)
    plot_09_heatmap_matrix(df)
    plot_10_timeline_consistency(df)

    print("\n" + "=" * 80)
    print(f" ¡Éxito! 10 gráficos generados en alta calidad en el directorio: {OUTPUT_DIR}")
    print("=" * 80)


if __name__ == "__main__":
    main()
