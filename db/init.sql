CREATE TABLE IF NOT EXISTS customers (
    customer_id INTEGER PRIMARY KEY,
    signup_date DATE NOT NULL,
    country TEXT NOT NULL,
    acquisition_channel TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    order_id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
    order_timestamp TIMESTAMPTZ NOT NULL,
    product_category TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price NUMERIC(10, 2) NOT NULL CHECK (unit_price > 0),
    discount_pct NUMERIC(4, 3) NOT NULL CHECK (discount_pct >= 0 AND discount_pct < 1),
    status TEXT NOT NULL CHECK (status IN ('completed', 'cancelled'))
);

CREATE INDEX IF NOT EXISTS idx_orders_timestamp ON orders (order_timestamp);
CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders (customer_id);

CREATE TABLE IF NOT EXISTS monthly_sales (
    month DATE PRIMARY KEY,
    revenue NUMERIC(14, 2) NOT NULL,
    completed_orders INTEGER NOT NULL,
    active_customers INTEGER NOT NULL,
    average_order_value NUMERIC(14, 2) NOT NULL
);

CREATE TABLE IF NOT EXISTS customer_features (
    customer_id INTEGER PRIMARY KEY REFERENCES customers(customer_id),
    first_order_date DATE,
    last_order_date DATE,
    recency_days INTEGER,
    completed_orders INTEGER NOT NULL,
    total_revenue NUMERIC(14, 2) NOT NULL,
    average_order_value NUMERIC(14, 2) NOT NULL,
    segment TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_customer_features_segment ON customer_features (segment);
