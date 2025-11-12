import { Injectable, NgZone } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { map } from 'rxjs/operators';
import * as XLSX from 'xlsx';

export interface EventLog {
  id: string;
  person_id: string;
  camera_id: number;
  time: string;
  label: string;
  name?: string;
  image_url?: string | null;
  video_url?: string | null;
  playback_url?: string | null;
  area_name?: string;
  area_id?: number;
}

@Injectable({ providedIn: 'root' })
export class EventService {
  private apiUrl = 'http://localhost:5000';

  constructor(private http: HttpClient, private zone: NgZone) {}

  /** 📋 Danh sách sự kiện */
  getEvents(limit: number = 500, offset: number = 0, areaId?: number): Observable<EventLog[]> {
    let url = `${this.apiUrl}/events?limit=${limit}&offset=${offset}`;
    if (areaId) {
      url += `&area_id=${areaId}`;
    }

    return this.http
      .get<EventLog[]>(url)
      .pipe(
        map(events =>
          events.map(e => ({
            ...e,
            image_url: this.fixStaticPath(e.image_url),
            video_url: this.fixStaticPath(e.video_url),
            playback_url: this.fixStaticPath(e.playback_url)
          }))
        )
      );
  }


  /** 🔢 Đếm số lượng sự kiện */
  getEventsCount(): Observable<{ count: number }> {
    return this.http.get<{ count: number }>(`${this.apiUrl}/events/count`);
  }

  /** 📡 Stream sự kiện realtime qua SSE */
  streamEvents(): Observable<EventLog> {
    return new Observable(observer => {
      const es = new EventSource(`${this.apiUrl}/events/stream`);
      es.onmessage = event => {
        try {
          const data = JSON.parse(event.data);
          this.zone.run(() => observer.next(data));
        } catch (e) {
          console.error('❌ Parse SSE error:', e);
        }
      };
      es.onerror = err => {
        console.error('🚫 SSE connection error:', err);
        es.close();
      };
      return () => es.close();
    });
  }

  /** 🗑️ Xóa 1 sự kiện */
  deleteEvent(eventId: string): Observable<any> {
    return this.http.delete(`${this.apiUrl}/events/${eventId}`);
  }

  /** 🧹 Xóa toàn bộ sự kiện */
  deleteAllEvents(): Observable<any> {
    return this.http.delete(`${this.apiUrl}/events/deleteall`);
  }

  /** 🖥️ Lấy danh sách NVR */
  getNvrs(): Observable<any[]> {
    return this.http.get<any[]>(`${this.apiUrl}/api/nvrs`);
  }

  /** 📼 Lấy playback video theo event ID */
  getPlayback(eventId: string): Observable<{ playback_url: string }> {
    return this.http.get<{ playback_url: string }>(
      `${this.apiUrl}/api/playback/${eventId}`
    );
  }

  /** 🧭 Lấy danh sách NVR kèm camera */
  getNvrsWithCameras(): Observable<any[]> {
    return this.http.get<any[]>(`${this.apiUrl}/api/nvrs-with-cameras`);
  }

  /** 🔧 Chuẩn hóa đường dẫn ảnh/video */
  private fixStaticPath(url?: string | null): string | null {
    if (!url) return null;
    if (url.startsWith('/static/')) {
      return `${this.apiUrl}${url}`;
    }
    return url;
  }
  /** 🎞️ Lấy các đoạn playback theo camera & ngày */
  getPlaybackSegments(cameraId: number, date: string): Observable<any[]> {
    return this.http
      .get<any[]>(`${this.apiUrl}/api/playback_segments/${cameraId}?date=${date}`)
      .pipe(
        map(segments =>
          segments.map(seg => ({
            ...seg,
            video_url: this.fixStaticPath(seg.video_url)
          }))
        )
      );
    }
  /** 📤 Xuất log sự kiện ra file Excel */
  exportEventsToExcel(events: EventLog[], filename: string = 'logs.xlsx') {
    const data = events.map(e => ({
      ID: e.id,
      Camera: e.camera_id,
      Label: e.label,
      Time: e.time,
      Area: e.area_name || '',
    }));

    const worksheet = XLSX.utils.json_to_sheet(data);
    const workbook = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(workbook, worksheet, 'Logs');
    XLSX.writeFile(workbook, filename);
  }
}
