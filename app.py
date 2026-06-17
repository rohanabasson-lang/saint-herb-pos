"""
Saint Herb Premium Inventory Management + POS - FINAL POLISHED BUILD
====================================================================

This file is intentionally seeded with neutral Product 001-064 placeholders.
The authorised store owner can rename products and update quantities/prices inside the app.

MAJOR UPGRADE SUMMARY
---------------------
This version upgrades the original local-JSON Streamlit POS into a safer go-live lite build:

1. Monthly edit/void controls
   - A transaction can only be edited or voided during its open month window.
   - A month opens on the 2nd day of that transaction month.
   - A month closes at the end of the 1st day of the following month.
   - Editing/voiding requires staff/bartender full name and a mandatory reason.
   - Voids and edits are retained in sale modification history and in a separate audit file.

2. Audit trail
   - Adds saint_herb_audit.json.
   - Sales Reports now includes Sales History, Edit/Void Sales, Voids & Edits Log, Audit Trail, and Backups.

3. Pricing engine
   - Adds a modular PricingEngine class.
   - Supports total upfront investment, payback months, overhead recovery rate,
     default risk buffer, default margin, and expected monthly units.
   - Formula:
       Fixed Cost Buffer per Unit = (Total Upfront Investment × Overhead Recovery Rate) / Expected Volume
       Loaded Unit Cost = Unit Cost Input + Fixed Cost Buffer
       Suggested Selling Price = Loaded Unit Cost / (1 - Desired Margin % - Risk Buffer %)

4. Enhanced product creation/pricing
   - Add/edit product pricing from unit cost, desired margin, risk buffer, expected units.
   - Supports rounding to nearest/up/down 5 or 10.
   - Supports special deal text such as "3 for R100".
   - Supports per-unit, per-gram, and pack style selling modes.

5. Data preservation
   - Does not delete or overwrite existing saint_herb_sales.json transactions.
   - Local JSON files remain the temporary lightweight database.

6. Auto pricing integration
   - Inline Inventory saves now recalculate selling price when unit cost, desired margin,
     risk buffer, or expected monthly units change.
   - Existing manual prices are preserved when pricing drivers are unchanged.

How to run locally
------------------
1. Save this file as: app.py
2. Install dependencies:
   pip install streamlit pandas plotly

   Or, if using the ZIP package:
   pip install -r requirements.txt

3. Run:
   streamlit run app.py
"""

from __future__ import annotations

import copy
import io
import json
import math
import re
import uuid
import zipfile
from datetime import datetime, date, time, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
AUDIT_FILE = Path("saint_herb_audit.json")
PRICING_CONFIG_FILE = Path("saint_herb_pricing_config.json")

