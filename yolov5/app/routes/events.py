from flask import Blueprint, jsonify, Response
import json, time
from queue import Empty
from ..db import get_conn
from .. import RUNTIME


events_bp = Blueprint('events', __name__)


@events_bp.route('/', methods=['GET'])
def list_events():
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute('SELECT id::text, label, time, image_url, video_url FROM events ORDER BY time DESC LIMIT 100')
    rows = cur.fetchall()
    conn.close()
    return jsonify([{ 'id': r[0], 'label': r[1], 'time': r[2].isoformat(), 'image_url': r[3], 'video_url': r[4] } for r in rows])


@events_bp.route('/stream')
def stream_events():
    q = RUNTIME['event_broadcast_queue']


    def generate():
        while True:
            try:
                event = q.get(timeout=2)
                yield f"data: {json.dumps(event)}\n\n"
            except Empty:
                yield ':\n\n'
                time.sleep(1)

    return Response(generate(), mimetype='text/event-stream')