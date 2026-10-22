"""Golden set: business questions with verified reference SQL.

The reference SQL is the oracle. Each query was written by hand and its output
inspected before use, because an unverified oracle produces a meaningless
accuracy score.

Categories exist so accuracy can be reported by question type rather than as a
single number that hides where the system actually struggles.
"""

from __future__ import annotations

GOLDEN = [
    # ---------- aggregation ----------
    dict(id="cat_sales", category="aggregation",
         question="What is total sales by category?",
         ref="SELECT p.category, ROUND(SUM(f.sales), 2) FROM fact_sales f "
             "JOIN dim_product p USING (product_id) GROUP BY 1 ORDER BY 1"),
    dict(id="region_profit", category="aggregation",
         question="What is total profit by region?",
         ref="SELECT l.region, ROUND(SUM(f.profit), 2) FROM fact_sales f "
             "JOIN dim_location l USING (postal_code) GROUP BY 1 ORDER BY 1"),
    dict(id="total_units", category="aggregation",
         question="What is the total number of units sold?",
         ref="SELECT SUM(quantity) FROM fact_sales"),
    dict(id="avg_discount", category="aggregation",
         question="What is the average discount across all order lines? Report it as a decimal, "
                  "for example 0.15",
         ref="SELECT ROUND(AVG(discount), 4) FROM fact_sales"),
    dict(id="order_count", category="aggregation",
         question="How many distinct orders are in the dataset?",
         ref="SELECT COUNT(DISTINCT order_id) FROM fact_sales"),

    # ---------- filtering ----------
    dict(id="same_day_ship", category="filtering",
         question="How many distinct orders were shipped on the same day they were ordered?",
         ref="SELECT COUNT(DISTINCT order_id) FROM fact_sales WHERE order_date = ship_date"),
    dict(id="consumer_sales", category="filtering",
         question="What is the total sales for the Consumer segment?",
         ref="SELECT ROUND(SUM(f.sales), 2) FROM fact_sales f "
             "JOIN dim_customer c USING (customer_id) WHERE c.segment = 'Consumer'"),
    dict(id="west_orders", category="filtering",
         question="How many distinct orders were placed in the West region?",
         ref="SELECT COUNT(DISTINCT f.order_id) FROM fact_sales f "
             "JOIN dim_location l USING (postal_code) WHERE l.region = 'West'"),
    dict(id="tech_profit", category="filtering",
         question="What is the total profit for Technology products?",
         ref="SELECT ROUND(SUM(f.profit), 2) FROM fact_sales f "
             "JOIN dim_product p USING (product_id) WHERE p.category = 'Technology'"),
    dict(id="standard_class_orders", category="filtering",
         question="How many distinct orders used Standard Class shipping?",
         ref="SELECT COUNT(DISTINCT order_id) FROM fact_sales WHERE ship_mode = 'Standard Class'"),

    # ---------- ranking ----------
    dict(id="top5_subcat_sales", category="ranking",
         question="What are the top 5 sub categories by total sales?",
         ref="SELECT p.sub_category, ROUND(SUM(f.sales), 2) FROM fact_sales f "
             "JOIN dim_product p USING (product_id) GROUP BY 1 ORDER BY 2 DESC LIMIT 5"),
    dict(id="top3_states_profit", category="ranking",
         question="Which 3 states have the highest total profit?",
         ref="SELECT l.state, ROUND(SUM(f.profit), 2) FROM fact_sales f "
             "JOIN dim_location l USING (postal_code) GROUP BY 1 ORDER BY 2 DESC LIMIT 3"),
    dict(id="bottom5_products_profit", category="ranking",
         question="What are the 5 products with the lowest total profit?",
         ref="SELECT p.product_name, ROUND(SUM(f.profit), 2) FROM fact_sales f "
             "JOIN dim_product p USING (product_id) GROUP BY 1 ORDER BY 2 ASC LIMIT 5"),
    dict(id="city_most_orders", category="ranking",
         question="Which city has the most orders?",
         ref="SELECT l.city, COUNT(DISTINCT f.order_id) FROM fact_sales f "
             "JOIN dim_location l USING (postal_code) GROUP BY 1 ORDER BY 2 DESC LIMIT 1"),
    dict(id="top10_customers_sales", category="ranking",
         question="Who are the top 10 customers by total sales?",
         ref="SELECT c.customer_name, ROUND(SUM(f.sales), 2) FROM fact_sales f "
             "JOIN dim_customer c USING (customer_id) GROUP BY 1 ORDER BY 2 DESC LIMIT 10"),

    # ---------- joins ----------
    dict(id="segment_sales", category="joins",
         question="What is total sales by customer segment?",
         ref="SELECT c.segment, ROUND(SUM(f.sales), 2) FROM fact_sales f "
             "JOIN dim_customer c USING (customer_id) GROUP BY 1 ORDER BY 1"),
    dict(id="shipmode_sales", category="joins",
         question="What is total sales by ship mode?",
         ref="SELECT ship_mode, ROUND(SUM(sales), 2) FROM fact_sales GROUP BY 1 ORDER BY 1"),
    dict(id="margin_by_category", category="joins",
         question="What is the profit margin percentage by category?",
         ref="SELECT p.category, ROUND(100 * SUM(f.profit) / SUM(f.sales), 2) FROM fact_sales f "
             "JOIN dim_product p USING (product_id) GROUP BY 1 ORDER BY 1"),
    dict(id="qty_by_region", category="joins",
         question="What is the total quantity sold by region?",
         ref="SELECT l.region, SUM(f.quantity) FROM fact_sales f "
             "JOIN dim_location l USING (postal_code) GROUP BY 1 ORDER BY 1"),
    dict(id="subcat_highest_discount", category="joins",
         question="Which sub category has the highest average discount? Report the average as a decimal.",
         ref="SELECT p.sub_category, ROUND(AVG(f.discount), 4) FROM fact_sales f "
             "JOIN dim_product p USING (product_id) GROUP BY 1 ORDER BY 2 DESC LIMIT 1"),

    # ---------- time ----------
    dict(id="orders_2017", category="time",
         question="How many distinct orders were placed in 2017?",
         ref="SELECT COUNT(DISTINCT order_id) FROM fact_sales WHERE YEAR(order_date) = 2017"),
    dict(id="sales_by_year", category="time",
         question="What is total sales by year?",
         ref="SELECT YEAR(order_date), ROUND(SUM(sales), 2) FROM fact_sales GROUP BY 1 ORDER BY 1"),
    dict(id="best_month", category="time",
         question="Which calendar month had the highest total sales?",
         ref="SELECT STRFTIME(order_date, '%Y-%m'), ROUND(SUM(sales), 2) FROM fact_sales "
             "GROUP BY 1 ORDER BY 2 DESC LIMIT 1"),
    dict(id="q1_2016_profit", category="time",
         question="What was the total profit in the first quarter of 2016?",
         ref="SELECT ROUND(SUM(profit), 2) FROM fact_sales "
             "WHERE YEAR(order_date) = 2016 AND MONTH(order_date) IN (1, 2, 3)"),
    dict(id="orders_dec_2017", category="time",
         question="How many distinct orders were placed in December 2017?",
         ref="SELECT COUNT(DISTINCT order_id) FROM fact_sales "
             "WHERE YEAR(order_date) = 2017 AND MONTH(order_date) = 12"),

    # ---------- ratios ----------
    dict(id="tech_share", category="ratios",
         question="What percentage of total sales comes from Technology products?",
         ref="SELECT ROUND(100 * SUM(CASE WHEN p.category = 'Technology' THEN f.sales END) "
             "/ SUM(f.sales), 2) FROM fact_sales f JOIN dim_product p USING (product_id)"),
    dict(id="overall_margin", category="ratios",
         question="What is the overall profit margin as a percentage?",
         ref="SELECT ROUND(100 * SUM(profit) / SUM(sales), 2) FROM fact_sales"),
    dict(id="avg_profit_per_order", category="ratios",
         question="What is the average profit per order?",
         ref="SELECT ROUND(SUM(profit) / COUNT(DISTINCT order_id), 2) FROM fact_sales"),
    dict(id="avg_line_value", category="ratios",
         question="What is the average sales value of an order line?",
         ref="SELECT ROUND(AVG(sales), 2) FROM fact_sales"),
    dict(id="loss_line_pct", category="ratios",
         question="What percentage of order lines were sold at a loss?",
         ref="SELECT ROUND(100 * COUNT(CASE WHEN profit < 0 THEN 1 END) / COUNT(*), 2) "
             "FROM fact_sales"),

    # ---------- comparison ----------
    dict(id="best_region_avg_profit", category="comparison",
         question="Which region has the highest average profit per order?",
         ref="SELECT l.region, ROUND(SUM(f.profit) / COUNT(DISTINCT f.order_id), 2) "
             "FROM fact_sales f JOIN dim_location l USING (postal_code) "
             "GROUP BY 1 ORDER BY 2 DESC LIMIT 1"),
    dict(id="lowest_discount_segment", category="comparison",
         question="Which customer segment has the lowest average discount? "
                  "Report the average as a decimal.",
         ref="SELECT c.segment, ROUND(AVG(f.discount), 4) FROM fact_sales f "
             "JOIN dim_customer c USING (customer_id) GROUP BY 1 ORDER BY 2 ASC LIMIT 1"),
    dict(id="lowest_margin_category", category="comparison",
         question="Which product category has the lowest profit margin percentage?",
         ref="SELECT p.category, ROUND(100 * SUM(f.profit) / SUM(f.sales), 2) "
             "FROM fact_sales f JOIN dim_product p USING (product_id) "
             "GROUP BY 1 ORDER BY 2 ASC LIMIT 1"),
    dict(id="slowest_ship_mode", category="comparison",
         question="Which ship mode has the longest average delivery time in days?",
         ref="SELECT ship_mode, ROUND(AVG(DATEDIFF('day', order_date, ship_date)), 2) "
             "FROM fact_sales GROUP BY 1 ORDER BY 2 DESC LIMIT 1"),
    dict(id="state_most_loss_lines", category="comparison",
         question="Which state has the most loss making order lines?",
         ref="SELECT l.state, COUNT(*) FROM fact_sales f JOIN dim_location l USING (postal_code) "
             "WHERE f.profit < 0 GROUP BY 1 ORDER BY 2 DESC LIMIT 1"),

    # ---------- traps: easy to get subtly wrong ----------
    dict(id="total_sales_all", category="traps",
         question="What is the total sales across all order lines?",
         ref="SELECT ROUND(SUM(sales), 2) FROM fact_sales"),
    dict(id="distinct_products", category="traps",
         question="How many distinct products are in the catalogue?",
         ref="SELECT COUNT(DISTINCT product_id) FROM dim_product"),
    dict(id="worst_subcat_net_profit", category="traps",
         question="Which sub category has the lowest total profit overall?",
         ref="SELECT p.sub_category, ROUND(SUM(f.profit), 2) FROM fact_sales f "
             "JOIN dim_product p USING (product_id) GROUP BY 1 ORDER BY 2 ASC LIMIT 1"),
    dict(id="worst_subcat_losses_only", category="traps",
         question="Which sub category has the largest total value of losses, counting only "
                  "the order lines that lost money?",
         ref="SELECT p.sub_category, ROUND(SUM(f.profit), 2) FROM fact_sales f "
             "JOIN dim_product p USING (product_id) WHERE f.profit < 0 "
             "GROUP BY 1 ORDER BY 2 ASC LIMIT 1"),
    dict(id="loss_line_count", category="traps",
         question="How many order lines were sold at a loss?",
         ref="SELECT COUNT(*) FROM fact_sales WHERE profit < 0"),
    dict(id="avg_ship_delay", category="traps",
         question="What is the average number of days between order date and ship date?",
         ref="SELECT ROUND(AVG(DATEDIFF('day', order_date, ship_date)), 2) FROM fact_sales"),
]

CATEGORIES = sorted({q["category"] for q in GOLDEN})
