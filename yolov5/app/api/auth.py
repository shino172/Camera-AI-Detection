from flask import Blueprint, request, jsonify
from app.models.database import get_conn
from werkzeug.security import generate_password_hash, check_password_hash

bp = Blueprint('auth', __name__)

@bp.route("/api/users/<int:person_id>/account", methods=["GET", "POST", "PUT", "DELETE"])
def api_user_account(person_id):
    conn = get_conn()
    cur = conn.cursor()

    # ---------------- GET ----------------
    if request.method == "GET":
        cur.execute("SELECT username FROM user_accounts WHERE person_id=%s", (person_id,))
        row = cur.fetchone()
        conn.close()

        if not row:
            # ⚠️ Trả 404 khi chưa có tài khoản để frontend nhận biết đúng
            return jsonify({"error": "no_account"}), 404

        return jsonify({"username": row[0]}), 200

    # ---------------- POST / PUT ----------------
    if request.method in ["POST", "PUT"]:
        data = request.get_json() or {}
        username = data.get("username")
        password = data.get("password")

        # Nếu là POST thì bắt buộc đủ username và password
        if request.method == "POST":
            if not username or not password:
                return jsonify({"error": "Thiếu username hoặc password"}), 400

            hashed = generate_password_hash(password)
            cur.execute(
                "INSERT INTO user_accounts (person_id, username, password) VALUES (%s, %s, %s)",
                (person_id, username, hashed)
            )
            conn.commit()
            conn.close()
            return jsonify({"message": "Tạo tài khoản thành công"}), 201

        # Nếu là PUT thì cho phép chỉ cập nhật 1 trong 2 trường
        update_fields = []
        params = []

        if username:
            update_fields.append("username=%s")
            params.append(username)

        if password:
            hashed = generate_password_hash(password)
            update_fields.append("password=%s")
            params.append(hashed)

        if not update_fields:
            conn.close()
            return jsonify({"error": "Không có dữ liệu để cập nhật"}), 400

        params.append(person_id)
        query = f"UPDATE user_accounts SET {', '.join(update_fields)} WHERE person_id=%s"
        cur.execute(query, tuple(params))
        conn.commit()
        conn.close()
        return jsonify({"message": "Cập nhật tài khoản thành công"}), 200

    # ---------------- DELETE ----------------
    if request.method == "DELETE":
        cur.execute("DELETE FROM user_accounts WHERE person_id=%s", (person_id,))
        conn.commit()
        conn.close()
        return jsonify({"message": "Đã xóa tài khoản"}), 200

@bp.route("/api/user_accounts", methods=["GET"])
def api_get_user_accounts():
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT person_id, username FROM user_accounts")
        rows = cur.fetchall()
    conn.close()
    return jsonify([{"person_id": r[0], "username": r[1]} for r in rows])

@bp.route("/api/auth/login", methods=["POST"])
def api_user_login():
    data = request.get_json() or {}
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"error": "Thiếu username hoặc password"}), 400

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT user_id, password FROM user_accounts WHERE username=%s", (username,))
    row = cur.fetchone()

    if not row:
        conn.close()
        return jsonify({"error": "Tài khoản không tồn tại"}), 401

    user_id, hashed = row

    if not check_password_hash(hashed, password):
        conn.close()
        return jsonify({"error": "Sai mật khẩu"}), 401

    # ✅ Lấy quyền của user
    cur.execute("SELECT code FROM user_permissions WHERE user_id=%s", (user_id,))
    permissions = [r[0] for r in cur.fetchall()]
    conn.close()

    return jsonify({
        "message": "Đăng nhập thành công",
        "username": username,
        "permissions": permissions
    })

@bp.route("/api/users/<int:person_id>/permissions", methods=["GET", "POST"])
def api_user_permissions(person_id):
    conn = get_conn()
    cur = conn.cursor()

    # 🔹 Lấy user_id từ bảng accounts
    cur.execute("SELECT user_id FROM user_accounts WHERE person_id=%s", (person_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "User chưa có tài khoản"}), 404

    user_id = row[0]

    if request.method == "GET":
        cur.execute("SELECT code FROM user_permissions WHERE user_id=%s", (user_id,))
        codes = [r[0] for r in cur.fetchall()]
        conn.close()
        return jsonify(codes)

    if request.method == "POST":
        data = request.get_json() or {}
        codes = data.get("codes", [])

        cur.execute("DELETE FROM user_permissions WHERE user_id=%s", (user_id,))
        for code in codes:
            cur.execute(
                "INSERT INTO user_permissions (user_id, code) VALUES (%s, %s)",
                (user_id, code)
            )
        conn.commit()
        conn.close()
        return jsonify({"message": "Cập nhật quyền thành công"})

@bp.route("/api/users/<int:user_id>/permissions", methods=["POST"])
def assign_permissions(user_id):
    data = request.get_json() or {}
    codes = data.get("codes", [])

    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM role_permissions WHERE role_id IN (SELECT role_id FROM user_roles WHERE user_id=%s)", (user_id,))
            cur.execute("SELECT role_id FROM user_roles WHERE user_id=%s", (user_id,))
            row = cur.fetchone()
            if not row:
                cur.execute("INSERT INTO roles (name) VALUES (%s) RETURNING id", (f"user_{user_id}",))
                role_id = cur.fetchone()[0]
                cur.execute("INSERT INTO user_roles (user_id, role_id) VALUES (%s, %s)", (user_id, role_id))
            else:
                role_id = row[0]

            for code in codes:
                cur.execute("SELECT id FROM permissions WHERE code=%s", (code,))
                perm = cur.fetchone()
                if perm:
                    cur.execute(
                        "INSERT INTO role_permissions (role_id, permission_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                        (role_id, perm[0])
                    )
    return jsonify({"status": "ok"})