# Neutral operational categories. The authorised store owner can rename/update products in-app.
CATEGORIES = [
    "Prepared Items",
    "Bulk / By Weight",
    "Packaged Goods",
    "Beverages",
    "Oils & Topicals",
    "Sweets / Snacks",
    "Accessories / Other",
]
UNITS = ["unit", "gram", "pack", "bottle", "box"]
SELLING_MODES = ["Per Unit", "Per Gram", "Pack"]
PAYMENT_METHODS = ["Cash", "Card", "EFT", "Other"]
ROUNDING_OPTIONS = [
    "No rounding",
    "Round nearest 5",
    "Round up to 5",
    "Round down to 5",
    "Round nearest 10",
    "Round up to 10",
    "Round down to 10",
]


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
            .main .block-container { padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1450px; }
            h1, h2, h3 { letter-spacing: -0.03em; }
            .saint-hero {
                padding: 1.4rem 1.6rem;
                border: 1px solid var(--saint-border);
                border-radius: 24px;
                background: radial-gradient(circle at top left, rgba(47, 209, 124, 0.22), transparent 32%),
                            linear-gradient(135deg, rgba(19, 30, 24, 0.98), rgba(10, 14, 12, 0.92));
                box-shadow: 0 18px 50px rgba(0, 0, 0, 0.18);
                margin-bottom: 1rem;
            }
            .saint-hero-title { font-size: 2.3rem; font-weight: 800; color: white; margin: 0; }
            .saint-hero-subtitle { color: var(--saint-text-soft); margin-top: 0.35rem; font-size: 1rem; }
            .metric-card {
                padding: 1.05rem 1.15rem;
                border-radius: 20px;
                background: linear-gradient(145deg, rgba(255,255,255,0.08), rgba(255,255,255,0.025));
                border: 1px solid var(--saint-border);
                box-shadow: 0 12px 34px rgba(0,0,0,0.10);
                min-height: 120px;
            }
            .metric-label { color: var(--saint-text-soft); font-size: 0.82rem; text-transform: uppercase; letter-spacing: 0.08em; font-weight: 700; margin-bottom: 0.35rem; }
            .metric-value { font-size: 1.85rem; font-weight: 800; letter-spacing: -0.03em; }
            .metric-help { color: var(--saint-text-soft); font-size: 0.85rem; margin-top: 0.25rem; }
            .product-card {
                padding: 1rem;
                border-radius: 20px;
                background: linear-gradient(145deg, rgba(255,255,255,0.075), rgba(255,255,255,0.025));
                border: 1px solid var(--saint-border);
                box-shadow: 0 10px 30px rgba(0,0,0,0.10);
                margin-bottom: 0.8rem;
            }
            .product-icon {
                width: 100%; min-height: 78px; border-radius: 16px;
                background: radial-gradient(circle at 30% 20%, rgba(47, 209, 124, 0.40), transparent 28%),
                            linear-gradient(135deg, rgba(47,209,124,0.16), rgba(215,181,109,0.10));
                border: 1px solid rgba(47,209,124,0.16);
                display: flex; align-items: center; justify-content: center;
                font-size: 2.1rem; margin-bottom: 0.75rem;
            }
            .product-name { font-weight: 800; font-size: 1rem; line-height: 1.25; margin-bottom: 0.2rem; }
            .product-meta { color: var(--saint-text-soft); font-size: 0.82rem; }
            .product-price { font-size: 1.15rem; font-weight: 800; color: var(--saint-green); margin-top: 0.45rem; }
            .deal-pill { display: inline-block; padding: .25rem .55rem; border-radius: 999px; background: rgba(215,181,109,.18); border: 1px solid rgba(215,181,109,.35); color: #f0d99a; font-size: .78rem; font-weight: 800; margin-top: .45rem; }
            .cart-box { padding: 1rem; border-radius: 22px; background: linear-gradient(145deg, rgba(47,209,124,0.12), rgba(255,255,255,0.025)); border: 1px solid rgba(47,209,124,0.22); box-shadow: 0 14px 40px rgba(0,0,0,0.12); }
            .cart-total { font-size: 2rem; font-weight: 900; color: var(--saint-green); margin-top: 0.2rem; }
            .status-pill { padding: 0.25rem 0.55rem; border-radius: 999px; font-size: 0.78rem; font-weight: 800; display: inline-block; }
            .status-good { color: #0a3b22; background: #a7f3c8; }
            .status-medium { color: #443300; background: #ffe08a; }
            .status-low { color: #4a1111; background: #ffb3b3; }
            div[data-testid="stSidebar"] { border-right: 1px solid rgba(255,255,255,0.08); }
            div.stButton > button { border-radius: 14px; font-weight: 800; border: 1px solid rgba(47, 209, 124, 0.25); }
            div.stButton > button[kind="primary"] { background: linear-gradient(135deg, #2fd17c, #0f8f4f); color: white; border: 0; }
            @media (max-width: 900px) { .saint-hero-title { font-size: 1.7rem; } .metric-value { font-size: 1.35rem; } }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# Utility Functions
# ============================================================

def money(value: float) -> str:
    return f"R {float(value):,.2f}"


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def make_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def today_string() -> str:
    return date.today().isoformat()


def now_string() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def parse_dt(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", ""))
    except Exception:
        try:
            return pd.to_datetime(value).to_pydatetime()
        except Exception:
            return None


def get_status(days_on_hand: float) -> str:
    if days_on_hand < 10:
        return "Low"
    if days_on_hand <= 30:
        return "Medium"
    return "Good"


def icon_for_category(category: str) -> str:
    icons = {
        "Prepared Items": "◼",
        "Bulk / By Weight": "◆",
        "Packaged Goods": "⬢",
        "Beverages": "●",
        "Oils & Topicals": "◈",
        "Sweets / Snacks": "■",
        "Accessories / Other": "◇",
    }
    return icons.get(category, "●")


def parse_deal_text(deal_text: str) -> Optional[Tuple[int, float]]:
    """Parses simple deal text such as '3 for R100' or '2 for 50'."""
    if not deal_text:
        return None
    match = re.search(r"(\d+)\s*for\s*R?\s*([0-9]+(?:\.[0-9]+)?)", str(deal_text), re.IGNORECASE)
    if not match:
        return None
    qty = safe_int(match.group(1))
    price = safe_float(match.group(2))
    if qty <= 0 or price <= 0:
        return None
    return qty, price


def line_total_with_deal(quantity: float, unit_price: float, deal_text: str = "") -> float:
    deal = parse_deal_text(deal_text)
    if not deal:
        return float(quantity) * float(unit_price)

    # Bundle deals are only sensible for whole units.
    deal_qty, deal_price = deal
    whole_qty = int(quantity)
    remainder_fraction = float(quantity) - whole_qty
    bundles = whole_qty // deal_qty
    remainder_units = whole_qty % deal_qty
    return (bundles * deal_price) + (remainder_units * unit_price) + (remainder_fraction * unit_price)


# ============================================================
# JSON Persistence
# ============================================================

def save_json(path: Path, data: Any) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)


def load_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        save_json(path, fallback)
        return fallback
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except json.JSONDecodeError:
        backup_path = path.with_suffix(f".corrupt_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        try:
            path.rename(backup_path)
            st.warning(f"{path.name} was unreadable. A corrupt copy was saved as {backup_path.name} and a clean file was created.")
        except Exception:
            st.warning(f"{path.name} was unreadable. A clean file was created.")
        save_json(path, fallback)
        return fallback


# ============================================================
# Pricing Engine
# ============================================================

class PricingEngine:
    """
    Centralised pricing engine.

    Core formula:
      Fixed Cost Buffer per Unit = (Total Upfront Investment × Overhead Recovery Rate) / Expected Volume
      Expected Volume = Payback Months × Expected Monthly Units
      Loaded Unit Cost = Unit Cost Input + Fixed Cost Buffer
      Suggested Selling Price = Loaded Unit Cost / (1 - Desired Margin % - Risk Buffer %)
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    @staticmethod
    def default_config() -> Dict[str, Any]:
        return {
            "total_upfront_investment": 141600.0,
            "payback_months": 12.0,
            "overhead_recovery_rate": 0.10,
            "default_risk_buffer": 0.05,
            "default_margin": 0.40,
            "default_expected_monthly_units": 100.0,
            "default_rounding": "Round nearest 5",
        }

    @property
    def total_upfront_investment(self) -> float:
        return safe_float(self.config.get("total_upfront_investment"), 0.0)

    @property
    def payback_months(self) -> float:
        return max(safe_float(self.config.get("payback_months"), 1.0), 1.0)

    @property
    def overhead_recovery_rate(self) -> float:
        return max(safe_float(self.config.get("overhead_recovery_rate"), 0.0), 0.0)

    @property
    def default_expected_monthly_units(self) -> float:
        return max(safe_float(self.config.get("default_expected_monthly_units"), 1.0), 1.0)

    def fixed_cost_buffer(self, expected_monthly_units: Optional[float] = None) -> float:
        units = safe_float(expected_monthly_units, self.default_expected_monthly_units)
        units = max(units, 1.0)
        expected_volume = units * self.payback_months
        recoverable_cost = self.total_upfront_investment * self.overhead_recovery_rate
        return recoverable_cost / expected_volume if expected_volume else 0.0

    def calculate(
        self,
        unit_cost: float,
        desired_margin: Optional[float] = None,
        risk_buffer: Optional[float] = None,
        expected_monthly_units: Optional[float] = None,
        rounding: Optional[str] = None,
    ) -> Dict[str, float]:
        unit_cost = max(safe_float(unit_cost), 0.0)
        desired_margin = safe_float(desired_margin, safe_float(self.config.get("default_margin"), 0.40))
        risk_buffer = safe_float(risk_buffer, safe_float(self.config.get("default_risk_buffer"), 0.05))
        fixed_buffer = self.fixed_cost_buffer(expected_monthly_units)
        loaded_cost = unit_cost + fixed_buffer
        denominator = 1 - desired_margin - risk_buffer
        suggested = loaded_cost / denominator if denominator > 0 else 0.0
        rounded = self.round_price(suggested, rounding or self.config.get("default_rounding", "No rounding"))
        return {
            "unit_cost": unit_cost,
            "desired_margin": desired_margin,
            "risk_buffer": risk_buffer,
            "fixed_cost_buffer": fixed_buffer,
            "loaded_unit_cost": loaded_cost,
            "suggested_selling_price": suggested,
            "rounded_selling_price": rounded,
        }

    @staticmethod
    def round_price(price: float, rounding: str) -> float:
        price = safe_float(price)
        if price <= 0:
            return 0.0
        if rounding == "No rounding":
            return round(price, 2)
        if "5" in rounding:
            base = 5
        elif "10" in rounding:
            base = 10
        else:
            base = 1
        if "up" in rounding.lower():
            return float(math.ceil(price / base) * base)
        if "down" in rounding.lower():
            return float(math.floor(price / base) * base)
        return float(round(price / base) * base)


def load_pricing_config() -> Dict[str, Any]:
    data = load_json(PRICING_CONFIG_FILE, PricingEngine.default_config())
    default = PricingEngine.default_config()
    default.update(data if isinstance(data, dict) else {})
    return default


def save_pricing_config(config: Dict[str, Any]) -> None:
    save_json(PRICING_CONFIG_FILE, config)


# ============================================================
# Enhanced Pricing Integration
# ============================================================

def recalculate_product_price(row: Dict[str, Any], engine: PricingEngine, rounding: Optional[str] = None) -> float:
    """Recalculate the final selling price from a product row using the active PricingEngine.

    This uses the full pricing model, including setup-cost recovery / fixed cost buffer.
    It is intentionally reusable across Add Product, Edit Product Pricing, and the
    main Inventory inline editor.
    """
    result = engine.calculate(
        unit_cost=safe_float(row.get("unit_cost")),
        desired_margin=safe_float(row.get("desired_margin")),
        risk_buffer=safe_float(row.get("risk_buffer")),
        expected_monthly_units=safe_float(row.get("expected_monthly_units")),
        rounding=rounding or str(engine.config.get("default_rounding", "Round nearest 5")),
    )
    return safe_float(result.get("rounded_selling_price"))


def pricing_inputs_changed(edited_row: Dict[str, Any], original_row: Dict[str, Any]) -> bool:
    """Return True when fields that drive the pricing model changed.

    The inline inventory editor must not blindly recalculate every product price,
    otherwise neutral placeholders or manually overridden prices could be overwritten.
    """
    pricing_cols = ["unit_cost", "desired_margin", "risk_buffer", "expected_monthly_units"]
    for col in pricing_cols:
        if abs(safe_float(edited_row.get(col)) - safe_float(original_row.get(col))) > 1e-9:
            return True
    return False


def pricing_input_error(row: Dict[str, Any]) -> Optional[str]:
    """Validate pricing inputs before calculating a selling price."""
    margin = safe_float(row.get("desired_margin"))
    risk = safe_float(row.get("risk_buffer"))
    expected_units = safe_float(row.get("expected_monthly_units"))
    if margin < 0 or risk < 0:
        return "margin and risk buffer cannot be negative"
    if margin + risk >= 1:
        return "margin plus risk buffer must be below 100%"
    if expected_units <= 0:
        return "expected monthly units must be greater than zero"
    return None


# ============================================================
# Default Data
# ============================================================

def default_inventory() -> List[Dict[str, Any]]:
    """
    Neutral seed data only.

    This version creates all 64 current product placeholder slots:
    Product 001 through Product 064.

    Notes:
    - Product names remain generic placeholders so they can be renamed in-app.
    - Existing saved inventory is not overwritten.
    - load_inventory() appends any missing placeholder IDs, but keeps any edits already saved.
    """
    product_specs = [
        # product_no, category, unit, quantity, selling_price
        (1, "Prepared Items", "unit", 25, 125),
        (2, "Prepared Items", "unit", 25, 125),
        (3, "Prepared Items", "unit", 25, 65),
        (4, "Prepared Items", "unit", 25, 65),
        (5, "Prepared Items", "unit", 25, 65),
        (6, "Prepared Items", "unit", 21, 0),
        (7, "Prepared Items", "unit", 28, 0),
        (8, "Prepared Items", "unit", 31, 0),

        (9, "Bulk / By Weight", "gram", 10, 45),
        (10, "Bulk / By Weight", "gram", 50, 95),
        (11, "Bulk / By Weight", "gram", 50, 105),
        (12, "Bulk / By Weight", "gram", 50, 135),
        (13, "Bulk / By Weight", "gram", 50, 115),
        (14, "Bulk / By Weight", "gram", 130, 135),
        (15, "Bulk / By Weight", "gram", 130, 135),
        (16, "Bulk / By Weight", "gram", 130, 135),

        (17, "Beverages", "bottle", 6, 115),
        (18, "Beverages", "bottle", 6, 115),
        (19, "Beverages", "bottle", 6, 115),

        (20, "Packaged Goods", "unit", 5, 235),
        (21, "Packaged Goods", "unit", 5, 305),
        (22, "Packaged Goods", "unit", 5, 235),
        (23, "Packaged Goods", "unit", 5, 305),
        (24, "Packaged Goods", "unit", 5, 235),
        (25, "Packaged Goods", "unit", 5, 305),
        (26, "Packaged Goods", "unit", 4, 195),
        (27, "Packaged Goods", "unit", 4, 215),
        (28, "Packaged Goods", "unit", 4, 235),
        (29, "Packaged Goods", "unit", 4, 90),
        (30, "Packaged Goods", "unit", 3, 135),
        (31, "Beverages", "bottle", 3, 145),

        (32, "Oils & Topicals", "unit", 3, 325),
        (33, "Oils & Topicals", "unit", 3, 385),
        (34, "Oils & Topicals", "unit", 3, 325),
        (35, "Oils & Topicals", "unit", 3, 325),
        (36, "Oils & Topicals", "unit", 3, 525),
        (37, "Oils & Topicals", "unit", 3, 325),
        (38, "Oils & Topicals", "unit", 3, 235),
        (39, "Oils & Topicals", "unit", 3, 525),
        (40, "Oils & Topicals", "unit", 3, 385),
        (41, "Oils & Topicals", "unit", 3, 385),

        (42, "Sweets / Snacks", "unit", 125, 35),
        (43, "Sweets / Snacks", "unit", 50, 35),
        (44, "Sweets / Snacks", "unit", 100, 55),
        (45, "Sweets / Snacks", "unit", 2, 65),
        (46, "Sweets / Snacks", "unit", 1, 65),
        (47, "Sweets / Snacks", "unit", 5, 55),
        (48, "Sweets / Snacks", "unit", 5, 35),
        (49, "Sweets / Snacks", "unit", 2, 55),
        (50, "Sweets / Snacks", "unit", 4, 55),
        (51, "Sweets / Snacks", "unit", 4, 55),
        (52, "Sweets / Snacks", "unit", 1, 55),
        (53, "Sweets / Snacks", "unit", 1, 45),
        (54, "Sweets / Snacks", "unit", 5, 45),
        (55, "Sweets / Snacks", "unit", 3, 75),
        (56, "Sweets / Snacks", "unit", 1, 85),
        (57, "Sweets / Snacks", "unit", 1, 15),
        (58, "Sweets / Snacks", "unit", 1, 15),
        (59, "Sweets / Snacks", "unit", 5, 35),
        (60, "Sweets / Snacks", "unit", 5, 35),
        (61, "Sweets / Snacks", "unit", 1, 25),
        (62, "Sweets / Snacks", "unit", 1, 25),
        (63, "Sweets / Snacks", "unit", 1, 255),
        (64, "Accessories / Other", "unit", 9, 0),
    ]

    products: List[Dict[str, Any]] = []
    for product_no, category, unit, qty, price in product_specs:
        pid = f"ITM-{product_no:03d}"
        selling_mode = "Per Gram" if unit == "gram" else "Per Unit"
        qty_float = float(qty)
        price_float = float(price)
        products.append({
            "id": pid,
            "name": f"Product {product_no:03d}",
            "category": category,
            "unit": unit,
            "selling_mode": selling_mode,
            "pack_size": 1.0,
            "quantity_on_hand": qty_float,
            "opening_quantity": qty_float,
            "unit_price": price_float,
            # Keep unit cost neutral/blank. Update it in Pricing once the actual cost is known.
            "unit_cost": 0.0,
            "desired_margin": 0.40,
            "risk_buffer": 0.05,
            "expected_monthly_units": max(qty_float, 1.0),
            "special_deal": "",
            "daily_sales_estimate": max(qty_float / 14, 1.0),
        })
    return products


def append_missing_default_products(data: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], bool]:
    """
    Adds any missing Product 001-064 placeholders to an existing inventory file.

    This is deliberately non-destructive:
    - If a product ID already exists, the saved row is kept as-is.
    - If the owner renamed Product 001, that name is not overwritten.
    - Only missing placeholder rows are appended.
    """
    if not isinstance(data, list):
        return default_inventory(), True

    existing_ids = {str(item.get("id", "")) for item in data if isinstance(item, dict)}
    updated = list(data)
    changed = False

    for placeholder in default_inventory():
        if placeholder["id"] not in existing_ids:
            updated.append(placeholder)
            existing_ids.add(placeholder["id"])
            changed = True

    return updated, changed


def default_sales() -> List[Dict[str, Any]]:
    return []


def default_audit() -> List[Dict[str, Any]]:
    return []


# ============================================================
# Data Loading and Normalisation
# ============================================================

def load_inventory() -> pd.DataFrame:
    data = load_json(INVENTORY_FILE, default_inventory())
    if not isinstance(data, list):
        data = default_inventory()
        save_json(INVENTORY_FILE, data)
    else:
        data, placeholders_added = append_missing_default_products(data)
        if placeholders_added:
            save_json(INVENTORY_FILE, data)
    df = pd.DataFrame(data)

    expected_cols = {
        "id": "",
        "name": "",
        "category": "Accessories / Other",
        "unit": "unit",
        "selling_mode": "Per Unit",
        "pack_size": 1.0,
        "quantity_on_hand": 0.0,
        "opening_quantity": None,
        "unit_price": 0.0,
        "unit_cost": 0.0,
        "desired_margin": 0.40,
        "risk_buffer": 0.05,
        "expected_monthly_units": 1.0,
        "special_deal": "",
        "daily_sales_estimate": 1.0,
    }
    for col, default in expected_cols.items():
        if col not in df.columns:
            if col == "opening_quantity" and "quantity_on_hand" in df.columns:
                df[col] = df["quantity_on_hand"]
            else:
                df[col] = default

    numeric_cols = ["quantity_on_hand", "opening_quantity", "unit_price", "unit_cost", "desired_margin", "risk_buffer", "expected_monthly_units", "pack_size", "daily_sales_estimate"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    df["opening_quantity"] = df["opening_quantity"].fillna(df["quantity_on_hand"])
    df["daily_sales_estimate"] = df["daily_sales_estimate"].replace(0, pd.NA)
    df["stock_value"] = df["quantity_on_hand"] * df["unit_price"]
    df["opening_stock_value"] = df["opening_quantity"] * df["unit_price"]
    df["sold_quantity"] = (df["opening_quantity"] - df["quantity_on_hand"]).clip(lower=0)
    df["sold_stock_value"] = df["sold_quantity"] * df["unit_price"]
    df["days_stock_on_hand"] = (df["quantity_on_hand"] / df["daily_sales_estimate"]).fillna(999.0)
    df["status"] = df["days_stock_on_hand"].apply(get_status)
    return df


def save_inventory(df: pd.DataFrame) -> None:
    save_cols = [
        "id", "name", "category", "unit", "selling_mode", "pack_size", "quantity_on_hand", "opening_quantity",
        "unit_price", "unit_cost", "desired_margin", "risk_buffer", "expected_monthly_units", "special_deal", "daily_sales_estimate",
    ]
    clean = df.copy()
    for col in save_cols:
        if col not in clean.columns:
            clean[col] = "" if col in ["id", "name", "category", "unit", "selling_mode", "special_deal"] else 0.0
    save_json(INVENTORY_FILE, clean[save_cols].to_dict(orient="records"))


def normalise_sale(sale: Dict[str, Any]) -> Dict[str, Any]:
    sale = copy.deepcopy(sale)
    sale.setdefault("sale_id", make_id("SALE"))
    sale.setdefault("timestamp", now_string())
    sale.setdefault("payment_method", "Other")
    sale.setdefault("items", [])
    sale.setdefault("status", "active")
    sale.setdefault("modification_history", [])
    sale.setdefault("created_at", sale.get("timestamp", now_string()))
    sale.setdefault("total", sum(safe_float(item.get("line_total")) for item in sale.get("items", [])))
    return sale


def load_sales() -> List[Dict[str, Any]]:
    data = load_json(SALES_FILE, default_sales())
    if not isinstance(data, list):
        data = []
        save_json(SALES_FILE, data)
    return [normalise_sale(sale) for sale in data if isinstance(sale, dict)]


def save_sales(sales: List[Dict[str, Any]]) -> None:
    save_json(SALES_FILE, [normalise_sale(sale) for sale in sales])


def load_audit() -> List[Dict[str, Any]]:
    data = load_json(AUDIT_FILE, default_audit())
    return data if isinstance(data, list) else []


def save_audit(audit: List[Dict[str, Any]]) -> None:
    save_json(AUDIT_FILE, audit)


def append_audit(action: str, sale_id: str, bartender: str, reason: str, before: Any = None, after: Any = None, metadata: Optional[Dict[str, Any]] = None) -> None:
    audit = load_audit()
    audit.append({
        "audit_id": make_id("AUDIT"),
        "timestamp": now_string(),
        "action": action,
        "sale_id": sale_id,
        "bartender": bartender,
        "reason": reason,
        "before": before,
        "after": after,
        "metadata": metadata or {},
    })
    save_audit(audit)


# ============================================================
# Monthly Editing / Void Lock Logic
# ============================================================

def edit_window_for_sale(sale_timestamp: Any) -> Tuple[Optional[datetime], Optional[datetime]]:
    sale_dt = parse_dt(sale_timestamp)
    if not sale_dt:
        return None, None
    start = datetime.combine(date(sale_dt.year, sale_dt.month, 2), time.min)
    if sale_dt.month == 12:
        next_month = date(sale_dt.year + 1, 1, 1)
    else:
        next_month = date(sale_dt.year, sale_dt.month + 1, 1)
    end = datetime.combine(next_month, time.max)
    return start, end


def can_modify_sale(sale: Dict[str, Any], now: Optional[datetime] = None) -> Tuple[bool, str]:
    now = now or datetime.now()
    if sale.get("status") == "voided":
        return False, "This sale is already voided and cannot be edited again."
    start, end = edit_window_for_sale(sale.get("timestamp"))
    if not start or not end:
        return False, "This sale has an invalid timestamp, so editing/voiding is blocked."
    if now < start:
        return False, f"This sale can only be edited/voided from {start.strftime('%Y-%m-%d %H:%M')} onwards."
    if now > end:
        return False, f"Editing/voiding is closed for this sale. The window ended on {end.strftime('%Y-%m-%d %H:%M')}."
    return True, f"Open for editing/voiding until {end.strftime('%Y-%m-%d %H:%M')}."


# ============================================================
# Reporting Helpers
# ============================================================

def inventory_display_df(df: pd.DataFrame) -> pd.DataFrame:
    output = df.copy()
    output["Product"] = output["name"]
    output["Category"] = output["category"]
    output["Unit"] = output["unit"]
    output["Mode"] = output["selling_mode"]
    output["Qty"] = output["quantity_on_hand"].round(2)
    output["Cost (R)"] = output["unit_cost"].round(2)
    output["Price (R)"] = output["unit_price"].round(2)
    output["Stock Value (R)"] = output["stock_value"].round(2)
    output["Days on Hand"] = output["days_stock_on_hand"].round(1)
    output["Deal"] = output["special_deal"].fillna("")
    output["Status"] = output["status"]
    return output[["Product", "Category", "Unit", "Mode", "Qty", "Cost (R)", "Price (R)", "Stock Value (R)", "Days on Hand", "Deal", "Status"]]


def sales_to_dataframe(sales: List[Dict[str, Any]], include_voided: bool = True) -> pd.DataFrame:
    rows = []
    for sale in sales:
        sale = normalise_sale(sale)
        if not include_voided and sale.get("status") == "voided":
            continue
        rows.append({
            "Sale ID": sale.get("sale_id", ""),
            "Timestamp": sale.get("timestamp", ""),
            "Status": sale.get("status", "active"),
            "Payment Method": sale.get("payment_method", ""),
            "Items": ", ".join([f"{item.get('name', '')} x {safe_float(item.get('quantity')):g}" for item in sale.get("items", [])]),
            "Total (R)": safe_float(sale.get("total")),
            "Modified Count": len(sale.get("modification_history", [])),
        })
    return pd.DataFrame(rows)


def sale_items_to_dataframe(sales: List[Dict[str, Any]], include_voided: bool = False) -> pd.DataFrame:
    rows = []
    for sale in sales:
        sale = normalise_sale(sale)
        if sale.get("status") == "voided" and not include_voided:
            continue
        timestamp = sale.get("timestamp", "")
        sale_date = str(timestamp)[:10]
        for item in sale.get("items", []):
            rows.append({
                "sale_id": sale.get("sale_id", ""),
                "timestamp": timestamp,
                "date": sale_date,
                "status": sale.get("status", "active"),
                "product_id": item.get("product_id", ""),
                "name": item.get("name", ""),
                "quantity": safe_float(item.get("quantity")),
                "unit_price": safe_float(item.get("unit_price")),
                "line_total": safe_float(item.get("line_total")),
                "payment_method": sale.get("payment_method", ""),
            })
    return pd.DataFrame(rows)


def stock_valuation_summary(inventory: pd.DataFrame, sales: List[Dict[str, Any]]) -> Dict[str, float]:
    active_sales = [s for s in sales if normalise_sale(s).get("status") != "voided"]
    opening_stock_value = float(inventory["opening_stock_value"].sum()) if "opening_stock_value" in inventory.columns else 0.0
    current_stock_value = float(inventory["stock_value"].sum()) if "stock_value" in inventory.columns else 0.0
    total_sales_value = float(sum(safe_float(sale.get("total")) for sale in active_sales))
    today_sales_value = sum(safe_float(sale.get("total")) for sale in active_sales if str(sale.get("timestamp", ""))[:10] == today_string())
    return {
        "opening_stock_value": opening_stock_value,
        "current_stock_value": current_stock_value,
        "total_sales_value": total_sales_value,
        "today_sales_value": today_sales_value,
        "sales_count": len(active_sales),
        "value_balance_less_sales": opening_stock_value - total_sales_value,
        "has_sales": len(active_sales) > 0,
    }


def build_backup_zip(inventory: pd.DataFrame, sales: List[Dict[str, Any]], only_today: bool = False) -> bytes:
    sales_df = sales_to_dataframe(sales, include_voided=True)
    items_df = sale_items_to_dataframe(sales, include_voided=True)
    audit_df = pd.DataFrame(load_audit())

    if not sales_df.empty:
        sales_df["Date"] = pd.to_datetime(sales_df["Timestamp"], errors="coerce").dt.date
    if not items_df.empty:
        items_df["date_parsed"] = pd.to_datetime(items_df["date"], errors="coerce").dt.date
    if only_today:
        today = date.today()
        if not sales_df.empty:
            sales_df = sales_df[sales_df["Date"] == today].copy()
        if not items_df.empty:
            items_df = items_df[items_df["date_parsed"] == today].copy()

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("inventory_current.csv", inventory_display_df(inventory).to_csv(index=False))
        zf.writestr("sales_summary.csv", sales_df.to_csv(index=False))
        zf.writestr("sales_line_items.csv", items_df.to_csv(index=False))
        zf.writestr("audit_trail.csv", audit_df.to_csv(index=False))
        zf.writestr("raw_inventory.json", inventory.to_json(orient="records", indent=2))
        zf.writestr("raw_sales.json", json.dumps(sales, indent=2, ensure_ascii=False))
        zf.writestr("raw_audit.json", json.dumps(load_audit(), indent=2, ensure_ascii=False))
        zf.writestr("pricing_config.json", json.dumps(load_pricing_config(), indent=2))
        zf.writestr("backup_notes.txt", f"Saint Herb backup created at {now_string()}\nOnly today: {only_today}\n")
    buffer.seek(0)
    return buffer.getvalue()


# ============================================================
# UI Components
# ============================================================

def hero(title: str, subtitle: str) -> None:
    st.markdown(f"""
    <div class="saint-hero">
        <div class="saint-hero-title">{title}</div>
        <div class="saint-hero-subtitle">{subtitle}</div>
    </div>
    """, unsafe_allow_html=True)


def metric_card(label: str, value: str, help_text: str = "") -> None:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">{label}</div>
        <div class="metric-value">{value}</div>
        <div class="metric-help">{help_text}</div>
    </div>
    """, unsafe_allow_html=True)


# ============================================================
# POS Logic
# ============================================================

def add_to_cart(product: pd.Series, quantity: float) -> None:
    if quantity <= 0:
        st.toast("Quantity must be greater than zero.", icon="⚠️")
        return
    unit_price = safe_float(product.get("unit_price"))
    if unit_price <= 0:
        st.toast("This product has no selling price yet. Update pricing before selling.", icon="⚠️")
        return
    product_id = str(product["id"])
    available = safe_float(product.get("quantity_on_hand"))
    current_qty = safe_float(st.session_state.cart.get(product_id, {}).get("quantity"))
    if current_qty + quantity > available:
        st.toast("Not enough stock available for that quantity.", icon="⚠️")
        return
    if product_id not in st.session_state.cart:
        st.session_state.cart[product_id] = {
            "product_id": product_id,
            "name": str(product.get("name", "")),
            "category": str(product.get("category", "")),
            "unit": str(product.get("unit", "unit")),
            "quantity": 0.0,
            "unit_price": unit_price,
            "special_deal": str(product.get("special_deal", "") or ""),
        }
    st.session_state.cart[product_id]["quantity"] += float(quantity)
    st.toast(f"Added {quantity:g} {product.get('unit', 'unit')} of {product.get('name', '')}", icon="✅")


def cart_total() -> float:
    return sum(line_total_with_deal(item["quantity"], item["unit_price"], item.get("special_deal", "")) for item in st.session_state.cart.values())


def conclude_sale(inventory: pd.DataFrame, payment_method: str) -> bool:
    if not st.session_state.cart:
        st.warning("Your cart is empty.")
        return False
    updated_inventory = inventory.copy()
    sale_items = []
    for product_id, cart_item in st.session_state.cart.items():
        idx = updated_inventory.index[updated_inventory["id"].astype(str) == str(product_id)]
        if len(idx) == 0:
            st.error(f"Product not found: {cart_item['name']}")
            return False
        idx = idx[0]
        available = safe_float(updated_inventory.loc[idx, "quantity_on_hand"])
        quantity = safe_float(cart_item.get("quantity"))
        if quantity <= 0:
            st.error("Invalid quantity found in cart.")
            return False
        if quantity > available:
            st.error(f"Insufficient stock for {cart_item['name']}. Available: {available:g}")
            return False
        updated_inventory.loc[idx, "quantity_on_hand"] = available - quantity
        line_total = line_total_with_deal(quantity, cart_item["unit_price"], cart_item.get("special_deal", ""))
        sale_items.append({
            "product_id": product_id,
            "name": cart_item["name"],
            "quantity": quantity,
            "unit_price": safe_float(cart_item["unit_price"]),
            "line_total": line_total,
            "special_deal": cart_item.get("special_deal", ""),
        })
    save_inventory(updated_inventory)
    sales = load_sales()
    sale_record = normalise_sale({
        "sale_id": make_id("SALE"),
        "timestamp": now_string(),
        "created_at": now_string(),
        "payment_method": payment_method,
        "items": sale_items,
        "total": sum(item["line_total"] for item in sale_items),
        "status": "active",
        "modification_history": [],
    })
    sales.append(sale_record)
    save_sales(sales)
    append_audit("SALE_CREATED", sale_record["sale_id"], "System", "Sale concluded through POS", before=None, after=sale_record)
    st.session_state.last_receipt = sale_record
    st.session_state.cart = {}
    st.toast("Sale concluded successfully.", icon="✅")
    return True


def render_receipt(sale: Dict[str, Any]) -> None:
    st.success("Sale completed. Receipt preview:")
    st.markdown(f"**Receipt:** `{sale['sale_id']}`  \n**Time:** {sale['timestamp']}  \n**Payment:** {sale['payment_method']}")
    receipt_df = pd.DataFrame(sale["items"])
    if not receipt_df.empty:
        receipt_df["quantity"] = receipt_df["quantity"].map(lambda x: f"{safe_float(x):g}")
        receipt_df["unit_price"] = receipt_df["unit_price"].map(money)
        receipt_df["line_total"] = receipt_df["line_total"].map(money)
        receipt_df = receipt_df.rename(columns={"name": "Product", "quantity": "Qty", "unit_price": "Price", "line_total": "Line Total", "special_deal": "Deal"})
        cols = [c for c in ["Product", "Qty", "Price", "Deal", "Line Total"] if c in receipt_df.columns]
        st.dataframe(receipt_df[cols], use_container_width=True, hide_index=True)
    st.markdown(f"### Grand Total: {money(safe_float(sale['total']))}")


# ============================================================
# Sale Edit / Void Logic
# ============================================================

def restore_stock_for_items(inventory: pd.DataFrame, items: List[Dict[str, Any]]) -> pd.DataFrame:
    updated = inventory.copy()
    for item in items:
        product_id = str(item.get("product_id", ""))
        qty = safe_float(item.get("quantity"))
        idx = updated.index[updated["id"].astype(str) == product_id]
        if len(idx) > 0:
            updated.loc[idx[0], "quantity_on_hand"] = safe_float(updated.loc[idx[0], "quantity_on_hand"]) + qty
    return updated


def apply_stock_delta_for_edit(inventory: pd.DataFrame, original_items: List[Dict[str, Any]], edited_items: List[Dict[str, Any]]) -> Tuple[bool, str, pd.DataFrame]:
    updated = inventory.copy()
    old_qty = {str(i.get("product_id")): safe_float(i.get("quantity")) for i in original_items}
    new_qty = {str(i.get("product_id")): safe_float(i.get("quantity")) for i in edited_items}
    all_ids = set(old_qty) | set(new_qty)
    for product_id in all_ids:
        delta = new_qty.get(product_id, 0.0) - old_qty.get(product_id, 0.0)
        idx = updated.index[updated["id"].astype(str) == product_id]
        if len(idx) == 0:
            return False, f"Product {product_id} was not found in inventory.", updated
        current = safe_float(updated.loc[idx[0], "quantity_on_hand"])
        if delta > current:
            name = str(updated.loc[idx[0], "name"])
            return False, f"Not enough stock to increase sale quantity for {name}. Available: {current:g}; extra needed: {delta:g}.", updated
        updated.loc[idx[0], "quantity_on_hand"] = current - delta
    return True, "Stock adjusted.", updated


def void_sale(sale_id: str, bartender: str, reason: str) -> Tuple[bool, str]:
    sales = load_sales()
    inventory = load_inventory()
    for i, sale in enumerate(sales):
        if sale.get("sale_id") != sale_id:
            continue
        allowed, msg = can_modify_sale(sale)
        if not allowed:
            return False, msg
        if not bartender.strip() or not reason.strip():
            return False, "Bartender full name and reason are required."
        before = copy.deepcopy(sale)
        inventory = restore_stock_for_items(inventory, sale.get("items", []))
        sale["status"] = "voided"
        sale["voided_at"] = now_string()
        sale["voided_by"] = bartender.strip()
        sale["void_reason"] = reason.strip()
        sale.setdefault("modification_history", []).append({
            "action": "VOID",
            "timestamp": now_string(),
            "bartender": bartender.strip(),
            "reason": reason.strip(),
            "original_record": before,
        })
        sales[i] = sale
        save_inventory(inventory)
        save_sales(sales)
        append_audit("SALE_VOIDED", sale_id, bartender.strip(), reason.strip(), before=before, after=sale)
        return True, "Sale voided and stock restored."
    return False, "Sale not found."


def edit_sale(sale_id: str, edited_items: List[Dict[str, Any]], new_payment_method: str, bartender: str, reason: str) -> Tuple[bool, str]:
    sales = load_sales()
    inventory = load_inventory()
    for i, sale in enumerate(sales):
        if sale.get("sale_id") != sale_id:
            continue
        allowed, msg = can_modify_sale(sale)
        if not allowed:
            return False, msg
        if not bartender.strip() or not reason.strip():
            return False, "Bartender full name and reason are required."
        before = copy.deepcopy(sale)
        ok, stock_msg, updated_inventory = apply_stock_delta_for_edit(inventory, sale.get("items", []), edited_items)
        if not ok:
            return False, stock_msg
        new_total = sum(safe_float(item.get("line_total")) for item in edited_items)
        sale["items"] = edited_items
        sale["payment_method"] = new_payment_method
        sale["total"] = new_total
        sale["last_edited_at"] = now_string()
        sale["last_edited_by"] = bartender.strip()
        sale.setdefault("modification_history", []).append({
            "action": "EDIT",
            "timestamp": now_string(),
            "bartender": bartender.strip(),
            "reason": reason.strip(),
            "original_record": before,
            "updated_items": edited_items,
        })
        sales[i] = sale
        save_inventory(updated_inventory)
        save_sales(sales)
        append_audit("SALE_EDITED", sale_id, bartender.strip(), reason.strip(), before=before, after=sale)
        return True, "Sale edited and stock adjusted."
    return False, "Sale not found."


# ============================================================
# Pages
# ============================================================

def page_dashboard(inventory: pd.DataFrame, sales: List[Dict[str, Any]]) -> None:
    hero("Saint Herb Command Centre", "Premium inventory visibility, live retail performance, and stock control in one clean operating view.")
    valuation = stock_valuation_summary(inventory, sales)
    low_stock_items = int((inventory["status"] == "Low").sum())
    avg_days = inventory["days_stock_on_hand"].replace(999, pd.NA).dropna().mean()
    avg_days = 0 if pd.isna(avg_days) else avg_days

    if not valuation["has_sales"]:
        col1, col2, col3, col4 = st.columns(4)
        with col1: metric_card("Total Stock Value", money(valuation["current_stock_value"]), "Current value of all stock loaded")
        with col2: metric_card("Sales Count", "0", "No active sales have been logged yet")
        with col3: metric_card("Low Stock Items", str(low_stock_items), "Items with fewer than 10 days on hand")
        with col4: metric_card("Avg Days on Hand", f"{avg_days:,.1f}", "Based on daily sales estimates")
    else:
        col1, col2, col3, col4 = st.columns(4)
        with col1: metric_card("Opening Stock Value", money(valuation["opening_stock_value"]), "Loaded stock value before sales")
        with col2: metric_card("Total Sales", money(valuation["total_sales_value"]), "All active logged sales")
        with col3: metric_card("Value Balance", money(valuation["value_balance_less_sales"]), "Opening stock value less active sales")
        with col4: metric_card("Current Stock Value", money(valuation["current_stock_value"]), "Remaining stock value after deductions")

    st.divider()
    c1, c2 = st.columns([1.1, 1])
    with c1:
        st.subheader("Current Stock Value by Category")
        category_stock = inventory.groupby("category", as_index=False)["stock_value"].sum()
        fig = px.bar(category_stock, x="category", y="stock_value", text_auto=".2s", labels={"category": "Category", "stock_value": "Stock Value (R)"}, height=420)
        fig.update_layout(margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        st.subheader("Recent Sales Trend")
        sales_df = sales_to_dataframe(sales, include_voided=False)
        if sales_df.empty:
            st.info("No sales have been logged yet.")
        else:
            sales_df["Date"] = pd.to_datetime(sales_df["Timestamp"], errors="coerce").dt.date
            daily_sales = sales_df.groupby("Date", as_index=False)["Total (R)"].sum()
            fig = px.line(daily_sales, x="Date", y="Total (R)", markers=True, height=420)
            fig.update_layout(margin=dict(l=10, r=10, t=30, b=10))
            st.plotly_chart(fig, use_container_width=True)

    st.subheader("Top Selling Products")
    items_df = sale_items_to_dataframe(sales, include_voided=False)
    if items_df.empty:
        st.info("No product-level sales data yet.")
    else:
        top = items_df.groupby("name", as_index=False).agg(quantity=("quantity", "sum"), sales=("line_total", "sum")).sort_values("sales", ascending=False).head(10)
        fig = px.bar(top, x="sales", y="name", orientation="h", text_auto=".2s", height=420, labels={"sales": "Sales (R)", "name": "Product"})
        fig.update_layout(yaxis={"categoryorder": "total ascending"}, margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig, use_container_width=True)


def page_pos(inventory: pd.DataFrame) -> None:
    hero("Point of Sale", "Fast checkout, live stock deduction, deal-aware cart totals, and instant receipt preview.")
    top1, top2, _ = st.columns([1, 1, 2])
    with top1:
        if st.button("➕ New Sale", type="primary", use_container_width=True):
            st.session_state.cart = {}
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
        tab_labels = ["All"] + CATEGORIES
        tabs = st.tabs(tab_labels)
        for tab, category_filter in zip(tabs, tab_labels):
            with tab:
                filtered = inventory.copy()
                if category_filter != "All":
                    filtered = filtered[filtered["category"] == category_filter]
                if search:
                    s = search.lower()
                    filtered = filtered[filtered["name"].str.lower().str.contains(s, na=False) | filtered["category"].str.lower().str.contains(s, na=False)]
                if filtered.empty:
                    st.info("No products match the current filters.")
                    continue
                rows = [filtered.iloc[i:i + 3] for i in range(0, len(filtered), 3)]
                for row in rows:
                    cols = st.columns(3)
                    for col, (_, product) in zip(cols, row.iterrows()):
                        with col:
                            deal_html = f'<div class="deal-pill">{product.get("special_deal", "")}</div>' if str(product.get("special_deal", "") or "").strip() else ""
                            st.markdown(f"""
                            <div class="product-card">
                                <div class="product-icon">{icon_for_category(product['category'])}</div>
                                <div class="product-name">{product['name']}</div>
                                <div class="product-meta">{product['category']} • {safe_float(product['quantity_on_hand']):g} {product['unit']} in stock</div>
                                <div class="product-price">{money(product['unit_price'])} / {product['unit']}</div>
                                {deal_html}
                            </div>
                            """, unsafe_allow_html=True)
                            qty_key = f"qty_{category_filter}_{product['id']}"
                            step = 0.5 if str(product.get("unit")) == "gram" or str(product.get("selling_mode")) == "Per Gram" else 1.0
                            qty = st.number_input("Qty", min_value=0.0, max_value=safe_float(product["quantity_on_hand"]), value=1.0 if safe_float(product["quantity_on_hand"]) >= 1 else 0.0, step=step, key=qty_key, label_visibility="collapsed")
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
                line_total = line_total_with_deal(item["quantity"], item["unit_price"], item.get("special_deal", ""))
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.markdown(f"**{item['name']}**")
                    deal_note = f" • Deal: {item.get('special_deal')}" if item.get("special_deal") else ""
                    st.caption(f"{item['quantity']:g} {item['unit']} × {money(item['unit_price'])}{deal_note}")
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


def page_inventory(inventory: pd.DataFrame) -> None:
    hero("Inventory Management", "Edit stock, pricing metadata, product details, auto-recalculate pricing drivers, and monitor low-stock risk.")
    valuation = stock_valuation_summary(inventory, load_sales())
    if not valuation["has_sales"]:
        c1, c2, c3 = st.columns(3)
        with c1: metric_card("Total Stock Value", money(valuation["current_stock_value"]), "Current value of all stock loaded")
        with c2: metric_card("Sales Count", "0", "No active sales have been logged yet")
        with c3: metric_card("Products Loaded", f"{len(inventory):,}", "Current number of products")
    else:
        c1, c2, c3, c4 = st.columns(4)
        with c1: metric_card("Opening Stock Value", money(valuation["opening_stock_value"]), "Loaded stock value before sales")
        with c2: metric_card("Total Sales", money(valuation["total_sales_value"]), "All active logged sales")
        with c3: metric_card("Value Balance", money(valuation["value_balance_less_sales"]), "Opening stock less sales")
        with c4: metric_card("Current Stock Value", money(valuation["current_stock_value"]), "Live stock value after sales")
    st.divider()

    st.subheader("Inventory Table")
    category_filter = st.multiselect("Filter by Category", CATEGORIES, default=CATEGORIES)
    status_filter = st.multiselect("Filter by Status", ["Low", "Medium", "Good"], default=["Low", "Medium", "Good"])
    table_df = inventory[inventory["category"].isin(category_filter) & inventory["status"].isin(status_filter)].copy()
    display = inventory_display_df(table_df)

    def style_status(row):
        if row["Status"] == "Good":
            return ["background-color: rgba(47, 209, 124, 0.12)"] * len(row)
        if row["Status"] == "Medium":
            return ["background-color: rgba(247, 201, 72, 0.14)"] * len(row)
        return ["background-color: rgba(255, 107, 107, 0.16)"] * len(row)

    st.dataframe(display.style.apply(style_status, axis=1), use_container_width=True, hide_index=True)
    st.subheader("Inline Editing - Auto Pricing Integrated")
    st.caption(
        "Edit stock and product details here. If Unit Cost, Margin, Risk Buffer, or Expected Monthly Units changes, "
        "the Selling Price is recalculated on save using the full Pricing Engine, including setup-cost recovery. "
        "Manual price edits are preserved when pricing drivers are unchanged."
    )
    editor_cols = ["id", "name", "category", "unit", "selling_mode", "pack_size", "quantity_on_hand", "opening_quantity", "unit_price", "unit_cost", "desired_margin", "risk_buffer", "expected_monthly_units", "special_deal", "daily_sales_estimate"]
    edited_df = st.data_editor(
        inventory[editor_cols].copy(),
        use_container_width=True,
        hide_index=True,
        disabled=["id"],
        column_config={
            "category": st.column_config.SelectboxColumn("Category", options=CATEGORIES, required=True),
            "unit": st.column_config.SelectboxColumn("Unit", options=UNITS, required=True),
            "selling_mode": st.column_config.SelectboxColumn("Selling Mode", options=SELLING_MODES, required=True),
            "quantity_on_hand": st.column_config.NumberColumn("Qty on Hand", min_value=0.0, step=0.5),
            "opening_quantity": st.column_config.NumberColumn("Opening Qty", min_value=0.0, step=0.5),
            "unit_price": st.column_config.NumberColumn("Selling Price (R) - manual unless pricing drivers change", min_value=0.0, step=1.0, format="R %.2f"),
            "unit_cost": st.column_config.NumberColumn("Unit Cost (R)", min_value=0.0, step=1.0, format="R %.2f"),
            "desired_margin": st.column_config.NumberColumn("Margin", min_value=0.0, max_value=0.95, step=0.01, format="%.2f"),
            "risk_buffer": st.column_config.NumberColumn("Risk Buffer", min_value=0.0, max_value=0.50, step=0.01, format="%.2f"),
            "expected_monthly_units": st.column_config.NumberColumn("Expected Monthly Units", min_value=1.0, step=1.0),
            "daily_sales_estimate": st.column_config.NumberColumn("Daily Sales Estimate", min_value=0.0, step=0.5),
        },
    )
    if st.button("Save Inventory Changes", type="primary"):
        config = load_pricing_config()
        engine = PricingEngine(config)
        default_rounding = str(config.get("default_rounding", "Round nearest 5"))
        validation_errors = []
        price_update_log = []
        original_by_id = inventory.set_index(inventory["id"].astype(str), drop=False)

        for idx, row in edited_df.iterrows():
            product_name = str(row.get("name", "")).strip() or str(row.get("id", "Unknown product"))
            if not product_name:
                validation_errors.append("Product name cannot be blank.")
            if safe_float(row.get("quantity_on_hand")) < 0:
                validation_errors.append(f"{product_name}: quantity cannot be negative.")
            if safe_float(row.get("unit_price")) < 0:
                validation_errors.append(f"{product_name}: price cannot be negative.")

            row_id = str(row.get("id", ""))
            if row_id in original_by_id.index:
                original_row = original_by_id.loc[row_id].to_dict()
                if pricing_inputs_changed(row, original_row):
                    pricing_error = pricing_input_error(row)
                    if pricing_error:
                        validation_errors.append(f"{product_name}: {pricing_error}.")
                    else:
                        old_price = safe_float(row.get("unit_price"))
                        new_price = recalculate_product_price(row, engine, default_rounding)
                        edited_df.at[idx, "unit_price"] = new_price
                        price_update_log.append({
                            "id": row_id,
                            "name": product_name,
                            "old_price": old_price,
                            "new_price": new_price,
                            "unit_cost": safe_float(row.get("unit_cost")),
                            "desired_margin": safe_float(row.get("desired_margin")),
                            "risk_buffer": safe_float(row.get("risk_buffer")),
                            "expected_monthly_units": safe_float(row.get("expected_monthly_units")),
                            "rounding": default_rounding,
                        })

        if validation_errors:
            for err in validation_errors:
                st.error(err)
        else:
            before_snapshot = inventory[editor_cols].to_dict(orient="records")
            save_inventory(edited_df)
            if price_update_log:
                append_audit(
                    "INVENTORY_PRICES_AUTO_RECALCULATED",
                    "N/A",
                    "Inventory User",
                    "Inline inventory save recalculated selling prices from pricing drivers",
                    before=before_snapshot,
                    after=edited_df[editor_cols].to_dict(orient="records"),
                    metadata={"updated_count": len(price_update_log), "price_updates": price_update_log},
                )
                st.toast(f"Inventory saved. {len(price_update_log)} price(s) auto-recalculated.", icon="✅")
            else:
                st.toast("Inventory changes saved.", icon="✅")
            st.rerun()

    st.divider()
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
                current_qty = safe_float(updated.loc[idx, "quantity_on_hand"])
                if adjustment_type == "Subtract Stock" and adjustment_qty > current_qty:
                    st.error("Cannot subtract more than the quantity on hand.")
                else:
                    signed_qty = adjustment_qty if adjustment_type == "Add Stock" else -adjustment_qty
                    before = {"product": product_name, "quantity_on_hand": current_qty}
                    updated.loc[idx, "quantity_on_hand"] = current_qty + signed_qty
                    save_inventory(updated)
                    append_audit("STOCK_ADJUSTMENT", "N/A", "Inventory User", reason.strip(), before=before, after={"product": product_name, "quantity_on_hand": current_qty + signed_qty}, metadata={"adjustment_type": adjustment_type, "quantity": adjustment_qty})
                    st.toast(f"Stock adjusted: {product_name}", icon="✅")
                    st.rerun()


def page_pricing(inventory: pd.DataFrame) -> None:
    hero("Pricing Engine", "Central pricing configuration, live price calculation, enhanced product creation, and price updates.")
    config = load_pricing_config()
    engine = PricingEngine(config)

    tabs = st.tabs(["Pricing Config", "Live Calculator", "Add Product", "Edit Product Pricing"])
    with tabs[0]:
        st.subheader("Global Pricing Parameters")
        with st.form("pricing_config_form"):
            c1, c2, c3 = st.columns(3)
            with c1:
                total_upfront = st.number_input("Total Upfront Investment (R)", min_value=0.0, value=safe_float(config["total_upfront_investment"]), step=1000.0)
                payback_months = st.number_input("Payback Months", min_value=1.0, value=safe_float(config["payback_months"]), step=1.0)
            with c2:
                overhead_rate = st.number_input("Overhead Recovery Rate", min_value=0.0, max_value=1.0, value=safe_float(config["overhead_recovery_rate"]), step=0.01, format="%.2f")
                default_units = st.number_input("Default Expected Monthly Units", min_value=1.0, value=safe_float(config["default_expected_monthly_units"]), step=10.0)
            with c3:
                default_margin = st.number_input("Default Margin", min_value=0.0, max_value=0.95, value=safe_float(config["default_margin"]), step=0.01, format="%.2f")
                default_risk = st.number_input("Default Risk Buffer", min_value=0.0, max_value=0.50, value=safe_float(config["default_risk_buffer"]), step=0.01, format="%.2f")
                default_rounding = st.selectbox("Default Rounding", ROUNDING_OPTIONS, index=ROUNDING_OPTIONS.index(config.get("default_rounding", "Round nearest 5")) if config.get("default_rounding") in ROUNDING_OPTIONS else 0)
            if st.form_submit_button("Save Pricing Configuration", type="primary"):
                save_pricing_config({
                    "total_upfront_investment": total_upfront,
                    "payback_months": payback_months,
                    "overhead_recovery_rate": overhead_rate,
                    "default_risk_buffer": default_risk,
                    "default_margin": default_margin,
                    "default_expected_monthly_units": default_units,
                    "default_rounding": default_rounding,
                })
                st.toast("Pricing configuration saved.", icon="✅")
                st.rerun()
        calc = engine.calculate(unit_cost=0, expected_monthly_units=engine.default_expected_monthly_units)
        st.info(f"Current fixed cost buffer per unit using default volume: {money(calc['fixed_cost_buffer'])}")

    with tabs[1]:
        st.subheader("Live Suggested Price Calculator")
        c1, c2, c3, c4 = st.columns(4)
        with c1: unit_cost = st.number_input("Unit Cost (R)", min_value=0.0, value=40.0, step=1.0, key="calc_cost")
        with c2: margin = st.number_input("Desired Margin", min_value=0.0, max_value=0.95, value=safe_float(config["default_margin"]), step=0.01, format="%.2f", key="calc_margin")
        with c3: risk = st.number_input("Risk Buffer", min_value=0.0, max_value=0.50, value=safe_float(config["default_risk_buffer"]), step=0.01, format="%.2f", key="calc_risk")
        with c4: expected_units = st.number_input("Expected Monthly Units", min_value=1.0, value=safe_float(config["default_expected_monthly_units"]), step=1.0, key="calc_units")
        rounding = st.selectbox("Rounding Preference", ROUNDING_OPTIONS, key="calc_rounding")
        result = engine.calculate(unit_cost, margin, risk, expected_units, rounding)
        m1, m2, m3, m4 = st.columns(4)
        with m1: metric_card("Fixed Cost Buffer", money(result["fixed_cost_buffer"]), "Recovered per unit")
        with m2: metric_card("Loaded Unit Cost", money(result["loaded_unit_cost"]), "Cost + buffer")
        with m3: metric_card("Suggested Price", money(result["suggested_selling_price"]), "Before rounding")
        with m4: metric_card("Final Rounded Price", money(result["rounded_selling_price"]), rounding)

    with tabs[2]:
        st.subheader("Add New Product with Auto-Pricing")
        with st.form("enhanced_add_product_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                name = st.text_input("Product Name")
                category = st.selectbox("Category", CATEGORIES)
                unit = st.selectbox("Unit", UNITS)
                selling_mode = st.selectbox("Selling Mode", SELLING_MODES)
                pack_size = st.number_input("Pack Size / Weight", min_value=1.0, value=1.0, step=1.0)
                opening_qty = st.number_input("Opening Quantity", min_value=0.0, value=0.0, step=1.0)
            with c2:
                unit_cost = st.number_input("Unit Cost (R)", min_value=0.0, value=40.0, step=1.0)
                margin = st.number_input("Desired Margin", min_value=0.0, max_value=0.95, value=safe_float(config["default_margin"]), step=0.01, format="%.2f")
                risk = st.number_input("Risk Buffer", min_value=0.0, max_value=0.50, value=safe_float(config["default_risk_buffer"]), step=0.01, format="%.2f")
                expected_units = st.number_input("Expected Monthly Units", min_value=1.0, value=safe_float(config["default_expected_monthly_units"]), step=1.0)
                rounding = st.selectbox("Rounding", ROUNDING_OPTIONS, index=ROUNDING_OPTIONS.index(config.get("default_rounding", "Round nearest 5")) if config.get("default_rounding") in ROUNDING_OPTIONS else 0)
                override_price = st.number_input("Override Final Price (optional, 0 = use calculated)", min_value=0.0, value=0.0, step=1.0)
                special_deal = st.text_input("Special Deal (optional)", placeholder="Example: 3 for R100")
            result = engine.calculate(unit_cost, margin, risk, expected_units, rounding)
            product_pricing_row = {
                "unit_cost": unit_cost,
                "desired_margin": margin,
                "risk_buffer": risk,
                "expected_monthly_units": expected_units,
            }
            final_price = override_price if override_price > 0 else recalculate_product_price(product_pricing_row, engine, rounding)
            st.markdown(f"**Suggested:** {money(result['suggested_selling_price'])} | **Final:** {money(final_price)} | **Buffer:** {money(result['fixed_cost_buffer'])}")
            if st.form_submit_button("Add Product", type="primary"):
                if not name.strip():
                    st.error("Product name is required.")
                elif name.strip().lower() in inventory["name"].str.lower().tolist():
                    st.error("A product with this name already exists.")
                else:
                    prefix = re.sub(r"[^A-Z]", "", category.upper())[:3] or "PRD"
                    new_row = {
                        "id": make_id(prefix), "name": name.strip(), "category": category, "unit": unit, "selling_mode": selling_mode, "pack_size": pack_size,
                        "quantity_on_hand": opening_qty, "opening_quantity": opening_qty, "unit_price": final_price, "unit_cost": unit_cost,
                        "desired_margin": margin, "risk_buffer": risk, "expected_monthly_units": expected_units, "special_deal": special_deal.strip(),
                        "daily_sales_estimate": max(expected_units / 30, 1.0),
                    }
                    updated = pd.concat([inventory, pd.DataFrame([new_row])], ignore_index=True)
                    save_inventory(updated)
                    append_audit("PRODUCT_ADDED", "N/A", "Pricing User", "Product added through Pricing Engine", before=None, after=new_row)
                    st.toast("Product added successfully.", icon="✅")
                    st.rerun()

    with tabs[3]:
        st.subheader("Edit Existing Product Pricing")
        if inventory.empty:
            st.info("No products available.")
        else:
            inventory_for_select = inventory.copy()
            inventory_for_select["id"] = inventory_for_select["id"].astype(str)
            product_ids = inventory_for_select["id"].tolist()
            product_lookup = inventory_for_select.set_index("id").to_dict(orient="index")

            selected_product_id = st.selectbox(
                "Select Product",
                product_ids,
                format_func=lambda pid: str(product_lookup.get(str(pid), {}).get("name", str(pid))),
                key="edit_pricing_selected_product_id",
            )
            row = inventory_for_select[inventory_for_select["id"] == str(selected_product_id)].iloc[0]

            current_name = str(row.get("name", "")).strip()
            current_price = safe_float(row.get("unit_price"))
            current_margin = safe_float(row.get("desired_margin"), safe_float(config.get("default_margin"), 0.40))
            current_risk = safe_float(row.get("risk_buffer"), safe_float(config.get("default_risk_buffer"), 0.05))
            stored_unit_cost = safe_float(row.get("unit_cost"))
            stored_expected_units = max(safe_float(row.get("expected_monthly_units"), engine.default_expected_monthly_units), 1.0)
            default_rounding_value = str(config.get("default_rounding", "Round nearest 5"))
            default_rounding_index = ROUNDING_OPTIONS.index(default_rounding_value) if default_rounding_value in ROUNDING_OPTIONS else 0

            # Many of the neutral placeholder rows start with unit_cost = 0 but already have a POS price.
            # For repricing, infer a starting unit cost from the current POS price and current margin/risk.
            # Using the global default volume keeps this aligned to the Live Calculator assumptions.
            should_infer_cost = stored_unit_cost <= 0 and current_price > 0
            default_expected_units_for_edit = engine.default_expected_monthly_units if should_infer_cost else stored_expected_units
            denominator = 1 - current_margin - current_risk
            inferred_unit_cost = 0.0
            if should_infer_cost and denominator > 0:
                inferred_unit_cost = max((current_price * denominator) - engine.fixed_cost_buffer(default_expected_units_for_edit), 0.0)
            default_unit_cost_for_edit = stored_unit_cost if stored_unit_cost > 0 else round(inferred_unit_cost, 2)

            st.markdown("#### Current POS Pricing")
            p1, p2, p3, p4 = st.columns(4)
            with p1: metric_card("Current Product", current_name or str(selected_product_id), str(selected_product_id))
            with p2: metric_card("Current POS Price", money(current_price), "Price currently visible in POS")
            with p3: metric_card("Current Margin", f"{current_margin * 100:.0f}%", "Stored pricing driver")
            with p4: metric_card("Current Risk Buffer", f"{current_risk * 100:.0f}%", "Stored pricing driver")

            if should_infer_cost and default_unit_cost_for_edit > 0:
                st.info(
                    f"Unit cost was blank/zero for this product, so the screen inferred {money(default_unit_cost_for_edit)} "
                    f"from the current POS price of {money(current_price)} using the current margin, risk buffer, and global expected monthly units. "
                    "You can overwrite it before saving."
                )

            st.markdown("#### Rename Product")
            new_name = st.text_input(
                "Product Name",
                value=current_name,
                key=f"edit_product_name_{selected_product_id}",
                help="This replaces the old Product 001-style name in inventory and in the POS catalog.",
            )

            st.markdown("#### Product Pricing Calculator")
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                unit_cost = st.number_input(
                    "Unit Cost (R)",
                    min_value=0.0,
                    value=float(default_unit_cost_for_edit),
                    step=1.0,
                    key=f"edit_unit_cost_{selected_product_id}",
                )
            with c2:
                margin = st.number_input(
                    "Desired Margin",
                    min_value=0.0,
                    max_value=0.95,
                    value=float(current_margin),
                    step=0.01,
                    format="%.2f",
                    key=f"edit_margin_{selected_product_id}",
                )
            with c3:
                risk = st.number_input(
                    "Risk Buffer",
                    min_value=0.0,
                    max_value=0.50,
                    value=float(current_risk),
                    step=0.01,
                    format="%.2f",
                    key=f"edit_risk_{selected_product_id}",
                )
            with c4:
                expected_units = st.number_input(
                    "Expected Monthly Units",
                    min_value=1.0,
                    value=float(default_expected_units_for_edit),
                    step=1.0,
                    key=f"edit_expected_units_{selected_product_id}",
                )

            rounding = st.selectbox(
                "Rounding Preference",
                ROUNDING_OPTIONS,
                index=default_rounding_index,
                key=f"edit_rounding_{selected_product_id}",
            )
            c5, c6 = st.columns(2)
            with c5:
                override = st.number_input(
                    "Manual Override Price (0 = use calculated)",
                    min_value=0.0,
                    value=0.0,
                    step=1.0,
                    key=f"edit_override_{selected_product_id}",
                )
            with c6:
                special_deal = st.text_input(
                    "Special Deal",
                    value=str(row.get("special_deal", "") or ""),
                    key=f"edit_special_deal_{selected_product_id}",
                    placeholder="Example: 3 for R100",
                )

            preview_row = {
                "unit_cost": unit_cost,
                "desired_margin": margin,
                "risk_buffer": risk,
                "expected_monthly_units": expected_units,
            }
            result = engine.calculate(unit_cost, margin, risk, expected_units, rounding)
            calculated_price = safe_float(result["suggested_selling_price"])
            rounded_price = recalculate_product_price(preview_row, engine, rounding)
            new_price = override if override > 0 else rounded_price

            pricing_error = pricing_input_error(preview_row)
            if pricing_error:
                st.error(f"Pricing check: {pricing_error}.")

            st.markdown("#### New Price Preview")
            m1, m2, m3, m4 = st.columns(4)
            with m1: metric_card("Fixed Cost Buffer", money(result["fixed_cost_buffer"]), "Recovered per unit")
            with m2: metric_card("Loaded Unit Cost", money(result["loaded_unit_cost"]), "Cost + buffer")
            with m3: metric_card("New Calculated Price", money(calculated_price), "Before rounding")
            with m4: metric_card("New Final Price", money(new_price), "Manual override used" if override > 0 else rounding)

            st.markdown(f"### New calculated price: {money(calculated_price)} | New final price: {money(new_price)}")
            st.caption("Once updated, the POS catalog will use the new product name and new final price immediately.")

            update_clicked = st.button("Update Product Pricing", type="primary", key=f"update_product_pricing_{selected_product_id}")
            if update_clicked:
                clean_name = new_name.strip()
                other_names = inventory_for_select.loc[inventory_for_select["id"] != str(selected_product_id), "name"].astype(str).str.strip().str.lower().tolist()

                if not clean_name:
                    st.error("Product name is required.")
                elif clean_name.lower() in other_names:
                    st.error("Another product already has this name. Please use a unique product name.")
                elif pricing_error:
                    st.error(f"Cannot update product pricing because {pricing_error}.")
                elif new_price <= 0:
                    st.error("New final price must be greater than zero.")
                else:
                    updated = inventory.copy()
                    idx_matches = updated.index[updated["id"].astype(str) == str(selected_product_id)]
                    if len(idx_matches) == 0:
                        st.error("Selected product was not found. Please refresh and try again.")
                    else:
                        idx = idx_matches[0]
                        before = updated.loc[idx].to_dict()
                        updated.loc[idx, "name"] = clean_name
                        updated.loc[idx, "unit_cost"] = unit_cost
                        updated.loc[idx, "desired_margin"] = margin
                        updated.loc[idx, "risk_buffer"] = risk
                        updated.loc[idx, "expected_monthly_units"] = expected_units
                        updated.loc[idx, "unit_price"] = new_price
                        updated.loc[idx, "special_deal"] = special_deal.strip()
                        save_inventory(updated)
                        append_audit(
                            "PRODUCT_RENAMED_AND_PRICE_UPDATED",
                            "N/A",
                            "Pricing User",
                            "Product name and pricing updated through Pricing Engine",
                            before=before,
                            after=updated.loc[idx].to_dict(),
                            metadata={
                                "old_name": before.get("name"),
                                "new_name": clean_name,
                                "old_price": safe_float(before.get("unit_price")),
                                "new_price": new_price,
                                "calculated_price_before_rounding": calculated_price,
                                "rounding": rounding,
                                "manual_override_used": override > 0,
                            },
                        )
                        st.toast("Product name and pricing updated. POS catalog refreshed.", icon="✅")
                        st.rerun()

def page_sales_reports(sales: List[Dict[str, Any]]) -> None:
    hero("Sales History & Reports", "Review sales, edit/void within monthly window, export backups, and inspect audit trail.")
    tabs = st.tabs(["Sales History", "Edit / Void Sales", "Voids & Edits Log", "Audit Trail", "Backups"])

    with tabs[0]:
        sales_df = sales_to_dataframe(sales, include_voided=True)
        if sales_df.empty:
            st.info("No sales logged yet.")
        else:
            sales_df["Timestamp Parsed"] = pd.to_datetime(sales_df["Timestamp"], errors="coerce")
            sales_df["Date"] = sales_df["Timestamp Parsed"].dt.date
            c1, c2, c3 = st.columns(3)
            active_total = sales_df.loc[sales_df["Status"] != "voided", "Total (R)"].sum()
            with c1: metric_card("Active Sales", money(active_total), "Excludes voided sales")
            with c2: metric_card("Transactions", f"{len(sales_df):,}", "Includes voided records")
            with c3: metric_card("Voided", f"{(sales_df['Status'] == 'voided').sum():,}", "Voided transactions retained")
            start_date = st.date_input("Start Date", value=min(sales_df["Date"]), key="sales_start")
            end_date = st.date_input("End Date", value=max(sales_df["Date"]), key="sales_end")
            filtered = sales_df[(sales_df["Date"] >= start_date) & (sales_df["Date"] <= end_date)].copy()
            st.dataframe(filtered[["Sale ID", "Timestamp", "Status", "Payment Method", "Items", "Total (R)", "Modified Count"]], use_container_width=True, hide_index=True)
            st.download_button("Export Sales History to CSV", data=filtered.to_csv(index=False).encode("utf-8"), file_name=f"saint_herb_sales_history_{today_string()}.csv", mime="text/csv", use_container_width=True)

    with tabs[1]:
        active_sales = [s for s in sales if normalise_sale(s).get("status") != "voided"]
        if not active_sales:
            st.info("No active sales available to edit or void.")
        else:
            labels = [f"{s['sale_id']} | {s.get('timestamp')} | {money(safe_float(s.get('total')))}" for s in active_sales]
            selected_label = st.selectbox("Select Sale", labels)
            selected_sale = active_sales[labels.index(selected_label)]
            allowed, msg = can_modify_sale(selected_sale)
            st.info(msg if allowed else f"Blocked: {msg}")
            st.dataframe(pd.DataFrame(selected_sale.get("items", [])), use_container_width=True, hide_index=True)
            bartender = st.text_input("Bartender Full Name")
            reason = st.text_area("Mandatory Reason")
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("Void Sale")
                st.caption("Voiding restores the sold quantities back into inventory and keeps the record as voided.")
                if st.button("Void Selected Sale", type="primary", disabled=not allowed, use_container_width=True):
                    ok, out = void_sale(selected_sale["sale_id"], bartender, reason)
                    if ok:
                        st.success(out)
                        st.rerun()
                    else:
                        st.error(out)
            with c2:
                st.subheader("Edit Sale Items")
                st.caption("Change quantities only. Use 0 to remove an item from the sale.")
                inventory = load_inventory()
                current_items = pd.DataFrame(selected_sale.get("items", []))
                if current_items.empty:
                    st.info("This sale has no items.")
                else:
                    edit_df = current_items[["product_id", "name", "quantity", "unit_price", "special_deal"]].copy() if "special_deal" in current_items.columns else current_items[["product_id", "name", "quantity", "unit_price"]].copy()
                    if "special_deal" not in edit_df.columns:
                        edit_df["special_deal"] = ""
                    edited = st.data_editor(edit_df, use_container_width=True, hide_index=True, disabled=["product_id", "name", "unit_price", "special_deal"], column_config={"quantity": st.column_config.NumberColumn("Quantity", min_value=0.0, step=0.5)})
                    new_payment = st.selectbox("Payment Method", PAYMENT_METHODS, index=PAYMENT_METHODS.index(selected_sale.get("payment_method", "Other")) if selected_sale.get("payment_method") in PAYMENT_METHODS else 0)
                    if st.button("Save Edited Sale", type="primary", disabled=not allowed, use_container_width=True):
                        edited_items = []
                        for _, item in edited.iterrows():
                            qty = safe_float(item["quantity"])
                            if qty <= 0:
                                continue
                            unit_price = safe_float(item["unit_price"])
                            deal = str(item.get("special_deal", "") or "")
                            edited_items.append({
                                "product_id": str(item["product_id"]),
                                "name": str(item["name"]),
                                "quantity": qty,
                                "unit_price": unit_price,
                                "line_total": line_total_with_deal(qty, unit_price, deal),
                                "special_deal": deal,
                            })
                        if not edited_items:
                            st.error("Edited sale must contain at least one item. Use void if the whole sale must be cancelled.")
                        else:
                            ok, out = edit_sale(selected_sale["sale_id"], edited_items, new_payment, bartender, reason)
                            if ok:
                                st.success(out)
                                st.rerun()
                            else:
                                st.error(out)

    with tabs[2]:
        rows = []
        for sale in sales:
            for event in normalise_sale(sale).get("modification_history", []):
                rows.append({
                    "Sale ID": sale.get("sale_id"),
                    "Sale Status": sale.get("status"),
                    "Action": event.get("action"),
                    "Timestamp": event.get("timestamp"),
                    "Bartender": event.get("bartender"),
                    "Reason": event.get("reason"),
                })
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("No voids or edits have been logged yet.")

    with tabs[3]:
        audit = load_audit()
        if audit:
            audit_df = pd.DataFrame(audit)
            display_cols = [c for c in ["audit_id", "timestamp", "action", "sale_id", "bartender", "reason"] if c in audit_df.columns]
            st.dataframe(audit_df[display_cols], use_container_width=True, hide_index=True)
            st.download_button("Export Audit Trail CSV", data=audit_df.to_csv(index=False).encode("utf-8"), file_name=f"saint_herb_audit_{today_string()}.csv", mime="text/csv", use_container_width=True)
        else:
            st.info("No audit records yet.")

    with tabs[4]:
        inventory = load_inventory()
        today_backup = build_backup_zip(inventory, sales, only_today=True)
        full_backup = build_backup_zip(inventory, sales, only_today=False)
        c1, c2 = st.columns(2)
        with c1:
            st.download_button("Save Today's Data Backup", data=today_backup, file_name=f"saint_herb_today_backup_{today_string()}.zip", mime="application/zip", use_container_width=True)
        with c2:
            st.download_button("Save Full Backup Pack", data=full_backup, file_name=f"saint_herb_full_backup_{today_string()}.zip", mime="application/zip", use_container_width=True)


def page_settings() -> None:
    hero("Settings", "Manage lightweight storage files, daily backups, and notes for the upcoming database upgrade.")
    inventory = load_inventory()
    sales = load_sales()
    st.subheader("Data Files")
    st.write(f"Inventory file: `{INVENTORY_FILE.resolve()}`")
    st.write(f"Sales file: `{SALES_FILE.resolve()}`")
    st.write(f"Audit file: `{AUDIT_FILE.resolve()}`")
    st.write(f"Pricing config file: `{PRICING_CONFIG_FILE.resolve()}`")
    st.info("There is no reset-demo button in this live-lite build.")
    st.subheader("Daily Backup")
    c1, c2 = st.columns(2)
    with c1:
        st.download_button("Save Today's Data Backup", data=build_backup_zip(inventory, sales, only_today=True), file_name=f"saint_herb_today_backup_{today_string()}.zip", mime="application/zip", use_container_width=True)
    with c2:
        st.download_button("Save Full Backup Pack", data=build_backup_zip(inventory, sales, only_today=False), file_name=f"saint_herb_full_backup_{today_string()}.zip", mime="application/zip", use_container_width=True)
    st.divider()
    st.subheader("Production Notes")
    st.markdown("""
    Next upgrade recommendation:
    - Move from local JSON to Supabase/PostgreSQL.
    - Add login and cashier roles.
    - Store every receipt, edit, void, stock movement and price change in relational tables.
    - Add end-of-day closeout by cashier and payment method.
    """)


# ============================================================
# Main App
# ============================================================

def init_state() -> None:
    if "cart" not in st.session_state:
        st.session_state.cart = {}
    if "last_receipt" not in st.session_state:
        st.session_state.last_receipt = None


def main() -> None:
    inject_css()
    init_state()
    inventory = load_inventory()
    sales = load_sales()
    with st.sidebar:
        st.markdown("## 🌿 Saint Herb")
        st.caption("Premium Inventory + POS")
        st.divider()
        page = st.radio("Navigation", ["Dashboard", "Point of Sale", "Inventory", "Pricing", "Sales Reports", "Settings"], label_visibility="collapsed")
        st.divider()
        st.caption("Current Session")
        st.write(f"Cart items: **{len(st.session_state.cart)}**")
        st.write(f"Cart total: **{money(cart_total())}**")
        st.divider()
        st.caption("Live-lite build. Save backups daily until database upgrade is complete.")
    if page == "Dashboard":
        page_dashboard(inventory, sales)
    elif page == "Point of Sale":
        page_pos(inventory)
    elif page == "Inventory":
        page_inventory(inventory)
    elif page == "Pricing":
        page_pricing(inventory)
    elif page == "Sales Reports":
        page_sales_reports(sales)
    elif page == "Settings":
        page_settings()


if __name__ == "__main__":
    main()