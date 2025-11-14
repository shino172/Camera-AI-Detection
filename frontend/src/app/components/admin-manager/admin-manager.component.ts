import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';

@Component({
  selector: 'app-admin-manager',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './admin-manager.component.html',
  styleUrl: './admin-manager.component.css'
})
export class AdminManagerComponent implements OnInit {
  activeTab: 'area' | 'nvr' | 'camera' = 'area';
  areaApi = 'http://localhost:5000/areas';
  nvrApi = 'http://localhost:5000/api/nvrs';
  cameraApi = 'http://localhost:5000/api/cameras';

  areas: any[] = [];
  nvrs: any[] = [];
  cameras: any[] = [];

  newArea = { code: '', name: '', description: '' };
  editArea: any = null;

  newNvr = { name: '', ip_address: '', port: 554, username: '', password: '' };
  editNvr: any = null;

  newCamera = { name: '', nvr_id: null, channel: null, area_id: null, rtsp_url: '', location: '', status: 'active' };
  editCamera: any = null;
  editingId: number | null =null;

  constructor(private http: HttpClient) {}

  ngOnInit() {
    this.loadAreas();
    this.loadNvrs();
    this.loadCameras();
  }

  // ---------------- AREA ----------------
  loadAreas() {
    this.http.get<any[]>(this.areaApi).subscribe(res => this.areas = res);
  }

  addArea() {
    this.http.post(this.areaApi, this.newArea).subscribe(() => {
      this.loadAreas();
      this.newArea = { code: '', name: '', description: '' };
    });
  }

  startEditArea(a: any) {
    this.editArea = { ...a };
  }

  saveEditArea() {
    this.http.put(`${this.areaApi}/${this.editArea.id}`, this.editArea).subscribe(() => {
      this.editArea = null;
      this.loadAreas();
    });
  }

  deleteArea(id: number) {
    if (confirm('Xóa khu vực này?')) {
      this.http.delete(`${this.areaApi}/${id}`).subscribe(() => this.loadAreas());
    }
  }
  cancelEditArea() {
    this.editArea = null;
  }

  // ---------------- NVR ----------------
  loadNvrs() {
    this.http.get<any[]>(this.nvrApi).subscribe(res => this.nvrs = res);
  }

  addNvr() {
    this.http.post(this.nvrApi, this.newNvr).subscribe(() => {
      this.loadNvrs();
      this.newNvr = { name: '', ip_address: '', port: 554, username: '', password: '' };
    });
  }

  startEditNvr(n: any) {
    this.editNvr = { ...n };
  }

  saveEditNvr() {
    this.http.put(`${this.nvrApi}/${this.editNvr.id}`, this.editNvr).subscribe(() => {
      this.editNvr = null;
      this.loadNvrs();
    });
  }

  deleteNvr(id: number) {
    if (confirm('Xóa NVR này?')) {
      this.http.delete(`${this.nvrApi}/${id}`).subscribe(() => this.loadNvrs());
    }
  }
  cancelEditNvr() {
    this.editNvr = null;
  }

  // ---------------- CAMERA ----------------
  loadCameras() {
    this.http.get<any[]>(this.cameraApi).subscribe(res => this.cameras = res);
  }

  addCamera() {
    this.http.post(this.cameraApi, this.newCamera).subscribe(() => {
      this.loadCameras();
      this.newCamera = { name: '', nvr_id: null, channel: null, area_id: null, rtsp_url: '', location: '', status: 'active' };
    });
  }

  startEditCamera(c: any) {
    this.editingId = c.id || c.camera_id ;
    this.editCamera ={ ...c}
  }

  saveEditCamera() {
    if (!this.editingId) return;
    this.http.put(`${this.cameraApi}/${this.editingId}`, this.editCamera).subscribe(() => {
      this.editingId = null;
      this.editCamera = {};
      this.loadCameras();
    });
  }

  deleteCamera(id: number) {
    if (!id) return alert('Camera ID không hợp lệ!');
    if (confirm('Xóa camera này?')) {
      this.http.delete(`${this.cameraApi}/${id}`).subscribe(() => this.loadCameras());
    }
  }

  cancelEditCamera() {
    this.editingId = null;
    this.editCamera = {};
  }
  
  toggleCameraStatus(id: number, status: 'active' | 'inactive') {
    console.log("Toggle camera:", id, status);

    this.http.put(`${this.cameraApi}/${id}/status`, { status }).subscribe({
      next: () => {
        this.loadCameras();
        console.log("Camera status updated:", status);
      },
      error: (err) => {
        console.error('[TOGGLE CAMERA STATUS ERROR]', err);
        alert('❌ Không thể thay đổi trạng thái camera!');
      },
    });
  }

}
