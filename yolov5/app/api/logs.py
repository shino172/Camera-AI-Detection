from flask import Blueprint, request, jsonify, send_file
import pandas as pd
from io import BytesIO
from app.models.database import get_conn
from werkzeug.security import check_password_hash

bp = Blueprint('logs', __name__)

@bp.route("/api/logs", methods=["GET"])
def get_logs():
    """
    Lấy danh sách log sự kiện, có thể lọc theo ngày hoặc tháng
    Ví dụ:
    /api/logs?date=2025-10-16
    /api/logs?month=2025-10
    """
    date = request.args.get("date")
    month = request.args.get("month")

    conn = get_conn()
    with conn.cursor() as cur:
        if date:
            cur.execute("SELECT * FROM events WHERE DATE(time) = %s ORDER BY time DESC", (date,))
        elif month:
            cur.execute("SELECT * FROM events WHERE DATE_FORMAT(time, '%Y-%m') = %s ORDER BY time DESC", (month,))
        else:
            cur.execute("SELECT * FROM events ORDER BY time DESC LIMIT 500")
        rows = cur.fetchall()
    
    # Get column names
    columns = [desc[0] for desc in cur.description]
    conn.close()
    
    # Convert to list of dicts
    result = []
    for row in rows:
        row_dict = {}
        for i, col in enumerate(columns):
            row_dict[col] = row[i]
            # Convert datetime to string
            if hasattr(row_dict[col], 'isoformat'):
                row_dict[col] = row_dict[col].isoformat()
        result.append(row_dict)
    
    return jsonify(result)

@bp.route("/api/logs/export/excel", methods=["GET"])
def export_logs_excel():
    """
    Xuất toàn bộ log theo ngày/tháng ra file Excel
    """
    date = request.args.get("date")
    month = request.args.get("month")

    conn = get_conn()
    with conn.cursor() as cur:
        if date:
            cur.execute("SELECT * FROM events WHERE DATE(time) = %s ORDER BY time DESC", (date,))
        elif month:
            cur.execute("SELECT * FROM events WHERE DATE_FORMAT(time, '%Y-%m') = %s ORDER BY time DESC", (month,))
        else:
            cur.execute("SELECT * FROM events ORDER BY time DESC")
        rows = cur.fetchall()
    
    # Get column names
    columns = [desc[0] for desc in cur.description]
    conn.close()

    # Convert to DataFrame
    df = pd.DataFrame(rows, columns=columns)
    
    # Convert datetime columns to string
    for col in df.columns:
        if df[col].dtype == 'datetime64[ns]':
            df[col] = df[col].dt.strftime('%Y-%m-%d %H:%M:%S')
    
    output = BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)

    filename = f"logs_{date or month or 'all'}.xlsx"
    return send_file(output, as_attachment=True, download_name=filename, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

@bp.route("/api/qr_logs", methods=["GET"])
def api_get_qr_logs():
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, camera_id, data, time
                FROM qr_logs
                ORDER BY time DESC
            """)
            rows = cur.fetchall()

        return jsonify([
            {
                "id": r[0],
                "camera_id": r[1],
                "data": r[2],
                "time": r[3].isoformat() if hasattr(r[3], 'isoformat') else r[3]
            }
            for r in rows
        ])
    except Exception as e:
        print("[QR_LOG API ERROR]", e)
        return jsonify({"error": str(e)}), 500