from datetime import datetime
import io
import os
import sqlite3
from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
import pandas as pd
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = 'khoa_bi_mat_sieu_an_toan'


# --- CỐ ĐỊNH ĐƯỜNG DẪN CƠ SỞ DỮ LIỆU ĐỂ KHÔNG BỊ MẤT DỮ LIỆU KHI TẮT MÁY ---
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'database.db')


# --- KHỞI TẠO CƠ SỞ DỮ LIỆU ---
def init_db():
  conn = sqlite3.connect(DB_PATH)
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

  # 2. Bảng đơn mua hàng (Purchases)
  cursor.execute('''
        CREATE TABLE IF NOT EXISTS purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cost_code TEXT,
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
            received_date TEXT,
            evaluation TEXT
        )
    ''')

  # Tự động bổ sung cột evaluation nếu database cũ chưa có
  cursor.execute('PRAGMA table_info(purchases)')
  columns = [column[1] for column in cursor.fetchall()]
  if 'evaluation' not in columns:
    cursor.execute('ALTER TABLE purchases ADD COLUMN evaluation TEXT')

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

    conn = sqlite3.connect(DB_PATH)
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
# QUẢN LÝ ĐƠN MUA HÀNG, TÌM KIẾM, LỌC & EXCEL
# ==========================================

@app.route('/purchases')
def list_purchases():
  if 'user_id' not in session:
    return redirect(url_for('login'))

  search_query = request.args.get('q', '').strip()
  status_filter = request.args.get('status', '').strip()

  conn = sqlite3.connect(DB_PATH)
  conn.row_factory = sqlite3.Row
  cursor = conn.cursor()

  query = 'SELECT * FROM purchases WHERE 1=1'
  params = []

  if search_query:
    query += (
        ' AND (item_code LIKE ? OR item_name LIKE ? OR cost_code LIKE ? OR'
        ' po_number LIKE ?)'
    )
    like_pattern = f'%{search_query}%'
    params.extend([like_pattern, like_pattern, like_pattern, like_pattern])

  if status_filter:
    query += ' AND status = ?'
    params.append(status_filter)

  query += ' ORDER BY id DESC'

  cursor.execute(query, params)
  purchases = cursor.fetchall()
  conn.close()

  return render_template(
      'purchases.html',
      purchases=purchases,
      search_query=search_query,
      status_filter=status_filter,
  )


@app.route('/purchases/export')
def export_purchases_excel():
  if 'user_id' not in session:
    return redirect(url_for('login'))

  conn = sqlite3.connect(DB_PATH)
  df = pd.read_sql_query('SELECT * FROM purchases ORDER BY id DESC', conn)
  conn.close()

  # Đổi tên các cột sang tiếng Việt khi xuất Excel
  df = df.rename(
      columns={
          'id': 'ID',
          'cost_code': 'Mã chi phí',
          'item_code': 'Mã vật tư',
          'item_name': 'Tên vật tư',
          'po_number': 'Số PO',
          'supplier': 'Nhà cung cấp',
          'quantity': 'Số lượng',
          'unit_price': 'Đơn giá',
          'total_price': 'Thành tiền',
          'order_date': 'Ngày đặt',
          'expected_date': 'Dự kiến nhận',
          'status': 'Trạng thái',
          'received_date': 'Ngày nhận thực tế',
          'evaluation': 'Đánh giá vật tư',
      }
  )

  output = io.BytesIO()
  with pd.ExcelWriter(output, engine='openpyxl') as writer:
    df.to_excel(writer, sheet_name='DanhSachDonHang', index=False)
  output.seek(0)

  return send_file(
      output,
      mimetype=(
          'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
      ),
      as_attachment=True,
      download_name='danh_sach_don_mua_hang.xlsx',
  )


@app.route('/purchases/add', methods=['GET', 'POST'])
def add_purchase():
  if 'user_id' not in session or session.get('role') != 'admin':
    flash('Bạn không có quyền thực hiện chức năng này!', 'danger')
    return redirect(url_for('list_purchases'))

  if request.method == 'POST':
    cost_code = request.form.get('cost_code')
    item_code = request.form.get('item_code')
    item_name = request.form['item_name']
    po_number = request.form['po_number']
    supplier = request.form['supplier']
    quantity = int(request.form['quantity'])
    unit_price = float(request.form['unit_price'])
    total_price = quantity * unit_price
    order_date = request.form['order_date']
    expected_date = request.form['expected_date']

    received_date = request.form.get('received_date')
    status = request.form['status']
    evaluation = request.form.get('evaluation', 'Chưa')

    # Tự động cập nhật trạng thái thành "Đã nhận" nếu điền ngày nhận thực tế
    if received_date and received_date.strip() != '':
      status = 'Đã nhận'

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
            INSERT INTO purchases (cost_code, item_code, item_name, po_number, supplier, quantity, unit_price, total_price, order_date, expected_date, status, received_date, evaluation)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            cost_code,
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
            evaluation,
        ),
    )
    conn.commit()
    conn.close()

    flash('Thêm đơn mua hàng thành công!', 'success')
    return redirect(url_for('list_purchases'))

  return render_template('add_purchase.html')


@app.route('/purchases/edit/<int:id>', methods=['GET', 'POST'])
def edit_purchase(id):
  if 'user_id' not in session or session.get('role') != 'admin':
    flash('Bạn không có quyền chỉnh sửa đơn hàng này!', 'danger')
    return redirect(url_for('list_purchases'))

  conn = sqlite3.connect(DB_PATH)
  conn.row_factory = sqlite3.Row
  cursor = conn.cursor()

  if request.method == 'POST':
    cost_code = request.form.get('cost_code')
    item_code = request.form.get('item_code')
    item_name = request.form['item_name']
    po_number = request.form['po_number']
    supplier = request.form['supplier']
    quantity = int(request.form['quantity'])
    unit_price = float(request.form['unit_price'])
    total_price = quantity * unit_price
    order_date = request.form['order_date']
    expected_date = request.form['expected_date']

    received_date = request.form.get('received_date')
    status = request.form['status']
    evaluation = request.form.get('evaluation', 'Chưa')

    if received_date and received_date.strip() != '':
      status = 'Đã nhận'

    cursor.execute(
        """
            UPDATE purchases 
            SET cost_code=?, item_code=?, item_name=?, po_number=?, supplier=?, quantity=?, unit_price=?, total_price=?, order_date=?, expected_date=?, status=?, received_date=?, evaluation=?
            WHERE id=?
        """,
        (
            cost_code,
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
            evaluation,
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


# ==========================================
# QUẢN LÝ TÀI KHOẢN (CHỈ ADMIN)
# ==========================================

@app.route('/users')
def list_users():
  if 'user_id' not in session or session.get('role') != 'admin':
    flash('Bạn không có quyền truy cập trang này!', 'danger')
    return redirect(url_for('index'))

  conn = sqlite3.connect(DB_PATH)
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
    role = request.form['role']

    hashed_pw = generate_password_hash(password)

    try:
      conn = sqlite3.connect(DB_PATH)
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


if __name__ == '__main__':
  app.run(host='0.0.0.0', port=5000, debug=True)
