from datetime import datetime, date
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

# Lấy chuỗi kết nối từ biến môi trường trên Render (DATABASE_URL qua cổng 6543 Session Pooler)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- MODEL DATABASE TRÊN SUPABASE ---
class Purchase(db.Model):
    __tablename__ = 'purchases'
    id = db.Column(db.Integer, primary_key=True)
    cost_code = db.Column(db.String(100))
    requester = db.Column(db.String(100))  # Người yêu cầu (chỉ lưu DB)
    purpose = db.Column(db.Text)            # Mục đích (chỉ lưu DB)
    item_code = db.Column(db.String(100))
    item_name = db.Column(db.Text, nullable=False)
    po_number = db.Column(db.String(100), nullable=False)
    supplier = db.Column(db.String(255), nullable=True)  # Cho phép bỏ trống
    unit = db.Column(db.String(50))
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Numeric(15, 2), nullable=True)  # Cho phép bỏ trống
    sc_received_date = db.Column(db.Date)
    expected_date = db.Column(db.Date)
    received_date = db.Column(db.Date)
    status = db.Column(db.String(50), default='Chưa nhận')
    evaluation = db.Column(db.Text, default='chưa')

# Danh sách tài khoản hệ thống (admin / ketoan / nhanvien)
USERS_DB = [
    {
        'id': 1,
        'username': 'admin',
        'password': generate_password_hash('admin123'),
        'role': 'admin',  # Toàn quyền
    },
    {
        'id': 2,
        'username': 'Huyen',
        'password': generate_password_hash('123456'),
        'role': 'editor',  # Thêm đơn, sửa ngày dự kiến, không sửa cái khác, không tải Excel
    },
    {
        'id': 3,
        'username': 'nhanvien',
        'password': generate_password_hash('123456'),
        'role': 'viewer',  # Chỉ xem
    },
]

