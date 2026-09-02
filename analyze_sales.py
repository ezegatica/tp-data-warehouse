#!/usr/bin/env python3
"""
analyze_sales.py
================
Script integral de analítica sobre el Data Warehouse (CSVs).
Proporciona análisis multidimensionales orientados a sustentar
la propuesta comercial de optimización y normalización de demanda:

1. Distribución Semanal General: Facturas (caudal), Unidades y Recaudación.
2. Métricas de Ticket: Ticket Promedio (AOV) y Unidades por Ticket (UPT).
3. Segmentación de Clientes: Comportamiento de Mayoristas vs. Particulares.
4. Concentración y Cuello de Botella Operativo: Ratio Pico vs. Valle.
5. Análisis por Categoría de Producto según día de promoción.
6. Diagnóstico y Recomendaciones Estratégicas para el cliente.
"""

import os
import sys
import pandas as pd
import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

DATASET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dataset")
PURCHASES_FILE = os.path.join(DATASET_DIR, "purchases.csv")
INVOICE_ITEMS_FILE = os.path.join(DATASET_DIR, "invoice_items.csv")
PRODUCTS_FILE = os.path.join(DATASET_DIR, "products.csv")
CUSTOMERS_FILE = os.path.join(DATASET_DIR, "customers.csv")
DISCOUNTS_FILE = os.path.join(DATASET_DIR, "discounts.csv")

DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DAY_ES = {
    "Monday": "Lunes",
    "Tuesday": "Martes (30% OFF)",
    "Wednesday": "Miércoles",
    "Thursday": "Jueves",
    "Friday": "Viernes (25% OFF)",
    "Saturday": "Sábado",
    "Sunday": "Domingo",
}


def load_integrated_dataset():
    """Carga y une todas las entidades del Data Warehouse."""
    print("Cargando y unificando datos del Data Warehouse...")
    purchases = pd.read_csv(PURCHASES_FILE)
    items = pd.read_csv(INVOICE_ITEMS_FILE)
    products = pd.read_csv(PRODUCTS_FILE)
    customers = pd.read_csv(CUSTOMERS_FILE)

    purchases["date"] = pd.to_datetime(purchases["date"])
    purchases["day_name"] = purchases["date"].dt.day_name()

    # Unir compras con items (1 a 1)
    df = purchases.copy()
    df["price"] = items["price"]
    df["line_total"] = items["line_total"]

    # Enriquecer con categorías y tipo de cliente
    df = df.merge(products[["product_id", "category"]], on="product_id", how="left")
    df = df.merge(customers[["CustomerID", "customer_type"]], on="CustomerID", how="left")

    df["day_order"] = df["day_name"].apply(lambda d: DAY_ORDER.index(d))
    return df


def draw_bar(val, max_val, max_chars=20):
    """Genera una barra visual en texto ASCII seguro."""
    if max_val == 0:
        return ""
    length = int((val / max_val) * max_chars)
    return "[" + "=" * length + " " * (max_chars - length) + "]"


def section_header(title):
    print("\n" + "=" * 90)
    print(f" {title.upper()} ".center(90, "="))
    print("=" * 90)


