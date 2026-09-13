import os
import sqlite3
from flask import Flask, flash, redirect, render_template_string, request, url_for
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = "khoa_bi_mat_sieu_an_toan"


def init_db():
  conn = sqlite3.connect("quan_ly_thiet_bi.db")
  cursor = conn.cursor()
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS thiet_bi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ten_tb TEXT NOT NULL,
            loai_tb TEXT,
            trang_thai TEXT
        )
    """)
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS phu_tung (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ten_pt TEXT NOT NULL,
            so_luong INTEGER,
            gia REAL
        )
    """)
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS lich_su_sua_chua (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            thiet_bi_id INTEGER,
            ngay TEXT,
            noi_dung TEXT,
            chi_phi REAL,
            FOREIGN KEY (thiet_bi_id) REFERENCES thiet_bi (id)
        )
    """)
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL 
        )
    """)
  # Tài khoản admin mặc định: admin / 123456
  cursor.execute("SELECT * FROM users WHERE username = 'admin'")
  if not cursor.fetchone():
    hashed_pw = generate_password_hash("123456")
    cursor.execute(
        "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
        ("admin", hashed_pw, "admin"),
    )
  conn.commit()
  conn.close()


BASE_LAYOUT = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8"><title>Quản lý Thiết bị & Phân quyền</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; background: #f4f6f9; }
        .header { background: #343a40; color: white; padding: 15px 20px; display: flex; justify-content: space-between; align-items: center; }
        .container { padding: 20px; }
        .nav a { margin-right: 15px; text-decoration: none; font-weight: bold; color: #007bff; }
        table { width: 100%; border-collapse: collapse; background: white; margin-bottom: 20px; }
        th, td { border: 1px solid #ddd; padding: 10px; text-align: left; }
        th { background-color: #007bff; color: white; }
        form { background: white; padding: 15px; border-radius: 5px; margin-bottom: 20px; width: fit-content; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        input, select { padding: 8px; margin-right: 10px; margin-bottom: 10px; width: 220px; display: block; }
        button { padding: 8px 15px; background: #28a745; color: white; border: none; cursor: pointer; border-radius: 3px; }
        .logout-btn { background: #dc3545; padding: 5px 10px; color: white; text-decoration: none; border-radius: 3px; }
        .alert { color: red; font-weight: bold; margin-bottom: 10px; }
        .success { color: green; font-weight: bold; margin-bottom: 10px; }
    </style>
</head>
<body>
    <div class="header">
        <div>Xin chào: <b>{{ session.get('user') }}</b> (Quyền: <b>{{ session.get('role') }}</b>)</div>
        <div><a href="/logout" class="logout-btn">Đăng xuất</a></div>
    </div>
    <div class="container">
        <div class="nav">
            <a href="/">Thiết bị</a> | 
            <a href="/phu_tung">Phụ tùng</a> | 
            <a href="/lich_su">Lịch sử sửa chữa</a> | 
            <a href="/doi_mat_khau">Đổi mật khẩu</a>
            {% if session.get('role') == 'admin' %} | <a href="/quan_ly_user" style="color: #d9534f;">Quản lý Tài khoản (Admin)</a>{% endif %}
        </div>
        <hr>
        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            {% for cat, msg in messages %}
              <div class="{{ 'success' if cat == 'success' else 'alert' }}">{{ msg }}</div>
            {% endfor %}
          {% endif %}
        {% endwith %}
        {{ content | safe }}
    </div>
</body>
</html>
"""

LOGIN_HTML = """
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>Đăng nhập</title>
<style>
    body { font-family: Arial; background: #f4f6f9; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
    .login-box { background: white; padding: 30px; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); width: 300px; }
    input { width: 100%; padding: 10px; margin-bottom: 15px; box-sizing: border-box; border: 1px solid #ccc; border-radius: 4px; }
    button { width: 100%; padding: 10px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; }
    .error { color: red; margin-bottom: 15px; font-size: 14px; text-align: center; }
</style>
</head>
<body>
<div class="login-box">
    <h2 style="text-align: center; margin-top:0;">Đăng Nhập</h2>
    {% with messages = get_flashed_messages() %}{% if messages %}<div class="error">{{ messages[0] }}</div>{% endif %}{% endwith %}
    <form method="POST">
        <label>Tên đăng nhập:</label><input type="text" name="username" required>
        <label>Mật khẩu:</label><input type="password" name="password" required>
        <button type="submit">Đăng Nhập</button>
    </form>
</div>
</body>
</html>
"""


@app.route("/login", methods=["GET", "POST"])
def login():
  if request.method == "POST":
    username = request.form["username"]
    password = request.form["password"]
    conn = sqlite3.connect("quan_ly_thiet_bi.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, password, role FROM users WHERE username = ?", (username,)
    )
    user = cursor.fetchone()
    conn.close()
    if user and check_password_hash(user[1], password):
      from flask import session

      session["user"] = username
      session["role"] = user[2]
      return redirect(url_for("index"))
    else:
      flash("Sai tài khoản hoặc mật khẩu!")
  return render_template_string(LOGIN_HTML)


@app.route("/logout")
def logout():
  from flask import session

  session.clear()
  return redirect(url_for("login"))


@app.route("/doi_mat_khau", methods=["GET", "POST"])
def doi_mat_khau():
  from flask import session

  if "user" not in session:
    return redirect(url_for("login"))

  if request.method == "POST":
    old_password = request.form["old_password"]
    new_password = request.form["new_password"]
    username = session["user"]

    conn = sqlite3.connect("quan_ly_thiet_bi.db")
    cursor = conn.cursor()
    cursor.execute("SELECT password FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()

    if user and check_password_hash(user[0], old_password):
      hashed_new_pw = generate_password_hash(new_password)
      cursor.execute(
          "UPDATE users SET password = ? WHERE username = ?",
          (hashed_new_pw, username),
      )
      conn.commit()
      conn.close()
      flash("Đổi mật khẩu thành công!", "success")
    else:
      conn.close()
      flash("Mật khẩu cũ không chính xác!", "error")

  content = """
    <h2>Đổi mật khẩu cá nhân</h2>
    <form method="POST">
        <label>Mật khẩu cũ:</label>
        <input type="password" name="old_password" required>
        <label>Mật khẩu mới:</label>
        <input type="password" name="new_password" required>
        <button type="submit">Cập nhật mật khẩu</button>
    </form>
    """
  return render_template_string(BASE_LAYOUT, content=content)


@app.route("/")
def index():
  from flask import session

  if "user" not in session:
    return redirect(url_for("login"))
  conn = sqlite3.connect("quan_ly_thiet_bi.db")
  cursor = conn.cursor()
  cursor.execute("SELECT * FROM thiet_bi")
  data = cursor.fetchall()
  conn.close()
  form_html = (
      """
    <h3>Thêm thiết bị mới</h3>
    <form action="/add_tb" method="POST">
        <input type="text" name="ten_tb" placeholder="Tên thiết bị" required>
        <input type="text" name="loai_tb" placeholder="Loại thiết bị">
        <input type="text" name="trang_thai" placeholder="Trạng thái">
        <button type="submit">Lưu thiết bị</button>
    </form>
    """
      if session.get("role") == "admin"
      else ""
  )
  content = (
      form_html
      + """
    <h2>Danh sách Thiết bị</h2>
    <table><tr><th>ID</th><th>Tên thiết bị</th><th>Loại</th><th>Trạng thái</th></tr>
    {% for row in data %}<tr><td>{{row[0]}}</td><td>{{row[1]}}</td><td>{{row[2]}}</td><td>{{row[3]}}</td></tr>{% endfor %}
    </table>
    """
  )
  return render_template_string(BASE_LAYOUT, content=content, data=data)


@app.route("/add_tb", methods=["POST"])
def add_tb():
  from flask import session

  if session.get("role") != "admin":
    return "Không có quyền", 403
  conn = sqlite3.connect("quan_ly_thiet_bi.db")
  cursor = conn.cursor()
  cursor.execute(
      "INSERT INTO thiet_bi (ten_tb, loai_tb, trang_thai) VALUES (?, ?, ?)",
      (
          request.form["ten_tb"],
          request.form["loai_tb"],
          request.form["trang_thai"],
      ),
  )
  conn.commit()
  conn.close()
  return redirect(url_for("index"))


@app.route("/phu_tung")
def phu_tung():
  from flask import session

  if "user" not in session:
    return redirect(url_for("login"))
  conn = sqlite3.connect("quan_ly_thiet_bi.db")
  cursor = conn.cursor()
  cursor.execute("SELECT * FROM phu_tung")
  data = cursor.fetchall()
  conn.close()
  form_html = (
      """
    <h3>Thêm phụ tùng mới</h3>
    <form action="/add_pt" method="POST">
        <input type="text" name="ten_pt" placeholder="Tên phụ tùng" required>
        <input type="number" name="so_luong" placeholder="Số lượng" required>
        <input type="number" step="any" name="gia" placeholder="Đơn giá" required>
        <button type="submit">Lưu phụ tùng</button>
    </form>
    """
      if session.get("role") == "admin"
      else ""
  )
  content = (
      form_html
      + """
    <h2>Kho Phụ Tùng</h2>
    <table><tr><th>ID</th><th>Tên phụ tùng</th><th>Số lượng</th><th>Đơn giá</th></tr>
    {% for row in data %}<tr><td>{{row[0]}}</td><td>{{row[1]}}</td><td>{{row[2]}}</td><td>{{row[3]}}</td></tr>{% endfor %}
    </table>
    """
  )
  return render_template_string(BASE_LAYOUT, content=content, data=data)


@app.route("/add_pt", methods=["POST"])
def add_pt():
  from flask import session

  if session.get("role") != "admin":
    return "Không có quyền", 403
  conn = sqlite3.connect("quan_ly_thiet_bi.db")
  cursor = conn.cursor()
  cursor.execute(
      "INSERT INTO phu_tung (ten_pt, so_luong, gia) VALUES (?, ?, ?)",
      (
          request.form["ten_pt"],
          int(request.form["so_luong"]),
          float(request.form["gia"]),
      ),
  )
  conn.commit()
  conn.close()
  return redirect(url_for("phu_tung"))


@app.route("/lich_su")
def lich_su():
  from flask import session

  if "user" not in session:
    return redirect(url_for("login"))
  conn = sqlite3.connect("quan_ly_thiet_bi.db")
  cursor = conn.cursor()
  cursor.execute("SELECT id, ten_tb FROM thiet_bi")
  thiet_bi_list = cursor.fetchall()
  cursor.execute("""
        SELECT lich_su_sua_chua.id, thiet_bi.ten_tb, lich_su_sua_chua.ngay, 
               lich_su_sua_chua.noi_dung, lich_su_sua_chua.chi_phi 
        FROM lich_su_sua_chua JOIN thiet_bi ON lich_su_sua_chua.thiet_bi_id = thiet_bi.id
    """)
  data = cursor.fetchall()
  conn.close()
  content = """
    <h3>Ghi nhận sửa chữa</h3>
    <form action="/add_ls" method="POST">
        <select name="thiet_bi_id" required><option value="">-- Chọn thiết bị --</option>
        {% for tb in thiet_bi_list %}<option value="{{tb[0]}}">{{tb[1]}}</option>{% endfor %}</select>
        <input type="text" name="ngay" placeholder="Ngày sửa (VD: 13/09/2026)" required>
        <input type="text" name="noi_dung" placeholder="Nội dung sửa" required>
        <input type="number" step="any" name="chi_phi" placeholder="Chi phí (VNĐ)">
        <button type="submit">Lưu lịch sử</button>
    </form>
    <h2>Lịch sử Sửa Chữa</h2>
    <table><tr><th>ID</th><th>Thiết bị</th><th>Ngày</th><th>Nội dung</th><th>Chi phí</th></tr>
    {% for row in data %}<tr><td>{{row[0]}}</td><td>{{row[1]}}</td><td>{{row[2]}}</td><td>{{row[3]}}</td><td>{{row[4]}}</td></tr>{% endfor %}
    </table>
    """
  return render_template_string(
      BASE_LAYOUT, content=content, data=data, thiet_bi_list=thiet_bi_list
  )


@app.route("/add_ls", methods=["POST"])
def add_ls():
  from flask import session

  if "user" not in session:
    return redirect(url_for("login"))
  conn = sqlite3.connect("quan_ly_thiet_bi.db")
  cursor = conn.cursor()
  cursor.execute(
      "INSERT INTO lich_su_sua_chua (thiet_bi_id, ngay, noi_dung, chi_phi)"
      " VALUES (?, ?, ?, ?)",
      (
          int(request.form["thiet_bi_id"]),
          request.form["ngay"],
          request.form["noi_dung"],
          float(request.form["chi_phi"]) if request.form["chi_phi"] else 0,
      ),
  )
  conn.commit()
  conn.close()
  return redirect(url_for("lich_su"))


@app.route("/quan_ly_user", methods=["GET", "POST"])
def quan_ly_user():
  from flask import session

  if session.get("role") != "admin":
    return "Không có quyền", 403
  if request.method == "POST":
    try:
      conn = sqlite3.connect("quan_ly_thiet_bi.db")
      cursor = conn.cursor()
      cursor.execute(
          "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
          (
              request.form["new_username"],
              generate_password_hash(request.form["new_password"]),
              request.form["new_role"],
          ),
      )
      conn.commit()
      conn.close()
      flash("Tạo tài khoản thành công!", "success")
    except:
      flash("Tên đăng nhập đã tồn tại!", "error")
  conn = sqlite3.connect("quan_ly_thiet_bi.db")
  cursor = conn.cursor()
  cursor.execute("SELECT id, username, role FROM users")
  users = cursor.fetchall()
  conn.close()
  content = """
    <h2>Quản lý Tài khoản & Phân quyền</h2>
    <form method="POST">
        <input type="text" name="new_username" placeholder="Tên đăng nhập" required>
        <input type="password" name="new_password" placeholder="Mật khẩu" required>
        <select name="new_role" required>
            <option value="nhanvien">Nhân viên (Xem & Ghi lịch sử)</option>
            <option value="admin">Admin (Toàn quyền quản lý)</option>
        </select>
        <button type="submit">Tạo tài khoản</button>
    </form>
    <table><tr><th>ID</th><th>Tên đăng nhập</th><th>Quyền hạn</th></tr>
    {% for u in users %}<tr><td>{{u[0]}}</td><td>{{u[1]}}</td><td>{{u[2]}}</td></tr>{% endfor %}
    </table>
    """
  return render_template_string(BASE_LAYOUT, content=content, users=users)


if __name__ == "__main__":
  init_db()
  port = int(os.environ.get("PORT", 5000))
  app.run(host="0.0.0.0", port=port)