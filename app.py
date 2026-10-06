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
import pandas as pd
import requests
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = 'khoa_bi_mat_sieu_an_toan'

# --- ĐƯỜNG DẪN WEB APP GOOGLE APPS SCRIPT CỦA BẠN ---
# Hãy thay thế đoạn chuỗi bên dưới bằng URL Web App bạn nhận được từ Google Apps Script
WEB_APP_URL = https://script.google.com/macros/s/AKfycbxG8bO19LoMxxIFnde9E8xzT-NE4GfSpVcJbu4GGO0Wzw9GcwSe6QkJPE3vp0D4nRrK/exec

# Tài khoản mặc định hệ thống (có thể thay đổi tùy ý)
DEFAULT_USERS = [
    {
        'id': 1,
        'username': 'admin',
        'password': generate_password_hash('admin123'),
        'role': 'admin',
    }
]


def get_all_purchases():
  try:
    response = requests.get(WEB_APP_URL)
    if response.status_code == 200:
      return response.json()
  except Exception as e:
    print(f'Lỗi kết nối Google Sheets: {e}')
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
    user = next((u for u in DEFAULT_USERS if u['username'] == username), None)

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
  df = pd.DataFrame(purchases)

  if not df.empty:
    df = df.rename(
        columns={
            'id': 'ID',
            'cost_code': 'Mã CP',
            'purpose': 'Mục đích sử dụng',
            'item_code': 'Mã vật tư',
            'item_name': 'Tên vật tư',
            'po_number': 'Số PO',
            'supplier': 'Nhà cung cấp',
            'unit': 'ĐVT',
            'quantity': 'SL',
            'unit_price': 'Đơn giá',
            'total_price': 'Thành tiền',
            'sc_received_date': 'Ngày SC nhận phiếu YC',
            'expected_date': 'Ngày dự kiến hàng về',
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
      requests.post(WEB_APP_URL, json=payload)
      flash('Thêm đơn mua hàng thành công lên Google Sheets!', 'success')
    except Exception as e:
      flash(f'Lỗi khi lưu lên Google Sheets: {e}', 'danger')

    return redirect(url_for('list_purchases'))

  return render_template('add_purchase.html')


@app.route('/purchases/edit/<int:id>', methods=['GET', 'POST'])
def edit_purchase(id):
  if 'user_id' not in session or session.get('role') != 'admin':
    flash('Bạn không có quyền chỉnh sửa đơn hàng này!', 'danger')
    return redirect(url_for('list_purchases'))

  purchases = get_all_purchases()
  purchase = next((p for p in purchases if int(p.get('id', 0)) == id), None)

  if not purchase:
    flash('Không tìm thấy đơn hàng cần sửa!', 'danger')
    return redirect(url_for('list_purchases'))

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
      requests.post(WEB_APP_URL, json=payload)
      flash('Cập nhật đơn mua hàng thành công!', 'success')
    except Exception as e:
      flash(f'Lỗi khi cập nhật Google Sheets: {e}', 'danger')

    return redirect(url_for('list_purchases'))

  return render_template('edit_purchase.html', purchase=purchase)


if __name__ == '__main__':
  app.run(host='0.0.0.0', port=5000, debug=True)