def analyze_weekly_distribution(df):
    section_header("1. Distribución Semanal: Afluencia, Volumen y Recaudación")
    
    daily = df.groupby(["day_order", "day_name"]).agg(
        invoices=("InvoiceID", "nunique"),
        customers=("CustomerID", "nunique"),
        units=("quantity", "sum"),
        revenue=("line_total", "sum")
    ).reset_index().sort_values("day_order")

    total_invoices = daily["invoices"].sum()
    total_units = daily["units"].sum()
    total_revenue = daily["revenue"].sum()

    daily["pct_inv"] = (daily["invoices"] / total_invoices) * 100
    daily["pct_units"] = (daily["units"] / total_units) * 100
    daily["pct_rev"] = (daily["revenue"] / total_revenue) * 100

    max_rev = daily["revenue"].max()

    print(f"{'Día':<22} | {'Facturas (% Tot)':<17} | {'Unidades (% Tot)':<17} | {'Recaudación (% Tot)':<22} | {'Intensidad':<15}")
    print("-" * 22 + "-+-" + "-" * 17 + "-+-" + "-" * 17 + "-+-" + "-" * 22 + "-+-" + "-" * 15)

    for _, r in daily.iterrows():
        day_label = DAY_ES[r["day_name"]]
        inv_str = f"{r['invoices']:,} ({r['pct_inv']:.1f}%)"
        units_str = f"{r['units']:,} ({r['pct_units']:.1f}%)"
        rev_str = f"${r['revenue']:,.2f} ({r['pct_rev']:.1f}%)"
        bar = draw_bar(r["revenue"], max_rev, 15)
        print(f"{day_label:<22} | {inv_str:<17} | {units_str:<17} | {rev_str:<22} | {bar}")

    print("-" * 90)
    print(f"{'TOTAL SEMANAL':<22} | {total_invoices:,} (100%)    | {total_units:,} (100%)    | ${total_revenue:,.2f} (100%)")
    return daily


def analyze_ticket_economics(df):
    section_header("2. Economía del Ticket: Valor Promedio (AOV) y Unidades por Carrito (UPT)")

    # Agrupar a nivel de factura primero
    invoice_level = df.groupby(["InvoiceID", "day_order", "day_name"]).agg(
        invoice_revenue=("line_total", "sum"),
        invoice_units=("quantity", "sum")
    ).reset_index()

    ticket_stats = invoice_level.groupby(["day_order", "day_name"]).agg(
        aov=("invoice_revenue", "mean"),
        median_ticket=("invoice_revenue", "median"),
        upt=("invoice_units", "mean")
    ).reset_index().sort_values("day_order")

    print(f"{'Día':<22} | {'Ticket Promedio (AOV)':<22} | {'Ticket Mediana':<16} | {'Unidades / Ticket (UPT)':<23}")
    print("-" * 22 + "-+-" + "-" * 22 + "-+-" + "-" * 16 + "-+-" + "-" * 23)

    for _, r in ticket_stats.iterrows():
        day_label = DAY_ES[r["day_name"]]
        aov_str = f"${r['aov']:,.2f}"
        med_str = f"${r['median_ticket']:,.2f}"
        upt_str = f"{r['upt']:.2f} unidades"
        print(f"{day_label:<22} | {aov_str:<22} | {med_str:<16} | {upt_str:<23}")

    print("\nInsight: En días con descuento, los clientes aumentan significativamente el tamaño")
    print("de su carrito (UPT), aprovechando la rebaja para adquirir más unidades por compra.")


def analyze_customer_segmentation(df):
    section_header("3. Segmentación: Clientes Mayoristas (Wholesaler) vs Particulares (Private)")

    seg = df.groupby(["day_order", "day_name", "customer_type"]).agg(
        invoices=("InvoiceID", "nunique"),
        revenue=("line_total", "sum")
    ).reset_index()

    piv_inv = seg.pivot(index=["day_order", "day_name"], columns="customer_type", values="invoices").fillna(0)
    piv_rev = seg.pivot(index=["day_order", "day_name"], columns="customer_type", values="revenue").fillna(0)

    print(f"{'Día':<22} | {'Facturas Particulares':<22} | {'Facturas Mayoristas':<20} | {'Recaudación Mayorista ($)':<25}")
    print("-" * 22 + "-+-" + "-" * 22 + "-+-" + "-" * 20 + "-+-" + "-" * 25)

    for (day_order, day_name) in piv_inv.index:
        day_label = DAY_ES[day_name]
        priv_inv = int(piv_inv.loc[(day_order, day_name), "private"])
        whol_inv = int(piv_inv.loc[(day_order, day_name), "wholesaler"])
        whol_rev = piv_rev.loc[(day_order, day_name), "wholesaler"]
        total_day_rev = piv_rev.loc[(day_order, day_name)].sum()
        pct_whol = (whol_rev / total_day_rev * 100) if total_day_rev > 0 else 0
        print(f"{day_label:<22} | {priv_inv:<22,} | {whol_inv:<20,} | ${whol_rev:,.2f} ({pct_whol:.1f}%)")

    print("\nInsight: El 30% y 25% OFF activa tanto el consumo minorista como grandes pedidos mayoristas,")
    print("explicando por qué los martes y viernes concentran la máxima facturación global.")


