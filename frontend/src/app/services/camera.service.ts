import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface Area {
  id: number;
  name: string;
  description?: string;
}

export interface Camera {
  camera_id: number;
  name: string;
  rtsp_url: string;
  location?: string;
  status?: string;
  triggerRecording?: boolean;
}

@Injectable({ providedIn: 'root' })
export class CameraService {
  private apiUrl = 'http://localhost:5000';
  // private apiUrl = '';

  constructor(private http: HttpClient) {}

  /** Lấy danh sách khu vực */
  getAreas(): Observable<Area[]> {
    return this.http.get<Area[]>(`${this.apiUrl}/areas`);
  }

  /** Lấy camera theo khu vực (theo area_id) */
  getCamerasByArea(areaId: number): Observable<Camera[]> {
    return this.http.get<Camera[]>(`${this.apiUrl}/areas/${areaId}/cameras`);
  }

  /** Lấy tất cả camera */
  getAllCameras(): Observable<Camera[]> {
    return this.http.get<Camera[]>(`${this.apiUrl}/cameras`);
  }

  /** Chọn camera (giữ lại để mở rộng) */
  selectCamera(cameraId: number): Observable<any> {
    return this.http.post(`${this.apiUrl}/cameras/select/${cameraId}`, {});
  }

  /** Lấy URL stream */
  getVideoFeedUrl(cameraId: number): string {
    return `${this.apiUrl}/video_feed/${cameraId}`;
  }

  // camera.service.ts
  saveTriggerRecording(cameraIds: number[]): Observable<any> {
    return this.http.post(`${this.apiUrl}/alarm-config/trigger-recording`, { camera_ids: cameraIds });
  }

}
