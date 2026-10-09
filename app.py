from datetime import datetime
import io
import os
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
from flask_sqlalchemy import SQLAlchemy
import openpyxl
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = 'khoa_bi_mat_sieu_an_toan'

# Lấy chuỗi kết nối từ biến môi trường trên Render (DATABASE_URL)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# --- MODEL DATABASE TRÊN SUPABASE ---
class Purchase(db.Model):
  __tablename__ = 'purchases'
  id = db.Column(db.Integer, primary_key=True)
  cost_code = db.Column(db.String(100))
  purpose = db.Column(db.Text)
  item_code = db.Column(db.String(100))
  item_name = db.Column(db.Text, nullable=False)
  po_number = db.Column(db.String(100), nullable=False)
  supplier = db.Column(db.String(255), nullable=False)
  unit = db.Column(db.String(50))
  quantity = db.Column(db.Integer, nullable=False)
  unit_price = db.Column(db.Numeric(15, 2), nullable=False)
  sc_received_date = db.Column(db.Date)
  expected_date = db.Column(db.Date)
  received_date = db.Column(db.Date)
  status = db.Column(db.String(50), default='Chưa nhận')
  evaluation = db.Column(db.Text, default='chưa')


# Danh sách tài khoản hệ thống (Admin / Viewer)
USERS_DB = [
    {
        'id': 1,
        'username': 'admin',
        'password': generate_password_hash('admin123@'),
        'role': 'admin',
    },
    {
        'id': 2,
        'username': 'Huyen',
        'password': generate_password_hash('123456'),
        'role': 'viewer',
    },
]


@app.route('/')
def index():
  if 'user_id' not in session:
    return redirect(url_for('login'))
  return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
  if request.method == 'POST':
    username = request.form['username']
    password = request.form['password']
    user = next((u for u in USERS_DB if u['username'] == username), None)

    if user and check_password_hash(user['password'], password):
      session['user_id'] = user['id']
      session['username'] = user['username']
      session['role'] = user['role']
      flash('Đăng nhập thành công!', 'success')
      return redirect(url_for('index'))
    else:
      flash('Tên đăng nhập hoặc mật khẩu không chính xác!', 'danger')

  return render_template('login.html')


@app.route('/logout')
def logout():
  session.clear()
  flash('Đã đăng xuất.', 'info')
  return redirect(url_for('login'))


# --- QUẢN LÝ TÀI KHOẢN (ADMIN) ---
@app.route('/users')
def list_users():
  if 'user_id' not in session or session.get('role') != 'admin':
    flash('Bạn không có quyền truy cập trang này!', 'danger')
    return redirect(url_for('index'))
  return render_template('users.html', users=USERS_DB)


@app.route('/users/add', methods=['GET', 'POST'])
def add_user():
  if 'user_id' not in session or session.get('role') != 'admin':
    flash('Bạn không có quyền thực hiện chức năng này!', 'danger')
    return redirect(url_for('index'))

  if request.method == 'POST':
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    role = request.form.get('role', 'viewer')

    if not username or not password:
      flash('Vui lòng nhập đầy đủ tên đăng nhập và mật khẩu!', 'danger')
      return redirect(url_for('add_user'))

    if any(u['username'] == username for u in USERS_DB):
      flash('Tên đăng nhập này đã tồn tại!', 'danger')
      return redirect(url_for('add_user'))

    new_id = len(USERS_DB) + 1
    USERS_DB.append({
        'id': new_id,
        'username': username,
        'password': generate_password_hash(password),
        'role': role,
    })
    flash(
        f"Tạo tài khoản '{username}' (Quyền: {role}) thành công!", 'success'
    )
    return redirect(url_for('list_users'))

  return render_template('add_user.html')