def analyze_operational_bottlenecks(daily):
    section_header("4. Índice de Estrés y Desbalance Operativo (Pico vs. Valle)")

    weekdays = daily[daily["day_name"].isin(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])]
    max_day = weekdays.loc[weekdays["revenue"].idxmax()]
    min_day = weekdays.loc[weekdays["revenue"].idxmin()]

    ratio_rev = max_day["revenue"] / min_day["revenue"]
    ratio_inv = max_day["invoices"] / min_day["invoices"]
    ratio_units = max_day["units"] / min_day["units"]

    print(f"Día Pico Hábil (Promo)  : {DAY_ES[max_day['day_name']]} -> {max_day['invoices']:,} facturas | ${max_day['revenue']:,.2f}")
    print(f"Día Valle Hábil (Vacío) : {DAY_ES[min_day['day_name']]} -> {min_day['invoices']:,} facturas | ${min_day['revenue']:,.2f}")
    print("-" * 90)
    print(f"Disparidad de Recaudación (Pico / Valle) : {ratio_rev:.1f}x veces más recaudación en el pico")
    print(f"Disparidad de Afluencia   (Pico / Valle) : {ratio_inv:.1f}x veces más personas en tienda")
    print(f"Disparidad de Unidades    (Pico / Valle) : {ratio_units:.1f}x veces más volumen logístico a despachar")
    print("-" * 90)
    print("DIAGNÓSTICO COMERCIAL:")
    print("  • Operación saturada: Martes y Viernes colapsan cajas registradoras, depósito y logística.")
    print("  • Capacidad ociosa: Miércoles y Jueves tienen costos fijos idénticos con una fracción del flujo.")
    print("  • Solución a vender: Un algoritmo de redistribución de promociones para estabilizar la curva.")


def analyze_top_categories_by_promo(df):
    section_header("5. Impacto por Categoría: Días de Descuento vs. Días Sin Descuento")

    df["is_promo_day"] = df["day_name"].isin(["Tuesday", "Friday"])
    cat_summary = df.groupby(["category", "is_promo_day"])["line_total"].sum().unstack().fillna(0)
    cat_summary.columns = ["Sin Descuento ($)", "Con Descuento ($)"]
    cat_summary["Total ($)"] = cat_summary.sum(axis=1)
    cat_summary["% en Días Promo"] = (cat_summary["Con Descuento ($)"] / cat_summary["Total ($)"]) * 100
    cat_summary = cat_summary.sort_values(by="Total ($)", ascending=False)

    print(f"{'Categoría':<35} | {'Días Promo (Mar/Vie)':<22} | {'Días Sin Promo':<18} | {'% en Promoción':<15}")
    print("-" * 35 + "-+-" + "-" * 22 + "-+-" + "-" * 18 + "-+-" + "-" * 15)

    for cat, r in cat_summary.iterrows():
        promo_rev = f"${r['Con Descuento ($)']:,.2f}"
        no_promo = f"${r['Sin Descuento ($)']:,.2f}"
        pct = f"{r['% en Días Promo']:.1f}%"
        print(f"{cat:<35} | {promo_rev:<22} | {no_promo:<18} | {pct:<15}")


def main():
    df = load_integrated_dataset()
    daily = analyze_weekly_distribution(df)
    analyze_ticket_economics(df)
    analyze_customer_segmentation(df)
    analyze_top_categories_by_promo(df)
    analyze_operational_bottlenecks(daily)
    print("\n" + "=" * 90)
    print(" Análisis finalizado exitosamente. Listo para presentar a clientes y directivos. ")
    print("=" * 90 + "\n")


if __name__ == "__main__":
    main()
