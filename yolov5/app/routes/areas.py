from flask import Blueprint, jsonify, request
from ..db import get_conn


areas_bp = Blueprint('areas', __name__)


@areas_bp.route('/', methods=['GET'])
def get_areas():
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute('SELECT id, name, description FROM areas ORDER BY id')
        rows = cur.fetchall()
    conn.close()
    return jsonify([{ 'id': r[0], 'name': r[1], 'description': r[2] } for r in rows])


@areas_bp.route('/', methods=['POST'])
def create_area():
    data = request.get_json()
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute('INSERT INTO areas (code, name, description) VALUES (%s, %s, %s) RETURNING id',
            (data.get('code'), data.get('name'), data.get('description')))
        new_id = cur.fetchone()[0]
    conn.commit()
    conn.close()
    return jsonify({ 'id': new_id, 'message': 'Area created' }), 201


@areas_bp.route('/<int:area_id>', methods=['DELETE'])
def delete_area(area_id):
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute('DELETE FROM areas WHERE id=%s', (area_id,))
    conn.commit()
    conn.close()
    return jsonify({'message': f'Area {area_id} deleted'})