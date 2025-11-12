import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

@Injectable({ providedIn: 'root' })
export class ConfigService {
  
  private baseUrl = 'http://localhost:5000/api/config';

  getCameraConfig(cameraId: number): Observable<any> {
    return this.http.get(`/api/config/${cameraId}`);
  }

  saveCameraConfig(data: any): Observable<any> {
    return this.http.post(`/api/config`, data);
  }

  constructor(private http: HttpClient) {}

  /** 🧩 Toàn bộ cấu hình hệ thống */
  getConfig(): Observable<any> {
    return this.http.get(`${this.baseUrl}`);
  }

  saveConfig(cfg: any): Observable<any> {
    return this.http.post(`${this.baseUrl}`, cfg);
  }

  /** 🗺️ Danh sách khu vực */
  getAreas(): Observable<any[]> {
    return this.http.get<any[]>(`http://localhost:5000/areas`);
  }

  /** ⚙️ Cấu hình từng khu vực */
  getAreaConfig(areaId: number): Observable<any> {
    return this.http.get(`${this.baseUrl}/areas/${areaId}`);
  }

  saveAreaConfig(areaId: number, cfg: any): Observable<any> {
    return this.http.put(`${this.baseUrl}/areas/${areaId}`, cfg);
  }

  applyAreaConfig(areaId: number, cfg: any): Observable<any> {
    return this.http.post(`${this.baseUrl}/areas/${areaId}/apply`, cfg);
  }

}
