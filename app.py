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
import openpyxl
import requests
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = 'khoa_bi_mat_sieu_an_toan'

WEB_APP_URL = (
    'https://script.google.com/macros/s/AKfycbxG8bO19LoMxxIFnde9E8xzT-NE4GfSpVcJbu4GGO0Wzw9GcwSe6QkJPE3vp0D4nRrK/exec'
)

# Danh sách tài khoản hệ thống (Admin và Viewer)
USERS_DB = [
    {
        'id': 1,
        'username': 'admin',
        'password': generate_password_hash('admin123'),
        'role': 'admin',
    },
    {
        'id': 2,
        'username': 'nhanvien',
        'password': generate_password_hash('123456'),
        'role': 'viewer',
    },
]


def format_date_str(date_str):
  if not date_str:
    return ''
  try:
    if 'T' in str(date_str):
      date_str = str(date_str).split('T')[0]
    dt = datetime.strptime(date_str.strip(), '%Y-%m-%d')
    return dt.strftime('%d/%m/%Y')
  except Exception:
    return str(date_str)


def get_all_purchases():
  try:
    response = requests.get(WEB_APP_URL, timeout=15)
    if response.status_code == 200:
      raw_data = response.json()
      normalized_data = []
      if isinstance(raw_data, list):
        for item in raw_data:
          new_item = {}
          for k, v in item.items():
            new_item[str(k).lower().strip()] = v
          normalized_data.append(new_item)
      return normalized_data
  except Exception as e:
    print(f'Lỗi kết nối Google Sheets (GET): {e}')
  return []


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


# --- QUẢN LÝ TÀI KHOẢN (DÀNH CHO ADMIN) ---
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


