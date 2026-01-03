from flask import Flask, jsonify, render_template, request, redirect, url_for, session
import os
import qrcode
import io
import base64


import pymysql

from datetime import datetime, timedelta

from services.database import get_connection

app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = "rahasia_besar"  # wajib buat session

UPLOAD_FOLDER = "static/images"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config['MYSQL_HOST'] = "localhost"
app.config['MYSQL_USER'] = "root"
app.config['MYSQL_PASSWORD'] = ""
app.config['MYSQL_DB'] = "db_name"




def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# ---------------- Login ----------------
@app.route("/")
def home():
    db = get_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    # Ambil semua produk
    cursor.execute("SELECT * FROM products")    
    products = cursor.fetchall()

    # Ambil user (jika login)
    user = session.get("user")
    user_id = session.get("user_id")

    # Ambil cart items jika user login
    items = []
    if user_id:
        cursor.execute("""
            SELECT 
                cart.quantity,
                products.name,
                products.price,
                products.image,
                products.id AS product_id
            FROM cart
            JOIN products ON cart.product_id = products.id
            WHERE cart.user_id = %s
        """, (user_id,))
        items = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "index.html",
        user=user,
        products=products,
        items=items  # ← KIRIM CART KE HTML
    )



@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        db = get_connection()
        cursor = db.cursor(pymysql.cursors.DictCursor)

        cursor.execute(
            "SELECT * FROM users WHERE email = %s AND password = %s",
            (email, password)
        )
        user = cursor.fetchone()
        cursor.close()
        db.close()

        if user:
            # Simpan data session
            session["user_id"] = user["id"]
            session["user"] = user["email"]
            session["role"] = user.get("role", "user")   # default 'user'

            # Arahkan berdasarkan role
            if session["role"] == "admin":
                return redirect(url_for("admin_dashboard"))
            else:
                return redirect(url_for("home"))

        else:
            return render_template(
                "login.html",
                error="Email atau password salah!"
            )

    return render_template("login.html")


def admin_required(f):
    def wrapper(*args, **kwargs):
        if session.get("role") != "admin":
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper


@app.route("/admin")
def admin_dashboard():
    return render_template("admin_dashboard.html")

@app.route("/admin/products")
@admin_required
def admin_products():
    db = get_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    cursor.execute("SELECT * FROM products")
    products = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template("admin_products.html", products=products)



@app.route("/admin/products/add", methods=["GET", "POST"])
def admin_add_product():

    # Cek admin
    if "role" not in session or session["role"] != "admin":
        return redirect("/login")

    if request.method == "POST":
        name = request.form.get("name")
        price = request.form.get("price")
        stock = request.form.get("stock")
        description = request.form.get("description")   # ← TAMBAH INI

        # Ambil file dari form
        image_file = request.files.get("image")
        image_filename = None

        # Kalau file ada dan format diijinkan
        if image_file and allowed_file(image_file.filename):
            image_filename = image_file.filename
            image_file.save(os.path.join(app.config["UPLOAD_FOLDER"], image_filename))

        # Simpan ke DB
        db = get_connection()
        cursor = db.cursor()

        cursor.execute("""
            INSERT INTO products (name, price, stock, image, description)
            VALUES (%s, %s, %s, %s, %s)
        """, (name, price, stock, image_filename, description))

        db.commit()
        cursor.close()
        db.close()

        return redirect("/admin/products")

    return render_template("admin_add_product.html")