# --- QUẢN LÝ ĐƠN HÀNG (TRUY VẤN TRỰC TIẾP TỪ SUPABASE) ---
@app.route('/purchases')
def list_purchases():
  if 'user_id' not in session:
    return redirect(url_for('login'))

  search_query = request.args.get('q', '').strip().lower()
  status_filter = request.args.get('status', '').strip()

  # Lấy dữ liệu từ Supabase sắp xếp theo ID mới nhất
  purchases_query = Purchase.query.order_by(Purchase.id.desc()).all()

  filtered_purchases = []
  for p in purchases_query:
    # Tự động đồng bộ trạng thái nếu có ngày nhận thực tế
    p_status = (
        'Đã nhận'
        if p.received_date
        else (p.status if p.status else 'Chưa nhận')
    )

    p_dict = {
        'id': p.id,
        'cost_code': p.cost_code or '',
        'purpose': p.purpose or '',
        'item_code': p.item_code or '',
        'item_name': p.item_name or '',
        'po_number': p.po_number or '',
        'supplier': p.supplier or '',
        'unit': p.unit or '',
        'quantity': p.quantity or 0,
        'unit_price': float(p.unit_price) if p.unit_price else 0,
        'sc_received_date': (
            p.sc_received_date.strftime('%d/%m/%Y')
            if p.sc_received_date
            else ''
        ),
        'expected_date': (
            p.expected_date.strftime('%d/%m/%Y') if p.expected_date else ''
        ),
        'status': p_status,
        'received_date': (
            p.received_date.strftime('%d/%m/%Y') if p.received_date else ''
        ),
        'evaluation': p.evaluation or '',
    }

    if status_filter and p_dict['status'] != status_filter:
      continue

    if search_query:
      combined_text = (
          f"{p_dict['item_code']} {p_dict['item_name']} {p_dict['cost_code']}"
          f" {p_dict['purpose']} {p_dict['po_number']} {p_dict['supplier']}"
      ).lower()
      if search_query not in combined_text:
        continue

    filtered_purchases.append(p_dict)

  return render_template(
      'purchases.html',
      purchases=filtered_purchases,
      search_query=search_query,
      status_filter=status_filter,
  )


@app.route('/purchases/export')
def export_purchases_excel():
  if 'user_id' not in session:
    return redirect(url_for('login'))

  purchases_query = Purchase.query.order_by(Purchase.id.desc()).all()

  wb = openpyxl.Workbook()
  ws = wb.active
  ws.title = 'DanhSachDonHang'

  headers = [
      'ID',
      'Mã CP',
      'Mục đích sử dụng',
      'Mã vật tư',
      'Tên vật tư',
      'Số PO',
      'Nhà cung cấp',
      'ĐVT',
      'SL',
      'Đơn giá',
      'Thành tiền',
      'Ngày SC nhận phiếu YC',
      'Ngày dự kiến hàng về',
      'Trạng thái',
      'Ngày nhận thực tế',
      'Đánh giá vật tư',
  ]
  ws.append(headers)

  for p in purchases_query:
    qty = p.quantity or 0
    price = float(p.unit_price) if p.unit_price else 0
    total = qty * price

    row = [
        p.id,
        p.cost_code or '',
        p.purpose or '',
        p.item_code or '',
        p.item_name or '',
        p.po_number or '',
        p.supplier or '',
        p.unit or '',
        qty,
        price,
        total,
        (
            p.sc_received_date.strftime('%d/%m/%Y')
            if p.sc_received_date
            else ''
        ),
        p.expected_date.strftime('%d/%m/%Y') if p.expected_date else '',
        (
            'Đã nhận'
            if p.received_date
            else (p.status if p.status else 'Chưa nhận')
        ),
        p.received_date.strftime('%d/%m/%Y') if p.received_date else '',
        p.evaluation or '',
    ]
    ws.append(row)

  output = io.BytesIO()
  wb.save(output)
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
    try:
      sc_date = (
          datetime.strptime(request.form['sc_received_date'], '%Y-%m-%d').date()
          if request.form.get('sc_received_date')
          else None
      )
      exp_date = (
          datetime.strptime(request.form['expected_date'], '%Y-%m-%d').date()
          if request.form.get('expected_date')
          else None
      )
      rec_date = (
          datetime.strptime(request.form['received_date'], '%Y-%m-%d').date()
          if request.form.get('received_date')
          else None
      )

      new_p = Purchase(
          cost_code=request.form.get('cost_code', ''),
          purpose=request.form.get('purpose', ''),
          item_code=request.form.get('item_code', ''),
          item_name=request.form['item_name'],
          po_number=request.form['po_number'],
          supplier=request.form['supplier'],
          unit=request.form.get('unit', ''),
          quantity=int(request.form['quantity']),
          unit_price=float(request.form['unit_price']),
          sc_received_date=sc_date,
          expected_date=exp_date,
          received_date=rec_date,
          evaluation=request.form.get('evaluation', 'chưa'),
      )
      db.session.add(new_p)
      db.session.commit()
      flash('Thêm đơn mua hàng thành công!', 'success')
    except Exception as e:
      db.session.rollback()
      flash(f'Lỗi khi lưu vào database: {e}', 'danger')

    return redirect(url_for('list_purchases'))

  return render_template('add_purchase.html')


