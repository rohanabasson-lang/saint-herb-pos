"""
Saint Herb Premium Inventory Management + POS
============================================

How to run locally
------------------
1. Save this file as: app.py
2. Install dependencies:
   pip install streamlit pandas plotly
3. Run the app:
   streamlit run app.py

Notes
-----
- This demo uses neutral placeholder products for development.
- Inventory and sales persist to local JSON files in the same folder:
  - saint_herb_inventory.json
  - saint_herb_sales.json
- Use "Reset Demo Data" in Settings to reload the sample data.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Any

import pandas as pd
import plotly.express as px
import streamlit as st


# ============================================================
# App Configuration
# ============================================================

st.set_page_config(
    page_title="Saint Herb POS",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

APP_NAME = "Saint Herb"
INVENTORY_FILE = Path("saint_herb_inventory.json")
SALES_FILE = Path("saint_herb_sales.json")

CATEGORIES = ["Pre-Rolls", "Flower / Bud", "Accessories"]
UNITS = ["gram", "unit", "pack", "bottle"]
PAYMENT_METHODS = ["Cash", "Card", "EFT", "Other"]


# ============================================================
# Styling
# ============================================================

def inject_css() -> None:
    st.markdown(
        """
        <style>
            :root {
                --saint-bg: #0f1411;
                --saint-panel: rgba(255, 255, 255, 0.06);
                --saint-panel-strong: rgba(255, 255, 255, 0.10);
                --saint-border: rgba(255, 255, 255, 0.12);
                --saint-green: #2fd17c;
                --saint-green-dark: #0f8f4f;
                --saint-gold: #d7b56d;
                --saint-red: #ff6b6b;
                --saint-yellow: #f7c948;
                --saint-text-soft: #aeb7b2;
            }

            .main .block-container {
                padding-top: 1.2rem;
                padding-bottom: 2rem;
                max-width: 1450px;
            }

            h1, h2, h3 {
                letter-spacing: -0.03em;
            }

            .saint-hero {
                padding: 1.4rem 1.6rem;
                border: 1px solid var(--saint-border);
                border-radius: 24px;
                background:
                    radial-gradient(circle at top left, rgba(47, 209, 124, 0.22), transparent 32%),
                    linear-gradient(135deg, rgba(19, 30, 24, 0.98), rgba(10, 14, 12, 0.92));
                box-shadow: 0 18px 50px rgba(0, 0, 0, 0.18);
                margin-bottom: 1rem;
            }

            .saint-hero-title {
                font-size: 2.3rem;
                font-weight: 800;
                color: white;
                margin: 0;
            }

            .saint-hero-subtitle {
                color: var(--saint-text-soft);
                margin-top: 0.35rem;
                font-size: 1rem;
            }

            .metric-card {
                padding: 1.05rem 1.15rem;
                border-radius: 20px;
                background: linear-gradient(145deg, rgba(255,255,255,0.08), rgba(255,255,255,0.025));
                border: 1px solid var(--saint-border);
                box-shadow: 0 12px 34px rgba(0,0,0,0.10);
                min-height: 120px;
            }

            .metric-label {
                color: var(--saint-text-soft);
                font-size: 0.82rem;
                text-transform: uppercase;
                letter-spacing: 0.08em;
                font-weight: 700;
                margin-bottom: 0.35rem;
            }

            .metric-value {
                font-size: 1.85rem;
                font-weight: 800;
                letter-spacing: -0.03em;
            }

            .metric-help {
                color: var(--saint-text-soft);
                font-size: 0.85rem;
                margin-top: 0.25rem;
            }

            .product-card {
                padding: 1rem;
                border-radius: 20px;
                background: linear-gradient(145deg, rgba(255,255,255,0.075), rgba(255,255,255,0.025));
                border: 1px solid var(--saint-border);
                box-shadow: 0 10px 30px rgba(0,0,0,0.10);
                margin-bottom: 0.8rem;
            }

            .product-icon {
                width: 100%;
                min-height: 78px;
                border-radius: 16px;
                background:
                    radial-gradient(circle at 30% 20%, rgba(47, 209, 124, 0.40), transparent 28%),
                    linear-gradient(135deg, rgba(47,209,124,0.16), rgba(215,181,109,0.10));
                border: 1px solid rgba(47,209,124,0.16);
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 2.1rem;
                margin-bottom: 0.75rem;
            }

            .product-name {
                font-weight: 800;
                font-size: 1rem;
                line-height: 1.25;
                margin-bottom: 0.2rem;
            }

            .product-meta {
                color: var(--saint-text-soft);
                font-size: 0.82rem;
            }

            .product-price {
                font-size: 1.15rem;
                font-weight: 800;
                color: var(--saint-green);
                margin-top: 0.45rem;
            }

            .cart-box {
                padding: 1rem;
                border-radius: 22px;
                background: linear-gradient(145deg, rgba(47,209,124,0.12), rgba(255,255,255,0.025));
                border: 1px solid rgba(47,209,124,0.22);
                box-shadow: 0 14px 40px rgba(0,0,0,0.12);
            }

            .cart-total {
                font-size: 2rem;
                font-weight: 900;
                color: var(--saint-green);
                margin-top: 0.2rem;
            }

            .status-pill {
                padding: 0.25rem 0.55rem;
                border-radius: 999px;
                font-size: 0.78rem;
                font-weight: 800;
                display: inline-block;
            }

            .status-good {
                color: #0a3b22;
                background: #a7f3c8;
            }

            .status-medium {
                color: #443300;
                background: #ffe08a;
            }

            .status-low {
                color: #4a1111;
                background: #ffb3b3;
            }

            div[data-testid="stSidebar"] {
                border-right: 1px solid rgba(255,255,255,0.08);
            }

            div.stButton > button {
                border-radius: 14px;
                font-weight: 800;
                border: 1px solid rgba(47, 209, 124, 0.25);
            }

            div.stButton > button[kind="primary"] {
                background: linear-gradient(135deg, #2fd17c, #0f8f4f);
                color: white;
                border: 0;
            }

            @media (max-width: 900px) {
                .saint-hero-title {
                    font-size: 1.7rem;
                }
                .metric-value {
                    font-size: 1.35rem;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# Utility Functions
# ============================================================

def money(value: float) -> str:
    return f"R {value:,.2f}"


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def make_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def today_string() -> str:
    return date.today().isoformat()


def now_string() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_status(days_on_hand: float) -> str:
    if days_on_hand < 10:
        return "Low"
    if days_on_hand <= 30:
        return "Medium"
    return "Good"


def status_html(status: str) -> str:
    css_class = {
        "Good": "status-good",
        "Medium": "status-medium",
        "Low": "status-low",
    }.get(status, "status-medium")
    return f'<span class="status-pill {css_class}">{status}</span>'


def icon_for_category(category: str) -> str:
    if category == "Pre-Rolls":
        return "◼"
    if category == "Flower / Bud":
        return "◆"
    return "●"


# ============================================================
# Demo Data
# ============================================================

def default_inventory() -> List[Dict[str, Any]]:
    return [
        # Neutral placeholder names. Replace later with real licensed product names.
        {"id": "PR-001", "name": "Purple Punch Pre-Roll", "category": "Pre-Rolls", "unit": "gram", "quantity_on_hand": 420.0, "unit_price": 28.0, "daily_sales_estimate": 12.0},
        {"id": "PR-002", "name": "Gelato Pre-Roll", "category": "Pre-Rolls", "unit": "gram", "quantity_on_hand": 350.0, "unit_price": 32.0, "daily_sales_estimate": 14.0},
        {"id": "PR-003", "name": "Blue Dream Pre-Roll", "category": "Pre-Rolls", "unit": "gram", "quantity_on_hand": 260.0, "unit_price": 25.0, "daily_sales_estimate": 11.0},
        {"id": "PR-004", "name": "Wedding Cake Pre-Roll", "category": "Pre-Rolls", "unit": "gram", "quantity_on_hand": 180.0, "unit_price": 35.0, "daily_sales_estimate": 10.0},
        {"id": "PR-005", "name": "Runtz Pre-Roll", "category": "Pre-Rolls", "unit": "gram", "quantity_on_hand": 85.0, "unit_price": 30.0, "daily_sales_estimate": 12.0},

        {"id": "FL-001", "name": "Purple Punch Flower", "category": "Flower / Bud", "unit": "gram", "quantity_on_hand": 720.0, "unit_price": 18.0, "daily_sales_estimate": 18.0},
        {"id": "FL-002", "name": "Gelato Flower", "category": "Flower / Bud", "unit": "gram", "quantity_on_hand": 610.0, "unit_price": 22.0, "daily_sales_estimate": 16.0},
        {"id": "FL-003", "name": "Blue Dream Flower", "category": "Flower / Bud", "unit": "gram", "quantity_on_hand": 490.0, "unit_price": 16.0, "daily_sales_estimate": 17.0},
        {"id": "FL-004", "name": "Wedding Cake Flower", "category": "Flower / Bud", "unit": "gram", "quantity_on_hand": 310.0, "unit_price": 24.0, "daily_sales_estimate": 14.0},
        {"id": "FL-005", "name": "Runtz Flower", "category": "Flower / Bud", "unit": "gram", "quantity_on_hand": 145.0, "unit_price": 20.0, "daily_sales_estimate": 15.0},

        {"id": "AC-001", "name": "Rolling Papers Classic", "category": "Accessories", "unit": "pack", "quantity_on_hand": 180.0, "unit_price": 25.0, "daily_sales_estimate": 5.0},
        {"id": "AC-002", "name": "Canna Juice Berry", "category": "Accessories", "unit": "bottle", "quantity_on_hand": 65.0, "unit_price": 45.0, "daily_sales_estimate": 4.0},
        {"id": "AC-003", "name": "Canna Juice Citrus", "category": "Accessories", "unit": "bottle", "quantity_on_hand": 52.0, "unit_price": 45.0, "daily_sales_estimate": 4.0},
        {"id": "AC-004", "name": "Premium Grinder", "category": "Accessories", "unit": "unit", "quantity_on_hand": 28.0, "unit_price": 135.0, "daily_sales_estimate": 1.0},
        {"id": "AC-005", "name": "Refillable Lighter", "category": "Accessories", "unit": "unit", "quantity_on_hand": 95.0, "unit_price": 18.0, "daily_sales_estimate": 3.0},
    ]


def default_sales() -> List[Dict[str, Any]]:
    base_day = date.today()
    demo_sales = []

    sample_items = [
        ("PR-002", "Gelato Pre-Roll", 6, 32.0),
        ("FL-002", "Gelato Flower", 10, 22.0),
        ("AC-001", "Rolling Papers Classic", 2, 25.0),
        ("FL-003", "Blue Dream Flower", 8, 16.0),
        ("AC-002", "Canna Juice Berry", 3, 45.0),
        ("PR-004", "Wedding Cake Pre-Roll", 4, 35.0),
    ]

    for i in range(10):
        sale_date = base_day - timedelta(days=9 - i)
        items = []
        total = 0.0

        for j, product in enumerate(sample_items):
            if (i + j) % 3 == 0:
                product_id, name, qty, price = product
                quantity = max(1, qty + ((i + j) % 4) - 1)
                line_total = quantity * price
                total += line_total
                items.append(
                    {
                        "product_id": product_id,
                        "name": name,
                        "quantity": float(quantity),
                        "unit_price": float(price),
                        "line_total": float(line_total),
                    }
                )

        if items:
            demo_sales.append(
                {
                    "sale_id": make_id("SALE"),
                    "timestamp": datetime.combine(sale_date, datetime.min.time()).replace(hour=10 + i % 8).strftime("%Y-%m-%d %H:%M:%S"),
                    "payment_method": PAYMENT_METHODS[i % len(PAYMENT_METHODS)],
                    "items": items,
                    "total": float(total),
                }
            )

    return demo_sales


# ============================================================
# Data Persistence
# ============================================================

def save_json(path: Path, data: Any) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)


def load_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        save_json(path, fallback)
        return fallback

    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except json.JSONDecodeError:
        st.warning(f"{path.name} was corrupted or unreadable. Demo data has been reloaded.")
        save_json(path, fallback)
        return fallback


def load_inventory() -> pd.DataFrame:
    data = load_json(INVENTORY_FILE, default_inventory())
    df = pd.DataFrame(data)

    expected_cols = ["id", "name", "category", "unit", "quantity_on_hand", "unit_price", "daily_sales_estimate"]
    for col in expected_cols:
        if col not in df.columns:
            if col in ["quantity_on_hand", "unit_price", "daily_sales_estimate"]:
                df[col] = 0.0
            else:
                df[col] = ""

    df["quantity_on_hand"] = pd.to_numeric(df["quantity_on_hand"], errors="coerce").fillna(0.0)
    df["unit_price"] = pd.to_numeric(df["unit_price"], errors="coerce").fillna(0.0)
    df["daily_sales_estimate"] = pd.to_numeric(df["daily_sales_estimate"], errors="coerce").replace(0, pd.NA)
    df["stock_value"] = df["quantity_on_hand"] * df["unit_price"]
    df["days_stock_on_hand"] = (df["quantity_on_hand"] / df["daily_sales_estimate"]).fillna(999.0)
    df["status"] = df["days_stock_on_hand"].apply(get_status)
    return df


def save_inventory(df: pd.DataFrame) -> None:
    save_cols = ["id", "name", "category", "unit", "quantity_on_hand", "unit_price", "daily_sales_estimate"]
    clean_df = df[save_cols].copy()
    clean_df["quantity_on_hand"] = clean_df["quantity_on_hand"].astype(float)
    clean_df["unit_price"] = clean_df["unit_price"].astype(float)
    clean_df["daily_sales_estimate"] = clean_df["daily_sales_estimate"].astype(float)
    save_json(INVENTORY_FILE, clean_df.to_dict(orient="records"))


def load_sales() -> List[Dict[str, Any]]:
    return load_json(SALES_FILE, default_sales())


def save_sales(sales: List[Dict[str, Any]]) -> None:
    save_json(SALES_FILE, sales)


def reset_demo_data() -> None:
    save_json(INVENTORY_FILE, default_inventory())
    save_json(SALES_FILE, default_sales())
    st.session_state.cart = {}
    st.toast("Demo data reset successfully.", icon="✅")


# ============================================================
# Session State
# ============================================================

def init_state() -> None:
    if "cart" not in st.session_state:
        st.session_state.cart = {}
    if "new_sale_started" not in st.session_state:
        st.session_state.new_sale_started = False
    if "last_receipt" not in st.session_state:
        st.session_state.last_receipt = None


# ============================================================
# Components
# ============================================================

def hero(title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="saint-hero">
            <div class="saint-hero-title">{title}</div>
            <div class="saint-hero-subtitle">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def metric_card(label: str, value: str, help_text: str = "") -> None:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
            <div class="metric-help">{help_text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def inventory_display_df(df: pd.DataFrame) -> pd.DataFrame:
    output = df.copy()
    output["Product"] = output["name"]
    output["Category"] = output["category"]
    output["Unit"] = output["unit"]
    output["Qty"] = output["quantity_on_hand"].round(2)
    output["Price (R)"] = output["unit_price"].round(2)
    output["Stock Value (R)"] = output["stock_value"].round(2)
    output["Days on Hand"] = output["days_stock_on_hand"].round(1)
    output["Status"] = output["status"]
    return output[["Product", "Category", "Unit", "Qty", "Price (R)", "Stock Value (R)", "Days on Hand", "Status"]]


def sales_to_dataframe(sales: List[Dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for sale in sales:
        rows.append(
            {
                "Sale ID": sale.get("sale_id", ""),
                "Timestamp": sale.get("timestamp", ""),
                "Payment Method": sale.get("payment_method", ""),
                "Items": ", ".join([f"{item['name']} x {item['quantity']:g}" for item in sale.get("items", [])]),
                "Total (R)": float(sale.get("total", 0.0)),
            }
        )
    return pd.DataFrame(rows)


def sale_items_to_dataframe(sales: List[Dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for sale in sales:
        timestamp = sale.get("timestamp", "")
        sale_date = timestamp[:10]
        for item in sale.get("items", []):
            rows.append(
                {
                    "sale_id": sale.get("sale_id", ""),
                    "timestamp": timestamp,
                    "date": sale_date,
                    "product_id": item.get("product_id", ""),
                    "name": item.get("name", ""),
                    "quantity": float(item.get("quantity", 0.0)),
                    "unit_price": float(item.get("unit_price", 0.0)),
                    "line_total": float(item.get("line_total", 0.0)),
                    "payment_method": sale.get("payment_method", ""),
                }
            )
    return pd.DataFrame(rows)


# ============================================================
# Dashboard
# ============================================================

def page_dashboard(inventory: pd.DataFrame, sales: List[Dict[str, Any]]) -> None:
    hero(
        "Saint Herb Command Centre",
        "Premium inventory visibility, live retail performance, and stock control in one clean operating view.",
    )

    sales_df = sales_to_dataframe(sales)
    items_df = sale_items_to_dataframe(sales)

    total_stock_value = inventory["stock_value"].sum()
    today_sales = 0.0
    if not sales_df.empty:
        sales_df["Date"] = pd.to_datetime(sales_df["Timestamp"], errors="coerce").dt.date
        today_sales = sales_df.loc[sales_df["Date"] == date.today(), "Total (R)"].sum()

    low_stock_items = int((inventory["status"] == "Low").sum())
    avg_days = inventory["days_stock_on_hand"].replace(999, pd.NA).dropna().mean()
    avg_days = 0 if pd.isna(avg_days) else avg_days

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        metric_card("Total Stock Value", money(total_stock_value), "Auto-calculated from quantity × price")
    with col2:
        metric_card("Today's Sales", money(today_sales), f"Sales date: {today_string()}")
    with col3:
        metric_card("Low Stock Items", str(low_stock_items), "Items with fewer than 10 days on hand")
    with col4:
        metric_card("Avg Days on Hand", f"{avg_days:,.1f}", "Based on demo daily sales estimates")

    st.divider()

    c1, c2 = st.columns([1.1, 1])
    with c1:
        st.subheader("Stock Value by Category")
        category_stock = inventory.groupby("category", as_index=False)["stock_value"].sum()
        fig = px.bar(
            category_stock,
            x="category",
            y="stock_value",
            text_auto=".2s",
            labels={"category": "Category", "stock_value": "Stock Value (R)"},
            height=420,
        )
        fig.update_layout(margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.subheader("Recent Sales Trend")
        if sales_df.empty:
            st.info("No sales have been logged yet.")
        else:
            daily_sales = sales_df.groupby("Date", as_index=False)["Total (R)"].sum()
            fig = px.line(
                daily_sales,
                x="Date",
                y="Total (R)",
                markers=True,
                labels={"Total (R)": "Sales (R)"},
                height=420,
            )
            fig.update_layout(margin=dict(l=10, r=10, t=30, b=10))
            st.plotly_chart(fig, use_container_width=True)

    st.subheader("Top Selling Products")
    if items_df.empty:
        st.info("No product-level sales data yet.")
    else:
        top_products = (
            items_df.groupby("name", as_index=False)
            .agg(quantity=("quantity", "sum"), sales=("line_total", "sum"))
            .sort_values("sales", ascending=False)
            .head(10)
        )
        fig = px.bar(
            top_products,
            x="sales",
            y="name",
            orientation="h",
            text_auto=".2s",
            labels={"sales": "Sales (R)", "name": "Product"},
            height=420,
        )
        fig.update_layout(yaxis={"categoryorder": "total ascending"}, margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig, use_container_width=True)


# ============================================================
# Point of Sale
# ============================================================

def add_to_cart(product: pd.Series, quantity: float) -> None:
    if quantity <= 0:
        st.toast("Quantity must be greater than zero.", icon="⚠️")
        return

    product_id = str(product["id"])
    available = float(product["quantity_on_hand"])
    current_qty = float(st.session_state.cart.get(product_id, {}).get("quantity", 0.0))

    if current_qty + quantity > available:
        st.toast("Not enough stock available for that quantity.", icon="⚠️")
        return

    if product_id not in st.session_state.cart:
        st.session_state.cart[product_id] = {
            "product_id": product_id,
            "name": str(product["name"]),
            "category": str(product["category"]),
            "unit": str(product["unit"]),
            "quantity": 0.0,
            "unit_price": float(product["unit_price"]),
        }

    st.session_state.cart[product_id]["quantity"] += float(quantity)
    st.toast(f"Added {quantity:g} {product['unit']} of {product['name']}", icon="✅")


def cart_total() -> float:
    return sum(item["quantity"] * item["unit_price"] for item in st.session_state.cart.values())


def conclude_sale(inventory: pd.DataFrame, payment_method: str) -> bool:
    if not st.session_state.cart:
        st.warning("Your cart is empty.")
        return False

    updated_inventory = inventory.copy()
    sale_items = []

    for product_id, cart_item in st.session_state.cart.items():
        idx = updated_inventory.index[updated_inventory["id"] == product_id]
        if len(idx) == 0:
            st.error(f"Product not found: {cart_item['name']}")
            return False

        idx = idx[0]
        available = float(updated_inventory.loc[idx, "quantity_on_hand"])
        quantity = float(cart_item["quantity"])

        if quantity <= 0:
            st.error("Invalid quantity found in cart.")
            return False

        if quantity > available:
            st.error(f"Insufficient stock for {cart_item['name']}. Available: {available:g}")
            return False

        updated_inventory.loc[idx, "quantity_on_hand"] = available - quantity
        line_total = quantity * float(cart_item["unit_price"])
        sale_items.append(
            {
                "product_id": product_id,
                "name": cart_item["name"],
                "quantity": quantity,
                "unit_price": float(cart_item["unit_price"]),
                "line_total": line_total,
            }
        )

    save_inventory(updated_inventory)
    sales = load_sales()
    sale_record = {
        "sale_id": make_id("SALE"),
        "timestamp": now_string(),
        "payment_method": payment_method,
        "items": sale_items,
        "total": sum(item["line_total"] for item in sale_items),
    }
    sales.append(sale_record)
    save_sales(sales)

    st.session_state.last_receipt = sale_record
    st.session_state.cart = {}
    st.toast("Sale concluded successfully.", icon="✅")
    return True


def render_receipt(sale: Dict[str, Any]) -> None:
    st.success("Sale completed. Receipt preview:")
    st.markdown(f"**Receipt:** `{sale['sale_id']}`  \n**Time:** {sale['timestamp']}  \n**Payment:** {sale['payment_method']}")

    receipt_df = pd.DataFrame(sale["items"])
    receipt_df["quantity"] = receipt_df["quantity"].map(lambda x: f"{x:g}")
    receipt_df["unit_price"] = receipt_df["unit_price"].map(money)
    receipt_df["line_total"] = receipt_df["line_total"].map(money)
    receipt_df = receipt_df.rename(
        columns={
            "name": "Product",
            "quantity": "Qty",
            "unit_price": "Price",
            "line_total": "Line Total",
        }
    )
    st.dataframe(receipt_df[["Product", "Qty", "Price", "Line Total"]], use_container_width=True, hide_index=True)
    st.markdown(f"### Grand Total: {money(float(sale['total']))}")


def page_pos(inventory: pd.DataFrame) -> None:
    hero(
        "Point of Sale",
        "Fast checkout, live stock deduction, clean cart handling, and instant receipt preview.",
    )

    top1, top2, top3 = st.columns([1, 1, 2])
    with top1:
        if st.button("➕ New Sale", type="primary", use_container_width=True):
            st.session_state.cart = {}
            st.session_state.new_sale_started = True
            st.toast("New sale started.", icon="🛒")
    with top2:
        if st.button("Clear Cart", use_container_width=True):
            st.session_state.cart = {}
            st.toast("Cart cleared.", icon="🧹")

    st.divider()

    left, right = st.columns([1.65, 1], gap="large")

    with left:
        st.subheader("Catalog")
        search = st.text_input("Search product", placeholder="Search by product name or category...", label_visibility="collapsed")

        tab_labels = ["All", "Pre-Rolls", "Flower / Bud", "Accessories"]
        tabs = st.tabs(tab_labels)

        for tab, category_filter in zip(tabs, tab_labels):
            with tab:
                filtered = inventory.copy()
                if category_filter != "All":
                    filtered = filtered[filtered["category"] == category_filter]

                if search:
                    search_lower = search.lower()
                    filtered = filtered[
                        filtered["name"].str.lower().str.contains(search_lower, na=False)
                        | filtered["category"].str.lower().str.contains(search_lower, na=False)
                    ]

                if filtered.empty:
                    st.info("No products match the current filters.")
                    continue

                cols_per_row = 3
                rows = [filtered.iloc[i : i + cols_per_row] for i in range(0, len(filtered), cols_per_row)]

                for row in rows:
                    cols = st.columns(cols_per_row)
                    for col, (_, product) in zip(cols, row.iterrows()):
                        with col:
                            st.markdown(
                                f"""
                                <div class="product-card">
                                    <div class="product-icon">{icon_for_category(product['category'])}</div>
                                    <div class="product-name">{product['name']}</div>
                                    <div class="product-meta">{product['category']} • {product['quantity_on_hand']:g} {product['unit']} in stock</div>
                                    <div class="product-price">{money(float(product['unit_price']))} / {product['unit']}</div>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )

                            qty_key = f"qty_{category_filter}_{product['id']}"
                            qty = st.number_input(
                                "Qty",
                                min_value=0.0,
                                max_value=float(product["quantity_on_hand"]),
                                value=1.0 if float(product["quantity_on_hand"]) >= 1 else 0.0,
                                step=1.0 if product["unit"] != "gram" else 0.5,
                                key=qty_key,
                                label_visibility="collapsed",
                            )

                            b1, b2, b3, b4 = st.columns(4)
                            with b1:
                                if st.button("+1", key=f"plus1_{category_filter}_{product['id']}", use_container_width=True):
                                    add_to_cart(product, 1.0)
                            with b2:
                                if st.button("+5", key=f"plus5_{category_filter}_{product['id']}", use_container_width=True):
                                    add_to_cart(product, 5.0)
                            with b3:
                                if st.button("+10", key=f"plus10_{category_filter}_{product['id']}", use_container_width=True):
                                    add_to_cart(product, 10.0)
                            with b4:
                                if st.button("Add", key=f"add_{category_filter}_{product['id']}", type="primary", use_container_width=True):
                                    add_to_cart(product, qty)

    with right:
        st.markdown('<div class="cart-box">', unsafe_allow_html=True)
        st.subheader("Cart")

        if not st.session_state.cart:
            st.info("Cart is empty. Add products from the catalog.")
        else:
            for product_id, item in list(st.session_state.cart.items()):
                line_total = item["quantity"] * item["unit_price"]
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.markdown(f"**{item['name']}**")
                    st.caption(f"{item['quantity']:g} {item['unit']} × {money(item['unit_price'])}")
                with c2:
                    st.markdown(f"**{money(line_total)}**")
                    if st.button("Remove", key=f"remove_{product_id}", use_container_width=True):
                        del st.session_state.cart[product_id]
                        st.rerun()
                st.divider()

            st.caption("Grand Total")
            st.markdown(f'<div class="cart-total">{money(cart_total())}</div>', unsafe_allow_html=True)

            payment_method = st.selectbox("Payment Method", PAYMENT_METHODS)

            if st.button("Conclude Sale", type="primary", use_container_width=True):
                if conclude_sale(inventory, payment_method):
                    st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

        if st.session_state.last_receipt:
            st.divider()
            render_receipt(st.session_state.last_receipt)


# ============================================================
# Inventory
# ============================================================

def page_inventory(inventory: pd.DataFrame) -> None:
    hero(
        "Inventory Management",
        "Edit stock and pricing, add products, make manual adjustments, and monitor low-stock risk.",
    )

    total_stock_value = inventory["stock_value"].sum()
    metric_card("Total Stock Value", money(total_stock_value), "Live value based on the current inventory table")

    st.divider()

    st.subheader("Inventory Table")
    category_filter = st.multiselect("Filter by Category", CATEGORIES, default=CATEGORIES)
    status_filter = st.multiselect("Filter by Status", ["Low", "Medium", "Good"], default=["Low", "Medium", "Good"])

    table_df = inventory[
        inventory["category"].isin(category_filter)
        & inventory["status"].isin(status_filter)
    ].copy()

    display = inventory_display_df(table_df)

    def style_status(row):
        status = row["Status"]
        if status == "Good":
            return ["background-color: rgba(47, 209, 124, 0.12)"] * len(row)
        if status == "Medium":
            return ["background-color: rgba(247, 201, 72, 0.14)"] * len(row)
        return ["background-color: rgba(255, 107, 107, 0.16)"] * len(row)

    st.dataframe(
        display.style.apply(style_status, axis=1),
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Inline Editing")
    st.caption("Edit quantity, price, and daily sales estimate. Save changes to persist them.")

    editor_df = inventory[["id", "name", "category", "unit", "quantity_on_hand", "unit_price", "daily_sales_estimate"]].copy()
    edited_df = st.data_editor(
        editor_df,
        use_container_width=True,
        hide_index=True,
        disabled=["id", "name", "category", "unit"],
        column_config={
            "quantity_on_hand": st.column_config.NumberColumn("Qty", min_value=0.0, step=0.5),
            "unit_price": st.column_config.NumberColumn("Price (R)", min_value=0.0, step=1.0, format="R %.2f"),
            "daily_sales_estimate": st.column_config.NumberColumn("Daily Sales Estimate", min_value=0.01, step=0.5),
        },
    )

    if st.button("Save Inventory Changes", type="primary"):
        validation_errors = []

        for _, row in edited_df.iterrows():
            if safe_float(row["quantity_on_hand"]) < 0:
                validation_errors.append(f"{row['name']}: quantity cannot be negative.")
            if safe_float(row["unit_price"]) < 0:
                validation_errors.append(f"{row['name']}: price cannot be negative.")
            if safe_float(row["daily_sales_estimate"]) <= 0:
                validation_errors.append(f"{row['name']}: daily sales estimate must be above zero.")

        if validation_errors:
            for error in validation_errors:
                st.error(error)
        else:
            save_inventory(edited_df)
            st.toast("Inventory changes saved.", icon="✅")
            st.rerun()

    st.divider()

    c1, c2 = st.columns(2, gap="large")

    with c1:
        st.subheader("Add New Product")
        with st.form("add_product_form", clear_on_submit=True):
            name = st.text_input("Product Name", placeholder="Example: Product A")
            category = st.selectbox("Category", CATEGORIES)
            unit = st.selectbox("Unit", UNITS)
            quantity = st.number_input("Opening Quantity", min_value=0.0, value=0.0, step=1.0)
            price = st.number_input("Unit Price (R)", min_value=0.0, value=0.0, step=1.0)
            daily_estimate = st.number_input("Daily Sales Estimate", min_value=0.01, value=1.0, step=0.5)

            submitted = st.form_submit_button("Add Product", type="primary")
            if submitted:
                if not name.strip():
                    st.error("Product name is required.")
                elif name.strip().lower() in inventory["name"].str.lower().tolist():
                    st.error("A product with this name already exists.")
                else:
                    new_row = {
                        "id": make_id(category[:2].upper()),
                        "name": name.strip(),
                        "category": category,
                        "unit": unit,
                        "quantity_on_hand": float(quantity),
                        "unit_price": float(price),
                        "daily_sales_estimate": float(daily_estimate),
                    }
                    updated = pd.concat([inventory, pd.DataFrame([new_row])], ignore_index=True)
                    save_inventory(updated)
                    st.toast("Product added successfully.", icon="✅")
                    st.rerun()

    with c2:
        st.subheader("Manual Stock Adjustment")
        with st.form("stock_adjustment_form", clear_on_submit=True):
            product_name = st.selectbox("Product", inventory["name"].tolist())
            adjustment_type = st.radio("Adjustment Type", ["Add Stock", "Subtract Stock"], horizontal=True)
            adjustment_qty = st.number_input("Quantity", min_value=0.0, value=0.0, step=1.0)
            reason = st.text_area("Reason", placeholder="Example: supplier delivery, stock count correction, damaged stock")

            submitted = st.form_submit_button("Apply Adjustment", type="primary")
            if submitted:
                if adjustment_qty <= 0:
                    st.error("Adjustment quantity must be greater than zero.")
                elif not reason.strip():
                    st.error("Please provide a reason for audit visibility.")
                else:
                    updated = inventory.copy()
                    idx = updated.index[updated["name"] == product_name][0]
                    current_qty = float(updated.loc[idx, "quantity_on_hand"])

                    if adjustment_type == "Subtract Stock" and adjustment_qty > current_qty:
                        st.error("Cannot subtract more than the quantity on hand.")
                    else:
                        signed_qty = adjustment_qty if adjustment_type == "Add Stock" else -adjustment_qty
                        updated.loc[idx, "quantity_on_hand"] = current_qty + signed_qty
                        save_inventory(updated)
                        st.toast(f"Stock adjusted: {product_name}", icon="✅")
                        st.rerun()


# ============================================================
# Sales Reports
# ============================================================

def page_sales_reports(sales: List[Dict[str, Any]]) -> None:
    hero(
        "Sales History & Reports",
        "Review every sale, export transaction history, and see product/day level performance.",
    )

    sales_df = sales_to_dataframe(sales)
    items_df = sale_items_to_dataframe(sales)

    if sales_df.empty:
        st.info("No sales logged yet.")
        return

    sales_df["Timestamp Parsed"] = pd.to_datetime(sales_df["Timestamp"], errors="coerce")
    sales_df["Date"] = sales_df["Timestamp Parsed"].dt.date

    c1, c2, c3 = st.columns(3)
    with c1:
        metric_card("Total Sales", money(sales_df["Total (R)"].sum()), "All logged transactions")
    with c2:
        metric_card("Number of Sales", f"{len(sales_df):,}", "Transaction count")
    with c3:
        avg_sale = sales_df["Total (R)"].mean()
        metric_card("Average Basket", money(avg_sale), "Average sale value")

    st.divider()

    start_date = st.date_input("Start Date", value=min(sales_df["Date"]))
    end_date = st.date_input("End Date", value=max(sales_df["Date"]))

    filtered_sales = sales_df[(sales_df["Date"] >= start_date) & (sales_df["Date"] <= end_date)].copy()

    st.subheader("Sales History")
    st.dataframe(
        filtered_sales[["Sale ID", "Timestamp", "Payment Method", "Items", "Total (R)"]],
        use_container_width=True,
        hide_index=True,
    )

    csv = filtered_sales[["Sale ID", "Timestamp", "Payment Method", "Items", "Total (R)"]].to_csv(index=False).encode("utf-8")
    st.download_button(
        "Export Sales History to CSV",
        data=csv,
        file_name=f"saint_herb_sales_history_{today_string()}.csv",
        mime="text/csv",
        use_container_width=True,
    )

    st.divider()

    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.subheader("Sales by Day")
        by_day = filtered_sales.groupby("Date", as_index=False)["Total (R)"].sum()
        fig = px.line(by_day, x="Date", y="Total (R)", markers=True, height=420)
        fig.update_layout(margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.subheader("Payment Mix")
        payment_mix = filtered_sales.groupby("Payment Method", as_index=False)["Total (R)"].sum()
        fig = px.pie(payment_mix, names="Payment Method", values="Total (R)", hole=0.55, height=420)
        fig.update_layout(margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Sales by Product")
    if items_df.empty:
        st.info("No item-level data available.")
    else:
        items_df["date_parsed"] = pd.to_datetime(items_df["date"], errors="coerce").dt.date
        filtered_items = items_df[(items_df["date_parsed"] >= start_date) & (items_df["date_parsed"] <= end_date)]
        by_product = (
            filtered_items.groupby("name", as_index=False)
            .agg(quantity_sold=("quantity", "sum"), sales=("line_total", "sum"))
            .sort_values("sales", ascending=False)
        )

        st.dataframe(
            by_product.rename(
                columns={
                    "name": "Product",
                    "quantity_sold": "Quantity Sold",
                    "sales": "Sales (R)",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

        fig = px.bar(
            by_product.head(12),
            x="sales",
            y="name",
            orientation="h",
            text_auto=".2s",
            height=480,
            labels={"sales": "Sales (R)", "name": "Product"},
        )
        fig.update_layout(yaxis={"categoryorder": "total ascending"}, margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig, use_container_width=True)


# ============================================================
# Settings
# ============================================================

def page_settings() -> None:
    hero(
        "Settings",
        "Manage demo data, persistence files, and operational notes for future production hardening.",
    )

    st.subheader("Data Files")
    st.write(f"Inventory file: `{INVENTORY_FILE.resolve()}`")
    st.write(f"Sales file: `{SALES_FILE.resolve()}`")

    st.warning("Resetting demo data will overwrite the current local inventory and sales history files.")

    if st.button("Reset Demo Data", type="primary"):
        reset_demo_data()
        st.rerun()

    st.divider()

    st.subheader("Production Notes")
    st.markdown(
        """
        For a live retail environment, consider adding:
        - User login and cashier permissions.
        - Barcode scanning.
        - Tax/VAT treatment.
        - Supplier purchase orders.
        - Stock receiving workflow.
        - Audit logs for every inventory adjustment.
        - Cloud database such as PostgreSQL, Supabase, Neon, or Azure SQL.
        - Proper backups and role-based access.
        """
    )


# ============================================================
# Main App
# ============================================================

def main() -> None:
    inject_css()
    init_state()

    inventory = load_inventory()
    sales = load_sales()

    with st.sidebar:
        st.markdown("## 🌿 Saint Herb")
        st.caption("Premium Inventory + POS")
        st.divider()

        page = st.radio(
            "Navigation",
            ["Dashboard", "Point of Sale", "Inventory", "Sales Reports", "Settings"],
            label_visibility="collapsed",
        )

        st.divider()
        st.caption("Current Session")
        st.write(f"Cart items: **{len(st.session_state.cart)}**")
        st.write(f"Cart total: **{money(cart_total())}**")

        st.divider()
        st.caption("Demo build using neutral placeholder product data.")

    if page == "Dashboard":
        page_dashboard(inventory, sales)
    elif page == "Point of Sale":
        page_pos(inventory)
    elif page == "Inventory":
        page_inventory(inventory)
    elif page == "Sales Reports":
        page_sales_reports(sales)
    elif page == "Settings":
        page_settings()


if __name__ == "__main__":
    main()
