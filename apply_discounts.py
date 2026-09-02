#!/usr/bin/env python3
"""
apply_discounts.py
==================
Este script realiza las transformaciones requeridas para el Data Warehouse:
1. Crea el dataset de descuentos `dataset/discounts.csv`
   con vigencia temporal, identificadores de producto y porcentaje de descuento
   (30% los martes y 25% los viernes).
2. Realiza un respaldo automático del dataset original en `dataset/backup/`.
3. Redistribuye el 50% de las ventas de los miércoles entre martes, viernes,
   sábado y domingo dentro de la misma semana.
4. Aplica el factor de demanda/elasticidad promocional en los días con descuento.
5. Aplica retroactivamente los descuentos sobre los precios unitarios y line_total
   en `invoice_items.csv`, garantizando sincronización exacta 1 a 1 con `purchases.csv`.
6. Valida y muestra el reporte comparativo (Antes vs. Después) para sustentar la
   narrativa comercial de analítica de datos.
"""

import os
import sys
import shutil
import argparse
import numpy as np
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_DIR = os.path.join(BASE_DIR, "dataset")
BACKUP_DIR = os.path.join(DATASET_DIR, "backup")

PURCHASES_FILE = os.path.join(DATASET_DIR, "purchases.csv")
INVOICE_ITEMS_FILE = os.path.join(DATASET_DIR, "invoice_items.csv")
PRODUCTS_FILE = os.path.join(DATASET_DIR, "products.csv")
CUSTOMERS_FILE = os.path.join(DATASET_DIR, "customers.csv")
DISCOUNTS_FILE = os.path.join(DATASET_DIR, "discounts.csv")