# --- QUẢN LÝ ĐƠN HÀNG ---
@app.route('/purchases')
def list_purchases():
  if 'user_id' not in session:
    return redirect(url_for('login'))

  search_query = request.args.get('q', '').strip().lower()
  status_filter = request.args.get('status', '').strip()

  purchases = get_all_purchases()

  filtered_purchases = []
  for p in reversed(purchases):
    if not str(p.get('id', '')):
      continue

    received_date_raw = str(p.get('received_date', '')).strip()
    if received_date_raw and received_date_raw.lower() not in [
        'none',
        'nan',
        '',
        'chưa',
    ]:
      p['status'] = 'Đã nhận'
    else:
      if not p.get('status') or p.get('status').strip() == '':
        p['status'] = 'Chưa nhận'

    p['sc_received_date'] = format_date_str(p.get('sc_received_date', ''))
    p['expected_date'] = format_date_str(p.get('expected_date', ''))
    p['received_date'] = format_date_str(p.get('received_date', ''))

    if status_filter and str(p.get('status', '')) != status_filter:
      continue

    if search_query:
      combined_text = (
          f"{p.get('item_code', '')} {p.get('item_name', '')}"
          f" {p.get('cost_code', '')} {p.get('purpose', '')}"
          f" {p.get('po_number', '')} {p.get('supplier', '')}"
      ).lower()
      if search_query not in combined_text:
        continue

    filtered_purchases.append(p)

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

  purchases = get_all_purchases()

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

  for p in purchases:
    row = [
        p.get('id', ''),
        p.get('cost_code', ''),
        p.get('purpose', ''),
        p.get('item_code', ''),
        p.get('item_name', ''),
        p.get('po_number', ''),
        p.get('supplier', ''),
        p.get('unit', ''),
        p.get('quantity', ''),
        p.get('unit_price', ''),
        p.get('total_price', ''),
        format_date_str(p.get('sc_received_date', '')),
        format_date_str(p.get('expected_date', '')),
        p.get('status', ''),
        format_date_str(p.get('received_date', '')),
        p.get('evaluation', ''),
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
    purchases = get_all_purchases()
    new_id = len(purchases) + 1

    cost_code = request.form.get('cost_code', '')
    purpose = request.form.get('purpose', '')
    item_code = request.form.get('item_code', '')
    item_name = request.form['item_name']
    po_number = request.form['po_number']
    supplier = request.form['supplier']
    unit = request.form.get('unit', '')
    quantity = int(request.form['quantity'])
    unit_price = float(request.form['unit_price'])

    sc_received_date = request.form.get('sc_received_date', '')
    expected_date = request.form.get('expected_date', '')
    received_date = request.form.get('received_date', '')
    evaluation = request.form.get('evaluation', 'chưa')

    payload = {
        'action': 'add',
        'id': new_id,
        'cost_code': cost_code,
        'purpose': purpose,
        'item_code': item_code,
        'item_name': item_name,
        'po_number': po_number,
        'supplier': supplier,
        'unit': unit,
        'quantity': quantity,
        'unit_price': unit_price,
        'sc_received_date': sc_received_date,
        'expected_date': expected_date,
        'received_date': received_date,
        'evaluation': evaluation,
    }

    try:
      response = requests.post(WEB_APP_URL, json=payload, timeout=15)
      if response.status_code == 200:
        res_json = response.json()
        if res_json.get('status') == 'success':
          flash('Thêm đơn mua hàng thành công lên Google Sheets!', 'success')
        else:
          flash(
              f"Lỗi từ Google Sheets: {res_json.get('message', 'Không rõ')}",
              'danger',
          )
      else:
        flash(
            f'Lỗi kết nối Google Sheets (HTTP Status {response.status_code})',
            'danger',
        )
    except Exception as e:
      flash(f'Lỗi khi lưu lên Google Sheets: {e}', 'danger')

    return redirect(url_for('list_purchases'))

  return render_template('add_purchase.html')


@app.route('/purchases/edit/<int:id>', methods=['GET', 'POST'])
def edit_purchase(id):
  if 'user_id' not in session or session.get('role') == 'viewer':
    flash('Bạn không có quyền chỉnh sửa đơn hàng này!', 'danger')
    return redirect(url_for('list_purchases'))

  purchases = get_all_purchases()
  purchase = next((p for p in purchases if int(p.get('id', 0)) == id), None)

  if not purchase:
    flash('Không tìm thấy đơn hàng cần sửa!', 'danger')
    return redirect(url_for('list_purchases'))

  # Xử lý chuẩn hóa ngày tháng về định dạng YYYY-MM-DD để hiển thị chuẩn vào thẻ input type="date"
  for date_field in ['sc_received_date', 'expected_date', 'received_date']:
    val = str(purchase.get(date_field, '')).strip()
    if val and val.lower() not in ['none', 'nan', '']:
      if 'T' in val:
        val = val.split('T')[0]
      elif len(val) == 10 and val[2] == '/' and val[5] == '/':
        parts = val.split('/')
        val = f'{parts[2]}-{parts[1]}-{parts[0]}'
      purchase[date_field] = val
    else:
      purchase[date_field] = ''

  if request.method == 'POST':
    cost_code = request.form.get('cost_code', '')
    purpose = request.form.get('purpose', '')
    item_code = request.form.get('item_code', '')
    item_name = request.form['item_name']
    po_number = request.form['po_number']
    supplier = request.form['supplier']
    unit = request.form.get('unit', '')
    quantity = int(request.form['quantity'])
    unit_price = float(request.form['unit_price'])

    sc_received_date = request.form.get('sc_received_date', '')
    expected_date = request.form.get('expected_date', '')
    received_date = request.form.get('received_date', '')
    evaluation = request.form.get('evaluation', 'chưa')

    payload = {
        'action': 'update',
        'id': id,
        'cost_code': cost_code,
        'purpose': purpose,
        'item_code': item_code,
        'item_name': item_name,
        'po_number': po_number,
        'supplier': supplier,
        'unit': unit,
        'quantity': quantity,
        'unit_price': unit_price,
        'sc_received_date': sc_received_date,
        'expected_date': expected_date,
        'received_date': received_date,
        'evaluation': evaluation,
    }

    try:
      response = requests.post(WEB_APP_URL, json=payload, timeout=15)
      if response.status_code == 200:
        res_json = response.json()
        if res_json.get('status') == 'success':
          flash('Cập nhật đơn mua hàng thành công!', 'success')
        else:
          flash(
              f"Lỗi cập nhật từ Google Sheets: {res_json.get('message', 'Không rõ')}",
              'danger',
          )
      else:
        flash(
            f'Lỗi kết nối Google Sheets khi cập nhật (HTTP {response.status_code})',
            'danger',
        )
    except Exception as e:
      flash(f'Lỗi khi cập nhật Google Sheets: {e}', 'danger')

    return redirect(url_for('list_purchases'))

  return render_template('edit_purchase.html', purchase=purchase)


if __name__ == '__main__':
  app.run(host='0.0.0.0', port=5000, debug=True)