@app.route('/purchases/edit/<int:id>', methods=['GET', 'POST'])
def edit_purchase(id):
  if 'user_id' not in session or session.get('role') == 'viewer':
    flash('Bạn không có quyền chỉnh sửa đơn hàng này!', 'danger')
    return redirect(url_for('list_purchases'))

  p = Purchase.query.get_or_404(id)

  # Chuyển đổi dữ liệu ngày tháng sang định dạng YYYY-MM-DD để hiển thị chuẩn vào form
  purchase_dict = {
      'id': p.id,
      'cost_code': p.cost_code or '',
      'purpose': p.purpose or '',
      'item_code': p.item_code or '',
      'item_name': p.item_name or '',
      'po_number': p.po_number or '',
      'supplier': p.supplier or '',
      'unit': p.unit or '',
      'quantity': p.quantity or 0,
      'unit_price': float(p.unit_price) if p.unit_price else 0,
      'sc_received_date': (
          p.sc_received_date.strftime('%Y-%m-%d')
          if p.sc_received_date
          else ''
      ),
      'expected_date': (
          p.expected_date.strftime('%Y-%m-%d') if p.expected_date else ''
      ),
      'received_date': (
          p.received_date.strftime('%Y-%m-%d') if p.received_date else ''
      ),
      'evaluation': p.evaluation or '',
  }

  if request.method == 'POST':
    try:
      p.cost_code = request.form.get('cost_code', '')
      p.purpose = request.form.get('purpose', '')
      p.item_code = request.form.get('item_code', '')
      p.item_name = request.form['item_name']
      p.po_number = request.form['po_number']
      p.supplier = request.form['supplier']
      p.unit = request.form.get('unit', '')
      p.quantity = int(request.form['quantity'])
      p.unit_price = float(request.form['unit_price'])

      p.sc_received_date = (
          datetime.strptime(request.form['sc_received_date'], '%Y-%m-%d').date()
          if request.form.get('sc_received_date')
          else None
      )
      p.expected_date = (
          datetime.strptime(request.form['expected_date'], '%Y-%m-%d').date()
          if request.form.get('expected_date')
          else None
      )
      p.received_date = (
          datetime.strptime(request.form['received_date'], '%Y-%m-%d').date()
          if request.form.get('received_date')
          else None
      )
      p.evaluation = request.form.get('evaluation', 'chưa')

      db.session.commit()
      flash('Cập nhật đơn mua hàng thành công!', 'success')
    except Exception as e:
      db.session.rollback()
      flash(f'Lỗi khi cập nhật database: {e}', 'danger')

    return redirect(url_for('list_purchases'))

  return render_template('edit_purchase.html', purchase=purchase_dict)


if __name__ == '__main__':
  app.run(host='0.0.0.0', port=5000, debug=True)
