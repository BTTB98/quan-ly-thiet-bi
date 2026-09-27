from datetime import datetime
import sqlite3
from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Thay đổi khóa bí mật của bạn


# --- KHỞI TẠO CƠ SỞ DỮ LIỆU ---
def init_db():
  conn = sqlite3.connect('database.db')
  cursor = conn.cursor()

  # 1. Bảng người dùng (Users)
  cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
    ''')

  # 2. Bảng thiết bị (Equipment)
  cursor.execute('''
        CREATE TABLE IF NOT EXISTS equipment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            code TEXT UNIQUE NOT NULL,
            status TEXT NOT NULL
        )
    ''')

  # 3. Bảng đơn mua hàng (Purchases) theo yêu cầu mới
  cursor.execute('''
        CREATE TABLE IF NOT EXISTS purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_code TEXT,
            item_name TEXT NOT NULL,
            po_number TEXT,
            supplier TEXT,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            total_price REAL NOT NULL,
            order_date TEXT,
            expected_date TEXT,
            status TEXT,
            received_date TEXT
        )
    ''')

  # Tạo tài khoản Admin mặc định nếu chưa có
  cursor.execute('SELECT * FROM users WHERE username = ?', ('admin',))
  if not cursor.fetchone():
    hashed_pw = generate_password_hash('admin123')
    cursor.execute(
        'INSERT INTO users (username, password, role) VALUES (?, ?, ?)',
        ('admin', hashed_pw, 'admin'),
    )

  conn.commit()
  conn.close()


init_db()


# --- TRANG CHỦ ---
@app.route('/')
def index():
  if 'user_id' not in session:
    return redirect(url_for('login'))
  return render_template('index.html')


# --- ĐĂNG NHẬP ---
@app.route('/login', methods=['GET', 'POST'])
def login():
  if request.method == 'POST':
    username = request.form['username']
    password = request.form['password']

    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()
    conn.close()

    if user and check_password_hash(user['password'], password):
      session['user_id'] = user['id']
      session['username'] = user['username']
      session['role'] = user['role']
      flash('Đăng nhập thành công!', 'success')
      return redirect(url_for('index'))
    else:
      flash('Tên đăng nhập hoặc mật khẩu không chính xác!', 'danger')

  return render_template('login.html')


# --- ĐĂNG XUẤT ---
@app.route('/logout')
def logout():
  session.clear()
  flash('Đã đăng xuất.', 'info')
  return redirect(url_for('login'))


# ==========================================
# QUẢN LÝ ĐƠN MUA HÀNG (PURCHASES)
# ==========================================

# Xem danh sách đơn mua hàng (Tất cả người dùng đã đăng nhập đều xem được)
@app.route('/purchases')
def list_purchases():
  if 'user_id' not in session:
    return redirect(url_for('login'))

  conn = sqlite3.connect('database.db')
  conn.row_factory = sqlite3.Row
  cursor = conn.cursor()
  cursor.execute('SELECT * FROM purchases ORDER BY id DESC')
  purchases = cursor.fetchall()
  conn.close()

  return render_template('purchases.html', purchases=purchases)


# Thêm đơn mua hàng (Chỉ Admin)
@app.route('/purchases/add', methods=['GET', 'POST'])
def add_purchase():
  if 'user_id' not in session or session.get('role') != 'admin':
    flash('Bạn không có quyền thực hiện chức năng này!', 'danger')
    return redirect(url_for('list_purchases'))

  if request.method == 'POST':
    item_code = request.form.get('item_code')
    item_name = request.form['item_name']
    po_number = request.form['po_number']
    supplier = request.form['supplier']
    quantity = int(request.form['quantity'])
    unit_price = float(request.form['unit_price'])
    total_price = quantity * unit_price  # Tự động tính thành tiền
    order_date = request.form['order_date']
    expected_date = request.form['expected_date']
    status = request.form['status']
    received_date = request.form.get('received_date')

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute(
        """
            INSERT INTO purchases (item_code, item_name, po_number, supplier, quantity, unit_price, total_price, order_date, expected_date, status, received_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            item_code,
            item_name,
            po_number,
            supplier,
            quantity,
            unit_price,
            total_price,
            order_date,
            expected_date,
            status,
            received_date,
        ),
    )
    conn.commit()
    conn.close()

    flash('Thêm đơn mua hàng thành công!', 'success')
    return redirect(url_for('list_purchases'))

  return render_template('add_purchase.html')


# Sửa đơn mua hàng (Chỉ Admin)
@app.route('/purchases/edit/<int:id>', methods=['GET', 'POST'])
def edit_purchase(id):
  if 'user_id' not in session or session.get('role') != 'admin':
    flash('Bạn không có quyền chỉnh sửa đơn hàng này!', 'danger')
    return redirect(url_for('list_purchases'))

  conn = sqlite3.connect('database.db')
  conn.row_factory = sqlite3.Row
  cursor = conn.cursor()

  if request.method == 'POST':
    item_code = request.form.get('item_code')
    item_name = request.form['item_name']
    po_number = request.form['po_number']
    supplier = request.form['supplier']
    quantity = int(request.form['quantity'])
    unit_price = float(request.form['unit_price'])
    total_price = quantity * unit_price
    order_date = request.form['order_date']
    expected_date = request.form['expected_date']
    status = request.form['status']
    received_date = request.form.get('received_date')

    cursor.execute(
        """
            UPDATE purchases 
            SET item_code=?, item_name=?, po_number=?, supplier=?, quantity=?, unit_price=?, total_price=?, order_date=?, expected_date=?, status=?, received_date=?
            WHERE id=?
        """,
        (
            item_code,
            item_name,
            po_number,
            supplier,
            quantity,
            unit_price,
            total_price,
            order_date,
            expected_date,
            status,
            received_date,
            id,
        ),
    )
    conn.commit()
    conn.close()

    flash('Cập nhật đơn mua hàng thành công!', 'success')
    return redirect(url_for('list_purchases'))

  cursor.execute('SELECT * FROM purchases WHERE id = ?', (id,))
  purchase = cursor.fetchone()
  conn.close()

  return render_template('edit_purchase.html', purchase=purchase)


if __name__ == '__main__':
  app.run(host='0.0.0.0', port=5000, debug=True)
  # --- QUẢN LÝ TÀI KHOẢN (CHỈ ADMIN) ---
@app.route('/users')
def list_users():
  if 'user_id' not in session or session.get('role') != 'admin':
    flash('Bạn không có quyền truy cập trang này!', 'danger')
    return redirect(url_for('index'))

  conn = sqlite3.connect('database.db')
  conn.row_factory = sqlite3.Row
  cursor = conn.cursor()
  cursor.execute('SELECT id, username, role FROM users')
  users = cursor.fetchall()
  conn.close()

  return render_template('users.html', users=users)


@app.route('/users/add', methods=['GET', 'POST'])
def add_user():
  if 'user_id' not in session or session.get('role') != 'admin':
    flash('Bạn không có quyền thêm tài khoản!', 'danger')
    return redirect(url_for('index'))

  if request.method == 'POST':
    username = request.form['username']
    password = request.form['password']
    role = request.form['role']  # 'admin' hoặc 'staff' (nhân viên)

    hashed_pw = generate_password_hash(password)

    try:
      conn = sqlite3.connect('database.db')
      cursor = conn.cursor()
      cursor.execute(
          'INSERT INTO users (username, password, role) VALUES (?, ?, ?)',
          (username, hashed_pw, role),
      )
      conn.commit()
      conn.close()
      flash(f'Đã tạo tài khoản "{username}" thành công!', 'success')
      return redirect(url_for('list_users'))
    except sqlite3.IntegrityError:
      flash('Tên đăng nhập này đã tồn tại, vui lòng chọn tên khác!', 'danger')

  return render_template('add_user.html')
  # --- QUẢN LÝ TÀI KHOẢN (CHỈ ADMIN) ---
@app.route('/users')
def list_users():
  if 'user_id' not in session or session.get('role') != 'admin':
    flash('Bạn không có quyền truy cập trang này!', 'danger')
    return redirect(url_for('index'))

  import sqlite3

  conn = sqlite3.connect('database.db')
  conn.row_factory = sqlite3.Row
  cursor = conn.cursor()
  cursor.execute('SELECT id, username, role FROM users')
  users = cursor.fetchall()
  conn.close()

  return render_template('users.html', users=users)


@app.route('/users/add', methods=['GET', 'POST'])
def add_user():
  if 'user_id' not in session or session.get('role') != 'admin':
    flash('Bạn không có quyền thêm tài khoản!', 'danger')
    return redirect(url_for('index'))

  if request.method == 'POST':
    username = request.form['username']
    password = request.form['password']
    role = request.form['role']  # 'admin' hoặc 'staff'

    hashed_pw = generate_password_hash(password)

    try:
      import sqlite3

      conn = sqlite3.connect('database.db')
      cursor = conn.cursor()
      cursor.execute(
          'INSERT INTO users (username, password, role) VALUES (?, ?, ?)',
          (username, hashed_pw, role),
      )
      conn.commit()
      conn.close()
      flash(f'Đã tạo tài khoản "{username}" thành công!', 'success')
      return redirect(url_for('list_users'))
    except sqlite3.IntegrityError:
      flash('Tên đăng nhập này đã tồn tại, vui lòng chọn tên khác!', 'danger')

  return render_template('add_user.html')
