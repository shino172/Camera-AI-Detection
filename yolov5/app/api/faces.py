from flask import Blueprint, request, jsonify, json
import tempfile
import os, json
import cloudinary.uploader
from app.models.database import load_db_cache, append_db_entry, delete_db_entry, update_db_name, get_conn
from app.models.database import _db_cache_ids, _db_cache_names, _db_cache_images, _db_cache_empids
from app.models.face_recognition import pending_faces, lock

bp = Blueprint('faces', __name__)

@bp.route("/faces", methods=["GET"])
def api_get_faces():
    load_db_cache()
    return jsonify([
        {
            "id": fid,
            "name": name,
            "image": img,
            "person_id": pid
        }
        for fid, name, img, pid in zip(_db_cache_ids, _db_cache_names, _db_cache_images, _db_cache_empids)
    ])

@bp.route("/faces/assign", methods=["POST"])
def api_assign_face():
    data = request.json or {}
    face_id = data.get("face_id")
    name = data.get("name")

    if not face_id or not name:
        return jsonify({"error": "face_id and name required"}), 400

    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            cur.execute("SELECT image_url FROM faces WHERE id=%s", (face_id,))
            row = cur.fetchone()
            image_url = row[0] if row else None

            if not image_url:
                pf = pending_faces.get(face_id)
                if pf and pf.get("image_b64"):
                    import base64
                    tmp_path = f"/tmp/{face_id}.jpg"
                    with open(tmp_path, "wb") as f:
                        f.write(base64.b64decode(pf["image_b64"]))
                    try:
                        upload = cloudinary.uploader.upload(tmp_path, folder="faces")
                        image_url = upload.get("secure_url")
                    except Exception as e:
                        print("[UPLOAD PENDING FACE ERROR]", e)

                        cur.execute("""
                            INSERT INTO persons (name, avatar)
                            VALUES (%s, %s)
                            ON CONFLICT (name) DO UPDATE SET avatar = COALESCE(persons.avatar, EXCLUDED.avatar)
                            RETURNING person_id
                        """, (name, image_url))

            person_id = cur.fetchone()[0]

            cur.execute("""
                UPDATE faces
                SET name=%s, person_id=%s, image_url=%s
                WHERE id=%s
            """, (name, person_id, image_url, face_id))

    global _db_cache_ts
    _db_cache_ts = 0

    return jsonify({"message": "Face assigned successfully", "person_id": person_id, "avatar": image_url})

@bp.route("/faces/<face_id>", methods=["PUT"])
def api_update_face(face_id):
    data = request.json or {}
    name = data.get("name")
    if not name:
        return jsonify({"error": "name required"}), 400
    try:
        updated = update_db_name(face_id, name)
        if not updated:
            return jsonify({"error": "update_failed"}), 404
        return jsonify({"updated": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500 

@bp.route("/faces/<face_id>", methods=["DELETE"])
def api_delete_face(face_id):
    try:
        deleted = delete_db_entry(face_id)
        if not deleted:
            return jsonify({"error": "not_found"}), 404
        return jsonify({"deleted": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bp.route("/pending_faces", methods=["GET"])
def api_get_pending_faces():
    with lock:
        result = [
            {
                "id": fid,
                "image_b64": f.get("image_b64"),
                "tempName": f.get("tempName", ""),
            }
            for fid, f in pending_faces.items()
        ]
    return jsonify(result)

@bp.route("/pending_faces/assign", methods=["POST"])
def api_assign_pending_face():
    data = request.json or {}
    pending_id = data.get("pending_id")
    name = data.get("name")

    if not pending_id or not name:
        return jsonify({"error": "pending_id and name required"}), 400

    with lock:
        pf = pending_faces.pop(pending_id, None)
    if not pf:
        return jsonify({"error": "pending_face not found"}), 404

    image_url = None
    if pf.get("image_b64"):
        try:
            import base64, io
            img_bytes = base64.b64decode(pf["image_b64"])
            tmp_dir = tempfile.gettempdir()
            tmp_path = os.path.join(tmp_dir, f"{pending_id}.jpg")
            with open(tmp_path, "wb") as f:
                f.write(img_bytes)
            upload = cloudinary.uploader.upload(tmp_path, folder="faces")
            image_url = upload.get("secure_url")
        except Exception as e:
            print("[UPLOAD PENDING FACE ERROR]", e)

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

            cur.execute("""
                INSERT INTO faces (id, person_id, name, encoding, image_url)
                VALUES (gen_random_uuid(), %s, %s, %s, %s)
                RETURNING id
            """, (person_id, name, json.dumps(pf["encoding"]), image_url))
            face_id = cur.fetchone()[0]

    global _db_cache_ts
    _db_cache_ts = 0
    load_db_cache(force=True)

    return jsonify({
        "message": "Pending face assigned successfully",
        "face_id": str(face_id),
        "person_id": person_id,
        "name": name,
        "image_url": image_url
    })

@bp.route("/pending_faces/<face_id>", methods=["DELETE"])
def api_delete_pending_face(face_id):
    with lock:
        if face_id in pending_faces:
            pending_faces.pop(face_id, None)
            return jsonify({"status": "deleted", "id": face_id})
    return jsonify({"error": "not_found"}), 404