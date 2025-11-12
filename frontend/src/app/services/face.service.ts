import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface FaceEntry {
  person_id: number;
  employee_id?: number;
  name: string;
  image?: string;
  ts?: number;
  avatar?: string
}

export interface PendingFace {
  id: string;
  person_id?: string;
  bbox: [number, number, number, number];
  image_b64: string;
  ts: number;
}

@Injectable({ providedIn: 'root' })
export class FaceService {
  private apiUrl = 'http://localhost:5000';
  // private apiUrl = '';

  constructor(private http: HttpClient) {}

  assignFace(faceId: string, name: string): Observable<any>{
    return this.http.post(`${this.apiUrl}/faces/assign`, {face_id: faceId, name})
  }
  getPerson(): Observable<any[]>{
    return this.http.get<any[]>(`${this.apiUrl}/persons`);
  }
  getFaces(): Observable<FaceEntry[]> {
    return this.http.get<FaceEntry[]>(`${this.apiUrl}/faces`);
  }

  manualAddPerson(name: string, imageBase64?: string): Observable<any> {
    return this.http.post(`${this.apiUrl}/persons/manual_add`, { name, image: imageBase64 });
  }

  updateFaceName(faceId: number, newName: string): Observable<any> {
    return this.http.put(`${this.apiUrl}/faces/${faceId}`, { name: newName });
  }
  updatePerson(personId: number, data: any): Observable<any> {
    return this.http.put(`${this.apiUrl}/persons/${personId}`, data);
  }

  getPendingFaces(): Observable<PendingFace[]> {
    return this.http.get<PendingFace[]>(`${this.apiUrl}/pending_faces`);
  }

  assignPendingFace(pendingId: string, name: string): Observable<any> {
    return this.http.post(`${this.apiUrl}/pending_faces/assign`, { pending_id:pendingId, name });
  }
  deletePendingFace(face_id: string): Observable<any> {
    return this.http.delete(`${this.apiUrl}/pending_faces/${face_id}`);
  }
  deleteFace(faceId: number): Observable<any> {
    return this.http.delete(`${this.apiUrl}/faces/${faceId}`);
  }
  deletePerson(personId: number): Observable<any> {
    return this.http.delete(`${this.apiUrl}/persons/${personId}`);
  }
  getVideoFeedUrl(): string {
    return `${this.apiUrl}/video_feed`;
  }
  setAvatar(personId: number, image: string): Observable<any> {
    return this.http.put(`${this.apiUrl}/persons/${personId}/avatar`, { image });
  }
  updateAvatar(personId: number, image: string): Observable<any> {
    return this.http.put(`${this.apiUrl}/persons/${personId}/avatar`, { image });
  }

  uploadAvatar(imageBase64: string) {
    return this.http.post<any>(`${this.apiUrl}/upload/avatar`, { image: imageBase64 });
  }

  getAutoLearnStatus(): Observable<{ auto_learn: boolean }> {
    return this.http.get<{ auto_learn: boolean }>(`${this.apiUrl}/auto_learn`);
  }

  // Bật/tắt chế độ tự học
  toggleAutoLearn(enabled: boolean): Observable<any> {
    return this.http.post(`${this.apiUrl}/auto_learn`, { enabled });
  }
}
