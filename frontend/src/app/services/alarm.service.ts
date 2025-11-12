import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

@Injectable({ providedIn: 'root' })
export class AlarmService {
  private api = 'http://localhost:5000/api';

  constructor(private http: HttpClient) {}

  /** 🔹 Lấy toàn bộ config theo khu vực */
  getAreaConfig(areaId: number): Observable<any> {
    return this.http.get(`${this.api}/config/areas/${areaId}`);
  }

  /** 🔹 Lưu cấu hình khu vực */
  // saveAreaConfig(areaId: number, data: any): Observable<any> {
  //   return this.http.post(`${this.api}/config/areas/${areaId}`, data);
  // }
  saveAreaConfig(areaId: number, data: any): Observable<any> {
    return this.http.put(`${this.api}/config/areas/${areaId}`, data);
  }

  /** 🔹 Phát âm thanh cảnh báo (nếu linkage bật audibleWarning) */
  playAudioAlarm(): Observable<any> {
    return this.http.post(`${this.api}/alarm/play-audio`, {});
  }

}