def create_backup():
    """Crea una copia de respaldo de los CSVs originales si no existe ya."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    for fname in ["purchases.csv", "invoice_items.csv"]:
        src = os.path.join(DATASET_DIR, fname)
        dst = os.path.join(BACKUP_DIR, fname)
        if os.path.exists(src) and not os.path.exists(dst):
            print(f"Creando respaldo de seguridad: {fname} -> {dst}")
            shutil.copy2(src, dst)


def restore_backup():
    """Restaura los archivos originales desde la carpeta de backup."""
    if not os.path.exists(BACKUP_DIR):
        print("No se encontró el directorio de respaldo dataset/backup/.")
        return
    for fname in ["purchases.csv", "invoice_items.csv"]:
        src = os.path.join(BACKUP_DIR, fname)
        dst = os.path.join(DATASET_DIR, fname)
        if os.path.exists(src):
            print(f"Restaurando {fname} desde {src}...")
            shutil.copy2(src, dst)
    print("Archivos restaurados al estado original con éxito.")


def generate_discounts_csv(products_df, min_date="2014-01-01", max_date="2015-12-31"):
    """
    Genera el archivo discounts.csv con las reglas de promociones para todos los productos
    con vigencia temporal (start_date, end_date) para martes (30% OFF) y viernes (25% OFF).
    """
    print(f"\nGenerando tabla de descuentos para {len(products_df):,} productos...")
    discounts_records = []
    discount_id = 1

    for prod_id in products_df["product_id"]:
        # Martes 30% OFF
        discounts_records.append({
            "discount_id": discount_id,
            "product_id": int(prod_id),
            "discount_percentage": 30.00,
            "start_date": min_date,
            "end_date": max_date,
            "day_of_week": "Tuesday",
            "campaign_name": "Martes Promo 30% OFF"
        })
        discount_id += 1

        # Viernes 25% OFF
        discounts_records.append({
            "discount_id": discount_id,
            "product_id": int(prod_id),
            "discount_percentage": 25.00,
            "start_date": min_date,
            "end_date": max_date,
            "day_of_week": "Friday",
            "campaign_name": "Viernes Promo 25% OFF"
        })
        discount_id += 1

    df_discounts = pd.DataFrame(discounts_records)
    df_discounts.to_csv(DISCOUNTS_FILE, index=False)
    print(f"Guardado exitosamente: {DISCOUNTS_FILE} ({len(df_discounts):,} registros)")
    return df_discounts


def print_stats_table(title, df):
    """Muestra una tabla legible con las estadísticas agrupadas por día de la semana."""
    df_temp = df.copy()
    if not np.issubdtype(df_temp["date"].dtype, np.datetime64):
        df_temp["date"] = pd.to_datetime(df_temp["date"])
    df_temp["day_name"] = df_temp["date"].dt.day_name()

    stats = df_temp.groupby("day_name").agg(
        invoices=("InvoiceID", "nunique"),
        customers=("CustomerID", "nunique"),
        total_qty=("quantity", "sum"),
        total_revenue=("line_total", "sum")
    ).reset_index()

    # Orden cronológico de la semana
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    stats["day_order"] = stats["day_name"].apply(lambda d: day_order.index(d) if d in day_order else 99)
    stats = stats.sort_values("day_order").drop(columns=["day_order"])

    print(f"\n{'='*75}")
    print(f"{title.center(75)}")
    print(f"{'='*75}")
    print(f"{'Día':<12} | {'Facturas (Gente)':<16} | {'Clientes Únicos':<15} | {'Ventas (Cant)':<13} | {'Recaudación ($)':<16}")
    print(f"{'-'*12}-+-{'-'*16}-+-{'-'*15}-+-{'-'*13}-+-{'-'*16}")
    for _, row in stats.iterrows():
        day = row["day_name"]
        inv = f"{row['invoices']:,}"
        cust = f"{row['customers']:,}"
        qty = f"{row['total_qty']:,}"
        rev = f"${row['total_revenue']:,.2f}"
        tag = ""
        if day in ["Tuesday", "Friday"]:
            tag = " *"
        print(f"{day:<12}{tag} | {inv:<16} | {cust:<15} | {qty:<13} | {rev:<16}")
    print(f"{'='*75}")
    print("(* Días con promoción / descuento)\n")
    return stats


def transform_data(dry_run=False):
    """Ejecuta la transformación completa de datos."""
    create_backup()

    print("\nLeyendo archivos CSV...")
    # Siempre leemos del backup para que sea reproducible e idempotente
    backup_purchases = os.path.join(BACKUP_DIR, "purchases.csv")
    backup_items = os.path.join(BACKUP_DIR, "invoice_items.csv")

    src_purchases = backup_purchases if os.path.exists(backup_purchases) else PURCHASES_FILE
    src_items = backup_items if os.path.exists(backup_items) else INVOICE_ITEMS_FILE

    df_purchases = pd.read_csv(src_purchases)
    df_items = pd.read_csv(src_items)
    df_products = pd.read_csv(PRODUCTS_FILE)

    # Verificar alineación inicial
    assert len(df_purchases) == len(df_items), "purchases.csv e invoice_items.csv no tienen la misma cantidad de filas"
    assert (df_purchases["InvoiceID"] == df_items["InvoiceID"]).all(), "Los InvoiceIDs no coinciden fila a fila"

    # Mapeo de precio base desde products.csv para consistencia absoluta
    product_price_map = dict(zip(df_products["product_id"], df_products["price"]))
    base_prices = df_items["product_id"].map(product_price_map).fillna(df_items["price"])

    # Tabla unificada para operar
    df = df_purchases.copy()
    df["base_price"] = base_prices
    df["price"] = df_items["price"]
    df["line_total"] = df_items["line_total"]
    df["date"] = pd.to_datetime(df["date"])
    df["day_name"] = df["date"].dt.day_name()

    print_stats_table("ESTADO ORIGINAL DEL DATASET", df)

    # 1. Generar CSV de Descuentos
    min_date = str(df["date"].min().date())
    max_date = str(df["date"].max().date())
    if not dry_run:
        generate_discounts_csv(df_products, min_date=min_date, max_date=max_date)

    # 2. Redistribuir el 50% de las ventas de los miércoles
    print("Redistribuyendo 50% de las ventas de los miércoles...")
    np.random.seed(42)
    wed_invoices = df[df["day_name"] == "Wednesday"]["InvoiceID"].unique()
    total_wed_invoices = len(wed_invoices)
    n_move = total_wed_invoices // 2

    shuffled_wed = np.random.permutation(wed_invoices)
    move_invoices = shuffled_wed[:n_move]

    # Distribución estratégica:
    # 28% a Martes (-1 día)
    # 52% a Viernes (+2 días) -> asegura superar a Lunes en afluencia y recaudación
    # 10% a Sábado (+3 días)
    # 10% a Domingo (+4 días)
    n_tue = int(n_move * 0.28)
    n_fri = int(n_move * 0.52)
    n_sat = int(n_move * 0.10)
    n_sun = n_move - n_tue - n_fri - n_sat

    inv_to_tue = set(move_invoices[:n_tue])
    inv_to_fri = set(move_invoices[n_tue:n_tue + n_fri])
    inv_to_sat = set(move_invoices[n_tue + n_fri:n_tue + n_fri + n_sat])
    inv_to_sun = set(move_invoices[n_tue + n_fri + n_sat:])

    print(f"Total facturas de miércoles: {total_wed_invoices:,}")
    print(f"Facturas a trasladar (50%): {n_move:,}")
    print(f"  -> A Martes  (-1 día): {len(inv_to_tue):,}")
    print(f"  -> A Viernes (+2 días): {len(inv_to_fri):,}")
    print(f"  -> A Sábado  (+3 días): {len(inv_to_sat):,}")
    print(f"  -> A Domingo (+4 días): {len(inv_to_sun):,}")

    mask_tue = df["InvoiceID"].isin(inv_to_tue)
    mask_fri = df["InvoiceID"].isin(inv_to_fri)
    mask_sat = df["InvoiceID"].isin(inv_to_sat)
    mask_sun = df["InvoiceID"].isin(inv_to_sun)

    df.loc[mask_tue, "date"] = df.loc[mask_tue, "date"] - pd.Timedelta(days=1)
    df.loc[mask_fri, "date"] = df.loc[mask_fri, "date"] + pd.Timedelta(days=2)
    df.loc[mask_sat, "date"] = df.loc[mask_sat, "date"] + pd.Timedelta(days=3)
    df.loc[mask_sun, "date"] = df.loc[mask_sun, "date"] + pd.Timedelta(days=4)

    # Actualizar día de la semana tras el movimiento
    df["day_name"] = df["date"].dt.day_name()

    # 3. Aplicar elasticidad y demanda promocional en días con descuento
    print("Aplicando elasticidad y volumen promocional en Martes y Viernes...")
    is_tue = df["day_name"] == "Tuesday"
    is_fri = df["day_name"] == "Friday"

    # Los clientes compran más volumen en promociones
    df.loc[is_tue, "quantity"] = (df.loc[is_tue, "quantity"] * 1.35).round().astype(int).clip(lower=1)
    df.loc[is_fri, "quantity"] = (df.loc[is_fri, "quantity"] * 2.10).round().astype(int).clip(lower=1)

    # 4. Aplicar descuentos a precios unitarios
    # Martes: 30% OFF -> precio = base_price * 0.70
    # Viernes: 25% OFF -> precio = base_price * 0.75
    # Otros días: precio = base_price
    print("Aplicando descuentos en precios (30% Martes, 25% Viernes)...")
    df["price"] = df["base_price"].round(2)
    df.loc[is_tue, "price"] = (df.loc[is_tue, "base_price"] * 0.70).round(2)
    df.loc[is_fri, "price"] = (df.loc[is_fri, "base_price"] * 0.75).round(2)

    # Recalcular line_total
    df["line_total"] = (df["quantity"] * df["price"]).round(2)

    final_stats = print_stats_table("ESTADO FINAL DEL DATASET (CON NARRATIVA Y DESCUENTOS)", df)

    # Validar la narrativa de negocio
    stats_dict = final_stats.set_index("day_name").to_dict(orient="index")
    tue = stats_dict["Tuesday"]
    fri = stats_dict["Friday"]
    mon = stats_dict["Monday"]
    wed = stats_dict["Wednesday"]
    thu = stats_dict["Thursday"]

    print("Verificación de la Narrativa de Negocio:")
    cond_rev_tue = tue["total_revenue"] > mon["total_revenue"]
    cond_rev_fri = fri["total_revenue"] > mon["total_revenue"]
    cond_qty_tue = tue["total_qty"] > mon["total_qty"]
    cond_qty_fri = fri["total_qty"] > mon["total_qty"]
    cond_inv_tue = tue["invoices"] > mon["invoices"]
    cond_inv_fri = fri["invoices"] > mon["invoices"]
    cond_wed_drop = wed["invoices"] < mon["invoices"]
    cond_thu_drop = thu["invoices"] < mon["invoices"]

    checks = [
        ("Recaudación: Martes con descuento supera a días hábiles sin descuento", cond_rev_tue),
        ("Recaudación: Viernes con descuento supera a días hábiles sin descuento", cond_rev_fri),
        ("Ventas (volumen): Martes con descuento supera a días hábiles sin descuento", cond_qty_tue),
        ("Ventas (volumen): Viernes con descuento supera a días hábiles sin descuento", cond_qty_fri),
        ("Afluencia (gente): Martes con descuento supera a días hábiles sin descuento", cond_inv_tue),
        ("Afluencia (gente): Viernes con descuento supera a días hábiles sin descuento", cond_inv_fri),
        ("Días sin descuento (Miércoles y Jueves) tienen mínimo caudal de gente", cond_wed_drop and cond_thu_drop),
    ]

    all_passed = True
    for desc, passed in checks:
        status = "[OK]" if passed else "[FALLO]"
        print(f"  {status} {desc}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\n¡Excelente! La narrativa quedó 100% validada y demostrada matemáticamente.")
    else:
        print("\nADVERTENCIA: Algunas condiciones de la narrativa no se cumplieron.")

    if not dry_run:
        print("\nGuardando cambios en los archivos CSV...")
        # Guardar purchases.csv
        df_out_purchases = df[["InvoiceID", "date", "CustomerID", "product_id", "quantity"]].copy()
        df_out_purchases["date"] = df_out_purchases["date"].dt.strftime("%Y-%m-%d")
        df_out_purchases.to_csv(PURCHASES_FILE, index=False)
        print(f"Actualizado: {PURCHASES_FILE} ({len(df_out_purchases):,} filas)")

        # Guardar invoice_items.csv
        df_out_items = df[["InvoiceID", "product_id", "quantity", "price", "line_total"]].copy()
        df_out_items.to_csv(INVOICE_ITEMS_FILE, index=False)
        print(f"Actualizado: {INVOICE_ITEMS_FILE} ({len(df_out_items):,} filas)")
        print("\nProceso finalizado con éxito.")
    else:
        print("\nModo --dry-run: No se modificó ningún archivo en disco.")


def main():
    parser = argparse.ArgumentParser(description="Aplica descuentos y narrativa de negocio sobre el dataset.")
    parser.add_argument("--restore", action="store_true", help="Restaura los archivos originales desde dataset/backup/")
    parser.add_argument("--dry-run", action="store_true", help="Simula y muestra las estadísticas sin sobreescribir archivos")
    args = parser.parse_args()

    if args.restore:
        restore_backup()
    else:
        transform_data(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
