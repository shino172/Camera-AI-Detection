from flask import Blueprint, request, jsonify
import tempfile
import os
import cloudinary.uploader
import base64
from app.models.database import get_conn
from werkzeug.security import generate_password_hash, check_password_hash

bp = Blueprint('persons', __name__)

@bp.route("/persons", methods=["GET"])
def api_get_persons():
    conn = get_conn()
    with conn: 
        with conn.cursor() as cur:
            cur.execute("SELECT person_id, name, avatar, email, phone, department, position, created_at FROM persons")
            rows = cur.fetchall()
        return jsonify([
            {
                "person_id": r[0],
                "name": r[1],
                "avatar": r[2],
                "email": r[3],
                "phone": r[4],
                "department": r[5],
                "position": r[6],
                "created_at": r[7].isoformat() if r[7] else None     
            } for r in rows
        ])

@bp.route("/persons/<int:person_id>", methods=["PUT"])
def api_update_person(person_id):
    data = request.json or {}
    fields = ["name", "email", "phone", "department", "position", "avatar"]
    updates, values = [], []
    for f in fields:
        if f in data:
            updates.append(f"{f}=%s")
            values.append(data[f])
    if not updates:
        return jsonify({"error": "no fields to update"}), 400
    values.append(person_id)

    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            cur.execute(f"UPDATE persons SET {', '.join(updates)} WHERE person_id=%s", values)
            if cur.rowcount == 0:
                return jsonify({"error": "person not found"}), 404
    return jsonify({"updated": True})

@bp.route("/persons/<int:person_id>", methods=["DELETE"])
def api_delete_person(person_id):
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT person_id FROM persons WHERE person_id = %s", (person_id,))
                if not cur.fetchone():
                    return jsonify({"error": "person_not_found"}), 404

                cur.execute("DELETE FROM faces WHERE person_id = %s", (person_id,))
                cur.execute("DELETE FROM persons WHERE person_id = %s", (person_id,))

        global _db_cache_ts
        _db_cache_ts = 0

        return jsonify({"deleted": True})
    except Exception as e:
        print("[DELETE PERSON ERROR]", e)
        return jsonify({"error": str(e)}), 500
    finally:
        try:
            conn.close()
        except:
            pass

@bp.route("/persons/manual_add", methods=["POST"])
def api_manual_add_person():
    """API thêm nhân viên thủ công từ frontend, có thể kèm ảnh base64."""
    try:
        data = request.get_json() or {}
        name = data.get("name")
        image_b64 = data.get("image")

        if not name:
            return jsonify({"error": "Thiếu tên nhân viên"}), 400

        # Nếu có ảnh thì upload Cloudinary
        image_url = None
        if image_b64:
            img_bytes = base64.b64decode(image_b64)
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
            tmp.write(img_bytes)
            tmp.close()
            upload = cloudinary.uploader.upload(tmp.name, folder="faces")
            image_url = upload.get("secure_url")
            os.remove(tmp.name)

        conn = get_conn()
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO persons (name, avatar)
                    VALUES (%s, %s)
                    ON CONFLICT (name) DO UPDATE SET avatar = EXCLUDED.avatar
                    RETURNING person_id
                """, (name, image_url))
                person_id = cur.fetchone()[0]

                if image_url:
                    cur.execute("""
                        INSERT INTO faces (id, person_id, name, encoding, image_url)
                        VALUES (gen_random_uuid(), %s, %s, '[]', %s)
                        RETURNING id
                    """, (person_id, name, image_url))

        global _db_cache_ts
        _db_cache_ts = 0

        return jsonify({
            "message": "Thêm nhân viên thủ công thành công",
            "person_id": person_id,
            "image_url": image_url
        }), 201

    except Exception as e:
        print("[MANUAL ADD ERROR]", e)
        return jsonify({"error": str(e)}), 500

@bp.route("/upload/avatar", methods=["POST"])
def api_upload_avatar():
    """Upload ảnh base64 từ frontend -> Cloudinary -> trả về URL"""
    try:
        data = request.get_json() or {}
        image_b64 = data.get("image")

        if not image_b64:
            return jsonify({"error": "Missing image"}), 400

        # Giải mã base64 -> file tạm
        img_bytes = base64.b64decode(image_b64)
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
        tmp_file.write(img_bytes)
        tmp_file.close()

        # Upload Cloudinary
        upload_result = cloudinary.uploader.upload(tmp_file.name, folder="faces")
        image_url = upload_result.get("secure_url")

        os.remove(tmp_file.name)
        return jsonify({"status": "ok", "image_url": image_url})
    except Exception as e:
        print("[UPLOAD AVATAR ERROR]", e)
        return jsonify({"error": str(e)}), 500

@bp.route("/persons/<int:person_id>/avatar", methods=["PUT"])
def api_set_avatar(person_id):
    data = request.json
    image = data.get("image")
    if not image:
        return jsonify({"error": "Missing image"}), 400
    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE persons SET avatar=%s WHERE person_id=%s", (image, person_id))
    conn.close()
    return jsonify({"status": "ok"})