@app.route("/admin/products/edit/<int:id>", methods=["GET", "POST"])
def admin_edit_product(id):
    # Cek role admin
    if "role" not in session or session["role"] != "admin":
        return redirect("/login")

    db = get_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    # Ambil data produk dulu
    cursor.execute("SELECT * FROM products WHERE id = %s", (id,))
    product = cursor.fetchone()

    if not product:
        cursor.close()
        return "Produk tidak ditemukan"

    # Kalau tombol submit ditekan
    if request.method == "POST":
        name = request.form.get("name")
        price = request.form.get("price")
        stock = request.form.get("stock")
        image = request.form.get("image")

        cursor.execute("""
            UPDATE products
            SET name=%s, price=%s, stock=%s, image=%s
            WHERE id=%s
        """, (name, price, stock, image, id))

        db.commit()
        cursor.close()

        return redirect("/admin/products")

    cursor.close()
    return render_template("admin_edit_product.html", product=product)

@app.route("/admin/products/delete/<int:id>")
def admin_delete_product(id):
    # Cek role admin
    if "role" not in session or session["role"] != "admin":
        return redirect("/login")

    db = get_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    cursor.execute("DELETE FROM products WHERE id = %s", (id,))
    db.commit()
    
    cursor.close()
    db.close()

    return redirect("/admin/products")


# routes.py

@app.route("/admin/orders")
@admin_required
def admin_orders():
    db = get_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    cursor.execute("""
        SELECT 
            id,
            customer_name,
            total,
            created_at,
            payment_method,
            delivery_method,
            status
        FROM orders
        ORDER BY id DESC
    """)

    orders = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template("admin_orders.html", orders=orders)

@app.route("/admin/reports")
@admin_required
def admin_reports():
    period = request.args.get("period", "weekly")

    db = get_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    today = datetime.now()

    if period == "weekly":
        start_date = today - timedelta(days=7)
    elif period == "monthly":
        start_date = today.replace(day=1)
    elif period == "yearly":
        start_date = today.replace(month=1, day=1)

    cursor.execute("""
        SELECT 
            DATE(created_at) as tanggal,
            COUNT(*) as total_order,
            IFNULL(SUM(total), 0) as total_pendapatan
        FROM orders
        WHERE created_at >= %s
        GROUP BY DATE(created_at)
        ORDER BY tanggal ASC
    """, (start_date,))

    reports = cursor.fetchall()
    cursor.close()
    db.close()

    # 🔑 pecah data untuk chart
    labels = [str(r["tanggal"]) for r in reports]
    pendapatan = [int(r["total_pendapatan"]) for r in reports]

    return render_template(
        "admin_reports.html",
        reports=reports,
        labels=labels,
        pendapatan=pendapatan,
        period=period
    )



@app.route("/admin/orders/print/<int:id>")
def admin_print_resi(id):
    db = get_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    cursor.execute("""
        SELECT 
            o.id,
            o.customer_name,
            o.total,
            o.created_at,
            o.payment_method,
            o.delivery_method,
            o.status,
            p.name AS product_name,
            1 AS qty,
            p.price
        FROM orders o
        JOIN products p ON o.product_id = p.id
        WHERE o.id = %s
    """, (id,))

    order = cursor.fetchone()

    cursor.close()
    db.close()

    if not order:
        return "Order tidak ditemukan", 404

    return render_template("print_resi.html", order=order)





@app.route("/admin/orders/delete/<int:order_id>")
def admin_delete_order(order_id):

    # Pastikan hanya admin
    if "role" not in session or session["role"] != "admin":
        return redirect("/login")

    db = get_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    cursor.execute("DELETE FROM orders WHERE id = %s", (order_id,))
    db.commit()

    cursor.close()
    db.close()

    return redirect("/admin/orders")



@app.route("/add_to_cart", methods=["POST"])
def add_to_cart():
    if "user_id" not in session:
        return jsonify({"success": False, "error": "not_logged_in"})

    user_id = session["user_id"]
    product_id = request.form.get("product_id")

    db = get_connection()

    # cek existing
    cursor = db.cursor(pymysql.cursors.DictCursor)
    cursor.execute("""
        SELECT quantity FROM cart 
        WHERE user_id = %s AND product_id = %s
    """, (user_id, product_id))
    existing = cursor.fetchone()
    cursor.close()

    # kalau SUDAH ADA → jangan tambah apa-apa, kirim pesan exists
    if existing:
        db.close()
        return jsonify({"success": False, "error": "exists"})

    # kalau BELUM ADA → baru insert
    cursor2 = db.cursor()
    cursor2.execute("""
        INSERT INTO cart (user_id, product_id, quantity) 
        VALUES (%s, %s, 1)
    """, (user_id, product_id))
    db.commit()
    cursor2.close()
    db.close()

    return jsonify({"success": True})




