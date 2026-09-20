#!/usr/bin/env python3
"""
assign_sucursales.py
====================
Este script:
1. Genera la tabla de dimensión `dataset/sucursal.csv` con los campos:
   - id_sucursal: Identificador de la sucursal (1, 2, 3)
   - des_sucursal: Nombre descriptivo de la sucursal
   - id_provincia: ID degenerado de la provincia
   - des_provincia: Descripción de la provincia
   - id_localidad: ID degenerado de la localidad
   - des_localidad: Descripción de la localidad

2. Asigna cada factura (InvoiceID) en `purchases.csv` a una de las 3 sucursales,
   cumpliendo estrictamente con la distribución requerida por tipo de cliente tanto
   en recaudación monetaria (importe total) como en volumen físico (items vendidos):
   - Mayoristas (wholesaler):
     * Sucursal 1: 65%
     * Sucursal 2: 5%
     * Sucursal 3: 30%
   - Minoristas (private):
     * Sucursal 1: 25%
     * Sucursal 2: 55%
     * Sucursal 3: 20%

3. Actualiza `dataset/purchases.csv` incorporando la columna `id_sucursal`.
"""

import os
import sys
import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_DIR = os.path.join(BASE_DIR, "dataset")

PURCHASES_FILE = os.path.join(DATASET_DIR, "purchases.csv")
INVOICE_ITEMS_FILE = os.path.join(DATASET_DIR, "invoice_items.csv")
CUSTOMERS_FILE = os.path.join(DATASET_DIR, "customers.csv")
SUCURSAL_FILE = os.path.join(DATASET_DIR, "sucursal.csv")


def create_sucursal_dimension():
    """Genera dataset/sucursal.csv con provincia y localidad como IDs degenerados."""
    sucursales_data = [
        {
            "id_sucursal": 1,
            "des_sucursal": "Sucursal 1 - Central Mayorista",
            "id_provincia": 1,
            "des_provincia": "Buenos Aires",
            "id_localidad": 101,
            "des_localidad": "CABA",
        },
        {
            "id_sucursal": 2,
            "des_sucursal": "Sucursal 2 - Retail Shopping",
            "id_provincia": 1,
            "des_provincia": "Buenos Aires",
            "id_localidad": 102,
            "des_localidad": "Vicente López",
        },
        {
            "id_sucursal": 3,
            "des_sucursal": "Sucursal 3 - Expansión Interior",
            "id_provincia": 2,
            "des_provincia": "Córdoba",
            "id_localidad": 201,
            "des_localidad": "Córdoba Capital",
        },
    ]

    df_sucursal = pd.DataFrame(sucursales_data)
    df_sucursal.to_csv(SUCURSAL_FILE, index=False)
    print(f"Dimension sucursal creada en: {SUCURSAL_FILE}")
    print(df_sucursal.to_string(index=False))
    print()
    return df_sucursal


