"""Generate the SYNTHETIC Olist-schema fixture in tests/fixtures/synthetic_olist/.

SYNTHETIC DATA. Every row is generated here from a fixed seed. Nothing is copied or derived from the
real Olist dataset (CC BY-NC-SA); only the column names match, so the SQL pipeline can run in CI.
It deliberately includes the edge cases the pipeline handles: late and on-time deliveries, reviews
written before delivery, a duplicate review for one order, a multi-seller order, split payments,
cancelled orders and several geolocation rows per zip prefix.

Run: python tests/fixtures/make_synthetic_olist.py
"""
import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

OUT = Path(__file__).parent / "synthetic_olist"
FMT = "%Y-%m-%d %H:%M:%S"


def ts(d):
    return d.strftime(FMT) if d else ""


def write(name, header, rows):
    with open(OUT / name, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def main(n_orders=40, seed=7):
    rng = random.Random(seed)
    OUT.mkdir(parents=True, exist_ok=True)
    states = ["SP", "RJ", "MG", "BA"]
    sellers = [(f"syn_seller_{i:02d}", f"{10000 + i * 1111:05d}"[:5], f"synth_city_{i}", states[i % 4]) for i in range(4)]
    cats = [("syn_categoria_a", "synthetic_cat_a"), ("syn_categoria_b", "synthetic_cat_b"), ("syn_categoria_c", "")]
    products = [(f"syn_prod_{i:02d}", cats[i % 3][0], 20, 100, 1, 500, 10, 10, 10) for i in range(6)]
    customers, orders, items, pays, reviews = [], [], [], [], []
    base = datetime(2017, 6, 1, 9, 0, 0)
    for i in range(n_orders):
        oid, cid = f"syn_order_{i:03d}", f"syn_cust_{i:03d}"
        uid = f"syn_person_{i % 30:03d}"  # some people order twice -> repeat customers
        customers.append((cid, uid, f"{20000 + i % 5:05d}", f"synth_town_{i % 5}", states[i % 4]))
        bought = base + timedelta(days=i * 11, hours=rng.randint(0, 8))
        est = (bought + timedelta(days=20)).replace(hour=0, minute=0, second=0)
        status = "canceled" if i % 13 == 5 else "delivered"
        late = i % 4 == 0
        delivered = None if status == "canceled" else est + timedelta(days=rng.randint(2, 9)) if late \
            else bought + timedelta(days=rng.randint(5, 15), hours=3)
        orders.append((oid, cid, status, ts(bought), ts(bought + timedelta(hours=1)),
                       ts(bought + timedelta(days=2)) if delivered else "", ts(delivered), ts(est)))
        n_items = 2 if i % 7 == 0 else 1
        total = 0.0
        for k in range(1, n_items + 1):
            price = round(rng.uniform(15, 250), 2)
            seller = sellers[(i + k) % 4][0]  # n_items == 2 -> two different sellers
            items.append((oid, k, products[(i + k) % 6][0], seller, ts(bought + timedelta(days=3)), f"{price:.2f}", "12.50"))
            total += price + 12.50
        if i % 6 == 0:  # split payment
            pays += [(oid, 1, "credit_card", 3, f"{total - 10:.2f}"), (oid, 2, "voucher", 1, "10.00")]
        else:
            pays.append((oid, 1, "boleto" if i % 5 == 0 else "credit_card", 1 if i % 5 == 0 else 1 + i % 8, f"{total:.2f}"))
        if delivered:
            created = (est if late else delivered + timedelta(days=1)).replace(hour=0, minute=0, second=0)
            score = rng.choice([1, 2, 3]) if late else rng.choice([4, 5, 5])
            reviews.append((f"syn_review_{i:03d}", oid, score, "", "", ts(created), ts(created + timedelta(hours=20))))
            if i == 8:  # duplicate review for one order, answered later
                reviews.append((f"syn_review_{i:03d}b", oid, 5, "", "", ts(created + timedelta(days=3)), ts(created + timedelta(days=4))))
    geo = [(f"{20000 + z:05d}", f"{-23.5 - z * 0.1 + j * 0.01:.4f}", f"{-46.6 + z * 0.1:.4f}", f"synth_town_{z}", states[z % 4])
           for z in range(5) for j in range(2)]
    geo += [(s[1], "-22.0000", "-45.0000", s[2], s[3]) for s in sellers]
    write("olist_orders_dataset.csv", ["order_id", "customer_id", "order_status", "order_purchase_timestamp", "order_approved_at",
                                       "order_delivered_carrier_date", "order_delivered_customer_date", "order_estimated_delivery_date"], orders)
    write("olist_customers_dataset.csv", ["customer_id", "customer_unique_id", "customer_zip_code_prefix", "customer_city", "customer_state"], customers)
    write("olist_order_items_dataset.csv", ["order_id", "order_item_id", "product_id", "seller_id", "shipping_limit_date", "price", "freight_value"], items)
    write("olist_order_payments_dataset.csv", ["order_id", "payment_sequential", "payment_type", "payment_installments", "payment_value"], pays)
    write("olist_order_reviews_dataset.csv", ["review_id", "order_id", "review_score", "review_comment_title", "review_comment_message",
                                              "review_creation_date", "review_answer_timestamp"], reviews)
    write("olist_products_dataset.csv", ["product_id", "product_category_name", "product_name_lenght", "product_description_lenght",
                                         "product_photos_qty", "product_weight_g", "product_length_cm", "product_height_cm", "product_width_cm"], products)
    write("olist_sellers_dataset.csv", ["seller_id", "seller_zip_code_prefix", "seller_city", "seller_state"], sellers)
    write("olist_geolocation_dataset.csv", ["geolocation_zip_code_prefix", "geolocation_lat", "geolocation_lng", "geolocation_city", "geolocation_state"], geo)
    write("product_category_name_translation.csv", ["product_category_name", "product_category_name_english"], [c for c in cats if c[1]])
    (OUT / "README.md").write_text("# SYNTHETIC test fixture\n\nGenerated by `../make_synthetic_olist.py` from a fixed seed. "
                                   "Not real Olist data and not derived from it; only the column names match. Used so CI can run "
                                   "the pipeline's integrity and parity tests without the CC BY-NC-SA dataset.\n")


if __name__ == "__main__":
    main()