# Hàm tự động tính trạng thái thông minh
def calculate_status(p):
    if p.expected_date and date.today() > p.expected_date and (not p.received_date):
        return 'Trễ hẹn'
        
    if p.status and p.status in ['Đã giao', 'Nhận 1 phần', 'Hoàn thành', 'Trễ hẹn']:
        return p.status
        
    return p.status if p.status else 'Chưa nhận'

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('list_purchases'))

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
            return redirect(url_for('list_purchases'))
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
    
    purchases_query = Purchase.query.order_by(Purchase.id.desc()).all()
    filtered_purchases = []
    
    for p in purchases_query:
        current_status = calculate_status(p)
        
        # Mặc định nếu không chọn bộ lọc trạng thái, chỉ hiển thị 'Chưa nhận' và 'Trễ hẹn'
        if not status_filter:
            if current_status not in ['Chưa nhận', 'Trễ hẹn']:
                continue
        else:
            # Nếu người dùng chủ động chọn bộ lọc trạng thái cụ thể
            if current_status != status_filter:
                continue
        
        rec_date_str = p.received_date.strftime('%d/%m/%Y') if p.received_date else ''
        exp_date_str = p.expected_date.strftime('%d/%m/%Y') if p.expected_date else ''
        sc_date_str = p.sc_received_date.strftime('%d/%m/%Y') if p.sc_received_date else ''
        
        p_dict = {
            'id': p.id,
            'cost_code': p.cost_code or '',
            'requester': p.requester or '',
            'purpose': p.purpose or '',
            'item_code': p.item_code or '',
            'item_name': p.item_name or '',
            'po_number': p.po_number or '',
            'supplier': p.supplier or '',
            'unit': p.unit or '',
            'quantity': p.quantity or 0,
            'unit_price': float(p.unit_price) if p.unit_price else 0,
            'sc_received_date': sc_date_str,
            'expected_date': exp_date_str,
            'status': current_status,
            'received_date': rec_date_str,
            'evaluation': p.evaluation or '',
        }
            
        if search_query:
            combined_text = (
                f"{p_dict['item_code']} {p_dict['item_name']} {p_dict['cost_code']} "
                f"{p_dict['requester']} {p_dict['purpose']} {p_dict['po_number']} {p_dict['supplier']} "
                f"{p_dict['received_date']} {p_dict['expected_date']}"
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

@app.route('/purchases/add', methods=['GET', 'POST'])
def add_purchase():
    role = session.get('role')
    if 'user_id' not in session or role not in ['admin', 'editor']:
        flash('Bạn không có quyền thực hiện chức năng này!', 'danger')
        return redirect(url_for('list_purchases'))
        
    if request.method == 'POST':
        try:
            sc_date = datetime.strptime(request.form['sc_received_date'], '%Y-%m-%d').date() if request.form.get('sc_received_date') else None
            exp_date = datetime.strptime(request.form['expected_date'], '%Y-%m-%d').date() if request.form.get('expected_date') else None
            rec_date = datetime.strptime(request.form['received_date'], '%Y-%m-%d').date() if request.form.get('received_date') else None
            
            unit_price_val = float(request.form['unit_price']) if request.form.get('unit_price') else 0.0
            supplier_val = request.form.get('supplier', '').strip()
            
            new_p = Purchase(
                cost_code=request.form.get('cost_code', ''),
                requester=request.form.get('requester', ''),
                purpose=request.form.get('purpose', ''),
                item_code=request.form.get('item_code', ''),
                item_name=request.form['item_name'],
                po_number=request.form['po_number'],
                supplier=supplier_val,
                unit=request.form.get('unit', ''),
                quantity=int(request.form['quantity']),
                unit_price=unit_price_val,
                sc_received_date=sc_date,
                expected_date=exp_date,
                received_date=rec_date,
                status=request.form.get('status', 'Chưa nhận'),
                evaluation=request.form.get('evaluation', 'chưa')
            )
            db.session.add(new_p)
            db.session.commit()
            flash('Thêm đơn hàng thành công!', 'success')
            return redirect(url_for('list_purchases'))
        except Exception as e:
            db.session.rollback()
            flash(f'Lỗi khi thêm đơn hàng: {e}', 'danger')
            
    return render_template('add_purchase.html')

@app.route('/purchases/edit/<int:id>', methods=['GET', 'POST'])
def edit_purchase(id):
    role = session.get('role')
    if 'user_id' not in session or role not in ['admin', 'editor']:
        flash('Bạn không có quyền thực hiện chức năng này!', 'danger')
        return redirect(url_for('list_purchases'))
        
    p = Purchase.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            if role == 'admin':
                p.cost_code = request.form.get('cost_code', '')
                p.requester = request.form.get('requester', '')
                p.purpose = request.form.get('purpose', '')
                p.item_code = request.form.get('item_code', '')
                p.item_name = request.form['item_name']
                p.po_number = request.form['po_number']
                p.supplier = request.form.get('supplier', '').strip()
                p.unit = request.form.get('unit', '')
                p.quantity = int(request.form['quantity'])
                p.unit_price = float(request.form['unit_price']) if request.form.get('unit_price') else 0.0
                p.sc_received_date = datetime.strptime(request.form['sc_received_date'], '%Y-%m-%d').date() if request.form.get('sc_received_date') else None
                p.received_date = datetime.strptime(request.form['received_date'], '%Y-%m-%d').date() if request.form.get('received_date') else None
                p.status = request.form.get('status', 'Chưa nhận')
                p.evaluation = request.form.get('evaluation', 'chưa')
            
            p.expected_date = datetime.strptime(request.form['expected_date'], '%Y-%m-%d').date() if request.form.get('expected_date') else None
            
            db.session.commit()
            flash('Cập nhật đơn hàng thành công!', 'success')
            return redirect(url_for('list_purchases'))
        except Exception as e:
            db.session.rollback()
            flash(f'Lỗi khi cập nhật đơn hàng: {e}', 'danger')
            
    return render_template('edit_purchase.html', p=p)

@app.route('/purchases/export')
def export_purchases_excel():
    if 'user_id' not in session or session.get('role') == 'editor':
        flash('Bạn không có quyền tải file Excel!', 'danger')
        return redirect(url_for('list_purchases'))
    
    purchases = Purchase.query.order_by(Purchase.id.desc()).all()
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Danh Sach Don Hang"
    
    headers = [
        "ID", "Mã Chi Phí", "Người Yêu Cầu", "Mục Đích", "Mã Vật Tư", "Tên Vật Tư", 
        "Số PO", "Nhà Cung Cấp", "ĐVT", "Số Lượng", "Đơn Giá", 
        "Thành Tiền", "Ngày SC Nhận", "Ngày Dự Kiến", "Ngày Thực Tế", 
        "Trạng Thái", "Đánh Giá"
    ]
    ws.append(headers)
    
    for p in purchases:
        current_status = calculate_status(p)
        total_price = float(p.quantity * p.unit_price) if p.quantity and p.unit_price else 0
        ws.append([
            p.id,
            p.cost_code or '',
            p.requester or '',
            p.purpose or '',
            p.item_code or '',
            p.item_name or '',
            p.po_number or '',
            p.supplier or '',
            p.unit or '',
            p.quantity or 0,
            float(p.unit_price) if p.unit_price else 0,
            total_price,
            p.sc_received_date.strftime('%d/%m/%Y') if p.sc_received_date else '',
            p.expected_date.strftime('%d/%m/%Y') if p.expected_date else '',
            p.received_date.strftime('%d/%m/%Y') if p.received_date else '',
            current_status,
            p.evaluation or ''
        ])
        
    file_stream = io.BytesIO()
    wb.save(file_stream)
    file_stream.seek(0)
    
    return send_file(
        file_stream,
        as_attachment=True,
        download_name=f"Danh_Sach_Don_Hang_{date.today().strftime('%d%m%Y')}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