def assign_sucursales():
    """Asigna id_sucursal a cada factura y actualiza purchases.csv."""
    print("Cargando compras, facturación y clientes...")
    purchases = pd.read_csv(PURCHASES_FILE)
    items = pd.read_csv(INVOICE_ITEMS_FILE)
    customers = pd.read_csv(CUSTOMERS_FILE)

    # Preparar resumen a nivel factura para optimización
    df = purchases[["InvoiceID", "CustomerID", "quantity"]].copy()
    df["line_total"] = items["line_total"]
    df = df.merge(customers[["CustomerID", "customer_type"]], on="CustomerID", how="left")

    inv = df.groupby(["InvoiceID", "customer_type"]).agg(
        revenue=("line_total", "sum"),
        items=("quantity", "sum")
    ).reset_index()

    targets = {
        "wholesaler": {1: 0.65, 2: 0.05, 3: 0.30},
        "private":    {1: 0.25, 2: 0.55, 3: 0.20}
    }

    invoice_to_sucursal = {}

    print("\nOptimizando distribución bicriterio (importe y unidades)...")

    for c_type, t_dict in targets.items():
        sub = inv[inv["customer_type"] == c_type].copy()
        total_rev = sub["revenue"].sum()
        total_it = sub["items"].sum()

        target_rev = {b: total_rev * t_dict[b] for b in [1, 2, 3]}
        target_it = {b: total_it * t_dict[b] for b in [1, 2, 3]}

        curr_rev = {1: 0.0, 2: 0.0, 3: 0.0}
        curr_it = {1: 0.0, 2: 0.0, 3: 0.0}

        # Ordenar descendente por recaudación e items
        sub = sub.sort_values(by=["revenue", "items"], ascending=[False, False]).reset_index(drop=True)
        assigned = []

        # Paso 1: Greedy según menor tasa de llenado ponderada
        for _, row in sub.iterrows():
            r = row["revenue"]
            it = row["items"]
            best_b = min(
                [1, 2, 3],
                key=lambda b: 0.5 * (curr_rev[b] / target_rev[b]) + 0.5 * (curr_it[b] / target_it[b])
            )
            curr_rev[best_b] += r
            curr_it[best_b] += it
            assigned.append(best_b)

        sub["bucket"] = assigned

        def calc_loss(c_rev, c_it):
            return sum(
                ((c_rev[b] / total_rev - t_dict[b]) ** 2 + (c_it[b] / total_it - t_dict[b]) ** 2)
                for b in [1, 2, 3]
            )

        current_loss = calc_loss(curr_rev, curr_it)

        # Paso 2: Refinamiento estocástico local para converger exactamente al objetivo
        for pass_num in range(2):
            indices = sub.index.tolist()
            np.random.seed(42 + pass_num)
            np.random.shuffle(indices)
            for idx in indices:
                old_b = sub.at[idx, "bucket"]
                r = sub.at[idx, "revenue"]
                it = sub.at[idx, "items"]
                for new_b in [1, 2, 3]:
                    if new_b == old_b:
                        continue
                    test_rev = curr_rev.copy()
                    test_it = curr_it.copy()
                    test_rev[old_b] -= r
                    test_rev[new_b] += r
                    test_it[old_b] -= it
                    test_it[new_b] += it
                    new_loss = calc_loss(test_rev, test_it)
                    if new_loss < current_loss:
                        current_loss = new_loss
                        curr_rev = test_rev
                        curr_it = test_it
                        sub.at[idx, "bucket"] = new_b
                        break

        # Guardar mapeo
        for inv_id, b in zip(sub["InvoiceID"], sub["bucket"]):
            invoice_to_sucursal[inv_id] = b

        print(f"\nResultados para segmento: {c_type.upper()}")
        print("-" * 75)
        print(f"{'Sucursal':<15} {'Target':<12} {'% Recaudación':<18} {'% Items Vendidos':<18} {'Total Facturas':<12}")
        print("-" * 75)
        for b in [1, 2, 3]:
            r_pct = curr_rev[b] / total_rev * 100
            it_pct = curr_it[b] / total_it * 100
            inv_count = (sub["bucket"] == b).sum()
            print(f"Sucursal {b:<6} {t_dict[b]*100:>5.1f}%       {r_pct:>6.2f}%             {it_pct:>6.2f}%             {inv_count:>7,}")
        print("-" * 75)

    # Actualizar purchases.csv
    print("\nActualizando dataset/purchases.csv...")
    purchases["id_sucursal"] = purchases["InvoiceID"].map(invoice_to_sucursal)
    
    # Aseguramos el orden canónico de columnas
    cols = ["InvoiceID", "date", "CustomerID", "product_id", "quantity", "id_sucursal"]
    purchases = purchases[cols]
    purchases.to_csv(PURCHASES_FILE, index=False)
    print(f"Archivo actualizado exitosamente: {PURCHASES_FILE} ({len(purchases):,} filas)")


def main():
    create_sucursal_dimension()
    assign_sucursales()
    print("\n¡Proceso de asignación de sucursales completado exitosamente!")


if __name__ == "__main__":
    main()