@app.route("/cart")
def cart():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    db = get_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    cursor.execute("""
        SELECT 
            cart.id AS cart_id,
            cart.quantity,
            products.id AS product_id,
            products.name,
            products.price,
            products.image
        FROM cart
        JOIN products ON cart.product_id = products.id
        WHERE cart.user_id = %s
    """, (user_id,))
    
    items = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template("cart.html", items=items, user_id=user_id)


@app.route("/delete_cart_item/<int:product_id>", methods=["POST"])
def delete_cart_item(product_id):
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "not logged in"}), 403

    conn = get_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    # Ambil quantity saat ini
    cursor.execute("""
        SELECT quantity FROM cart 
        WHERE user_id = %s AND product_id = %s
    """, (user_id, product_id))
    item = cursor.fetchone()

    if not item:
        cursor.close()
        conn.close()
        return jsonify({"error": "item not found"}), 404

    current_qty = item["quantity"]

    # Jika quantity > 1 → kurangi
    if current_qty > 1:
        cursor.execute("""
            UPDATE cart SET quantity = quantity - 1 
            WHERE user_id = %s AND product_id = %s
        """, (user_id, product_id))
    
    # Jika quantity == 1 → hapus row
    else:
        cursor.execute("""
            DELETE FROM cart 
            WHERE user_id = %s AND product_id = %s
        """, (user_id, product_id))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"success": True})



@app.route("/clear_cart")
def clear_cart():
    session["cart"] = []
    return redirect(url_for("cart"))

@app.route('/about') 
def about():
    return render_template('about.html')


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")

        # --- validasi dasar ---
        if not name or not email or not password:
            return render_template("register.html", error="Semua field wajib diisi!")
        elif len(password) < 8:
            return render_template("register.html", error="Password minimal 8 karakter!")

        db = get_connection()
        cursor = db.cursor(pymysql.cursors.DictCursor)

        # --- cek apakah email sudah terdaftar ---
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        existing_user = cursor.fetchone()

        if existing_user:
            cursor.close()
            db.close()
            return render_template("register.html", error="Email sudah terdaftar, silakan login.")

        # --- simpan user baru ---
        try:
            cursor.execute(
                "INSERT INTO users (name, email, password) VALUES (%s, %s, %s)",
                (name, email, password)
            )
            db.commit()
        except Exception as e:
            db.rollback()
            cursor.close()
            db.close()
            return render_template("register.html", error=f"Terjadi kesalahan: {str(e)}")

        cursor.close()
        db.close()

        return render_template("login.html", success="Register berhasil! Silakan login.")

    return render_template("register.html")




@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        # nanti bisa tambahkan logika untuk kirim email reset password
        return render_template('forgot.html', message="Link reset password telah dikirim ke email Anda (contoh).")
    return render_template('forgot.html')



# ---------------- Logout ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.route('/product/<int:product_id>')
def product_detail(product_id):
    db = get_connection()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    cursor.execute("SELECT * FROM products WHERE id = %s", (product_id,))
    product = cursor.fetchone()

    cursor.close()
    db.close()

    if not product:
        return "Product not found", 404

    return render_template('product_detail.html', product=product)



