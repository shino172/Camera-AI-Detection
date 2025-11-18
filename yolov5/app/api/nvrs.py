from flask import Blueprint, request, jsonify
from app.models.database import get_conn

bp = Blueprint('nvrs', __name__)

@bp.route("/api/nvrs", methods=["POST"])
def api_create_nvr():
    data = request.json
    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO nvrs (name, ip_address, port, username, password)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (data["name"], data["ip_address"], data["port"], data["username"], data["password"]))
            nvr_id = cur.fetchone()[0]
    conn.close()
    return jsonify({"id": nvr_id, "message": "NVR created successfully"}), 201

@bp.route("/api/nvrs/<int:nvr_id>", methods=["PUT"])
def api_update_nvr(nvr_id):
    data = request.json or {}

    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            # Lấy bản ghi hiện tại
            cur.execute("SELECT name, ip_address, port, username, password FROM nvrs WHERE id=%s", (nvr_id,))
            old = cur.fetchone()
            if not old:
                conn.close()
                return jsonify({"error": "NVR not found"}), 404

            # Gán giá trị mới (nếu không có thì giữ cũ)
            name = data.get("name", old[0])
            ip_address = data.get("ip_address", old[1])
            port = data.get("port", old[2])
            username = data.get("username", old[3])
            password = data.get("password", old[4])

            # Thực hiện cập nhật
            cur.execute("""
                UPDATE nvrs
                SET name=%s, ip_address=%s, port=%s, username=%s, password=%s
                WHERE id=%s
            """, (name, ip_address, port, username, password, nvr_id))
        conn.commit()
    conn.close()
    return jsonify({"message": "NVR updated successfully"})

@bp.route("/api/nvrs/<int:nvr_id>", methods=["DELETE"])
def api_delete_nvr(nvr_id):
    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM nvrs WHERE id=%s", (nvr_id,))
    conn.close()
    return jsonify({"message": "NVR deleted successfully"})

@bp.route("/api/nvrs", methods=["GET"])
def api_get_nvrs():
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 
                id,
                name,
                ip_address,
                port,
                username,
                password
            FROM nvrs
            ORDER BY id;
        """)
        rows = cur.fetchall()
    conn.close()

    return jsonify([
        {
            "id": r[0],
            "name": r[1],
            "ip_address": r[2],
            "port": r[3],
            "username": r[4],
            "password": r[5]
        } for r in rows
    ])

@bp.route("/api/nvrs-with-cameras", methods=["GET"])
def api_nvrs_with_cameras():
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 
                n.id AS nvr_id, n.name AS nvr_name, n.ip_address, n.port,
                c.camera_id, c.name AS camera_name, c.status, c.area_id
            FROM nvrs n
            LEFT JOIN cameras c ON n.id = c.nvr_id
            ORDER BY n.id, c.camera_id
        """)
        rows = cur.fetchall()
    conn.close()

    nvrs = {}
    for r in rows:
        nvr_id = r[0]
        if nvr_id not in nvrs:
            nvrs[nvr_id] = {
                "id": nvr_id,
                "name": r[1],
                "ip": r[2],
                "port": r[3],
                "cameras": []
            }
        if r[4]:
            nvrs[nvr_id]["cameras"].append({
                "id": r[4],
                "name": r[5],
                "status": r[6],
                "area_id": r[7]
            })

    return jsonify(list(nvrs.values()))