@app.route("/checkout/<int:product_id>", methods=["GET", "POST"])
def checkout(product_id):

    #  CEK LOGIN DULU
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    cursor.execute("SELECT * FROM products WHERE id = %s", (product_id,))
    product = cursor.fetchone()

    if not product:
        conn.close()
        return "Product not found", 404

    if request.method == "POST":

        full_name = request.form.get("first_name") + " " + request.form.get("last_name")

        cursor.execute("""
            INSERT INTO orders 
            (product_id, customer_name, delivery_method, payment_method, shipping, total)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            product_id,
            full_name,
            request.form.get("delivery_method"),
            request.form.get("payment_method"),
            0,
            product["price"]
        ))

        conn.commit()
        order_id = cursor.lastrowid

        cursor.close()
        conn.close()

        return redirect(url_for("checkout_success", order_id=order_id))

    cursor.close()
    conn.close()

    return render_template("checkout.html", product=product)





@app.route("/checkout/success/<int:order_id>")
def checkout_success(order_id):
    conn = get_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    cursor.execute("SELECT * FROM orders WHERE id = %s", (order_id,))
    order = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template("checkout_success.html", order=order)



@app.route("/search")
def search():
    query = request.args.get("q", "").strip()

    conn = get_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    cursor.execute(
        "SELECT * FROM products WHERE name LIKE %s",
        (f"%{query}%",)
    )

    results = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template("search.html", query=query, results=results)


@app.route("/cart-data")
def cart_data():
    user_id = session.get("user_id")
    if not user_id:
        return {"items": []}

    conn = get_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    cursor.execute("""
        SELECT 
            cart.quantity,
            products.name,
            products.price,
            products.image,
            products.id AS product_id
        FROM cart
        JOIN products ON cart.product_id = products.id
        WHERE cart.user_id = %s
    """, (user_id,))

    items = cursor.fetchall()

    cursor.close()
    conn.close()

    return {"items": items}


@app.route("/add_to_cart_ajax", methods=["POST"])
def add_to_cart_ajax():
    if "user_id" not in session:
        return {"success": False, "error": "not_logged_in"}

    user_id = session["user_id"]
    data = request.get_json()
    product_id = data.get("product_id")

    conn = get_connection()

    # Cek apakah produk sudah ada
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("""
        SELECT quantity FROM cart WHERE user_id = %s AND product_id = %s
    """, (user_id, product_id))
    existing = cursor.fetchone()
    cursor.close()

    # Insert / Update
    cursor2 = conn.cursor()
    if existing:
        cursor2.execute("""
            UPDATE cart SET quantity = quantity + 1 
            WHERE user_id = %s AND product_id = %s
        """, (user_id, product_id))
    else:
        cursor2.execute("""
            INSERT INTO cart (user_id, product_id, quantity)
            VALUES (%s, %s, 1)
        """, (user_id, product_id))

    conn.commit()
    cursor2.close()
    conn.close()

    return {"success": True}


@app.route("/get_cart_items")
def get_cart_items():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify([])

    conn = get_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("""
        SELECT 
            cart.product_id,
            products.name,
            products.image,
            products.price,
            cart.quantity
        FROM cart
        JOIN products ON cart.product_id = products.id
        WHERE cart.user_id = %s
    """, (user_id,))
    
    items = cursor.fetchall()
    cursor.close()
    conn.close()

    return jsonify(items)


@app.route('/change-password', methods=['GET', 'POST'])
def change_password():
    if request.method == 'POST':
        new_password = request.form['password']
        # UPDATE password user di database di sini
        return redirect(url_for('login'))

    return render_template('reset.html')


@app.route("/subscribe", methods=["POST"])
def subscribe():
    email = request.form.get("email")

    # (opsional) simpan ke database kalau mau
    # db = get_connection()
    # cursor = db.cursor()
    # cursor.execute("INSERT INTO subscribers (email) VALUES (%s)", (email,))
    # db.commit()
    # cursor.close()
    # db.close()

    return jsonify({"success": True})


# ---------------- Main ----------------
if __name__ == "__main__":
    app.run(debug=True)
