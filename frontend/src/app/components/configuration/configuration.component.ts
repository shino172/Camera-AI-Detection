import { Component, ElementRef, OnInit, ViewChild } from '@angular/core';
import { ConfigService } from '../../services/config.service';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClientModule } from '@angular/common/http';
import { MatSnackBar } from '@angular/material/snack-bar';
import { CameraService } from '../../services/camera.service';
import { FaceService } from '../../services/face.service';

@Component({
  selector: 'app-configuration',
  standalone: true,
  imports: [CommonModule, FormsModule, HttpClientModule],
  templateUrl: './configuration.component.html',
  styleUrls: ['./configuration.component.css']
})
export class ConfigurationComponent implements OnInit {
  config: any = null;
  areas: any[] = [];
  selectedArea: any = null;
  areaConfig: any = {};
  cameras: any[] = [];
  selectedCameraId: string | number | null = null;

  autoLearn = false;

  constructor(
    private configService: ConfigService,
    private snackBar: MatSnackBar,
    private cameraService: CameraService,
    private faceService: FaceService

  ) {}

  ngOnInit(): void {
    this.loadConfig();
    this.loadAreas();
    this.loadAutoLearn();
  }

  loadConfig(): void {
    this.configService.getConfig().subscribe({
      next: (cfg) => {
        // ✅ Luôn đảm bảo có cấu trúc chuẩn
        this.config = cfg || { system: {}, events: {}, areas: {} };
        if (!this.config.events) {
          this.config.events = {
            face_recognition: true,
            smoking: true,
            violence: false,
            checkincheckout: true,
          };
        }
      },
      error: (err) => console.error('[CONFIG LOAD ERROR]', err),
    });
  }


  loadAreas(): void {
    this.configService.getAreas().subscribe({
      next: (res) => (this.areas = res || []),
      error: (err) => console.error('[AREAS LOAD ERROR]', err),
    });
  }

  getEventKeys(): string[] {
    return this.config?.events ? Object.keys(this.config.events) : [];
  }

  isEventEnabled(eventId: string): boolean {
    return this.areaConfig.enabled_events?.includes(eventId);
  }

  toggleEvent(eventId: string): void {
    const enabled = this.isEventEnabled(eventId);
    if (enabled) {
      this.areaConfig.enabled_events = this.areaConfig.enabled_events.filter((ev: string) => ev !== eventId);
    } else {
      this.areaConfig.enabled_events.push(eventId);
    }

    if(eventId==='face_recognition'){
      const newState = !enabled;
      this.faceService.toggleAutoLearn(newState).subscribe({
        next:()=>{
          this.snackBar.open(`🤖 Tự học gương mặt ${newState ? 'đã bật' : 'đã tắt'}`, 'Đóng', { duration: 2000 });
        },
        error:(err)=>console.error('[AUTOLEARN TOGGLE ERROR]',err),
      })
    }
    this.snackBar.open(`✅ ${enabled ? 'Tắt' : 'Bật'} sự kiện '${eventId}'`, 'Đóng', {
      duration: 2000,
      horizontalPosition: 'left',
      verticalPosition: 'bottom',
    });
  }

  /** 🎥 LIVE CAMERA + DRAW AREA */
  @ViewChild('drawCanvas') drawCanvas!: ElementRef<HTMLCanvasElement>;
  liveUrl: string | null = null;
  ctx!: CanvasRenderingContext2D | null;
  drawing = false;
  startX = 0;
  startY = 0;
  rects: { x: number; y: number; w: number; h: number }[] = [];
  currentRect: any = null;

  selectArea(area: any) {
    this.selectedArea = area;

    this.configService.getAreaConfig(area.id).subscribe({
      next: (cfg) => {
        this.areaConfig = cfg || {};
        if (!this.areaConfig.enabled_events) this.areaConfig.enabled_events = [];
        if (!this.areaConfig.cameras) this.areaConfig.cameras = {};
        if (!this.areaConfig.draw_areas) this.areaConfig.draw_areas = [];

        setTimeout(() => this.initCanvas(), 200);
      },
      error: (err) => console.error('[LOAD AREA CONFIG ERROR]', err),
    });

    this.cameraService.getCamerasByArea(area.id).subscribe({
      next: (cams) => {
        this.cameras = cams || [];
        if (this.cameras.length > 0) {
          this.selectedCameraId = this.cameras[0].camera_id;
          this.updateLiveUrl();
        } else {
          this.liveUrl = null;
        }
      },
      error: (err) => console.error('[LOAD CAMERAS ERROR]', err),
    });
  }

  // selectArea(area: any) {
  //   this.selectedArea = area;

  //   // Load cấu hình khu vực
  //   this.configService.getAreaConfig(area.id).subscribe({
  //     next: (cfg) => {
  //       this.areaConfig = cfg || { enabled_events: [], draw_areas: [] };
  //       if (!this.areaConfig.enabled_events) this.areaConfig.enabled_events = [];
  //       if (!this.areaConfig.draw_areas) this.areaConfig.draw_areas = [];
  //       setTimeout(() => this.initCanvas(), 200);
  //     },
  //     error: (err) => console.error('[LOAD AREA CONFIG ERROR]', err),
  //   });

  //   // 🟢 Load danh sách camera theo khu vực
  //   this.cameraService.getCamerasByArea(area.id).subscribe({
  //     next: (cams) => {
  //       this.cameras = cams || [];
  //       if (this.cameras.length > 0) {
  //         this.selectedCameraId = this.cameras[0].camera_id;
  //         this.updateLiveUrl();
  //       } else {
  //         this.liveUrl = null;
  //       }
  //     },
  //     error: (err) => console.error('[LOAD CAMERAS ERROR]', err),
  //   });
  // }
  onCameraChange() {
    this.updateLiveUrl();

    if (!this.selectedArea || !this.areaConfig) return;
    const camId = Number(this.selectedCameraId);
    const camConfig = this.areaConfig.cameras?.[camId];

    // Nếu có vùng lưu trong camera → hiển thị
    if (camConfig?.draw_areas?.length > 0) {
      const canvas = this.drawCanvas?.nativeElement;
      if (canvas) {
        this.rects = camConfig.draw_areas.map((r: any) => ({
          x: r.x * canvas.width,
          y: r.y * canvas.height,
          w: r.w * canvas.width,
          h: r.h * canvas.height,
        }));
        this.drawAllRects();
      }
    } else {
      // ✅ Nếu chưa có → full màn hình
      const canvas = this.drawCanvas?.nativeElement;
      if (canvas) {
        this.rects = [{ x: 0, y: 0, w: canvas.width, h: canvas.height }];
        this.drawAllRects();
      }
    }
  }

  // onCameraChange() {
  //   this.updateLiveUrl();

  //   if (!this.selectedArea || !this.areaConfig) return;
  //   const camId = Number(this.selectedCameraId);
  //   const camConfig = this.areaConfig.cameras?.[camId];

  //   if (camConfig?.draw_areas?.length > 0) {
  //     const canvas = this.drawCanvas?.nativeElement;
  //     if (canvas) {
  //       this.rects = camConfig.draw_areas.map((r: any) => ({
  //         x: r.x * canvas.width,
  //         y: r.y * canvas.height,
  //         w: r.w * canvas.width,
  //         h: r.h * canvas.height,
  //       }));
  //       this.drawAllRects();
  //     }
  //   } else {
  //     this.rects = [];
  //     this.clearCanvas();
  //   }
  // }

  // Cập nhật live stream camera
  updateLiveUrl() {
    if (this.selectedCameraId) {
      // ép kiểu sang number
      const camId = Number(this.selectedCameraId);
      this.liveUrl = this.cameraService.getVideoFeedUrl(camId);
      setTimeout(() => this.initCanvas(), 500);
    } else {
      this.liveUrl = null;
    }
  }

  initCanvas() {
    const canvas = this.drawCanvas?.nativeElement;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    this.ctx = ctx;

    // Chỉ resize nếu chưa có width/height (lần đầu)
    if (canvas.width === 0 || canvas.height === 0) {
      canvas.width = canvas.clientWidth;
      canvas.height = canvas.clientHeight;
    }

    this.drawAllRects();
  }

  startDraw(event: MouseEvent) {
    if (!this.ctx) return;
    this.drawing = true;
    const canvas = this.drawCanvas.nativeElement;
    const rect = canvas.getBoundingClientRect();

    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;

    this.startX = (event.clientX - rect.left) * scaleX;
    this.startY = (event.clientY - rect.top) * scaleY;
  }

  drawingArea(event: MouseEvent) {
    if (!this.drawing || !this.ctx) return;
    const canvas = this.drawCanvas.nativeElement;
    const rect = canvas.getBoundingClientRect();

    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;

    const x = (event.clientX - rect.left) * scaleX;
    const y = (event.clientY - rect.top) * scaleY;
    const w = x - this.startX;
    const h = y - this.startY;

    this.clearCanvas();
    this.drawAllRects();

    this.ctx.strokeStyle = 'red';
    this.ctx.lineWidth = 2;
    this.ctx.fillStyle = 'rgba(255,0,0,0.3)';
    this.ctx.fillRect(this.startX, this.startY, w, h);
    this.ctx.strokeRect(this.startX, this.startY, w, h);
    this.currentRect = { x: this.startX, y: this.startY, w, h };
  }

  stopDraw() {
    if (!this.drawing) return;
    this.drawing = false;
    if (this.currentRect) {
      this.rects.push(this.currentRect);
      this.currentRect = null;
      this.drawAllRects();
    }
  }

  drawAllRects() {
    if (!this.ctx) return;
    const canvas = this.drawCanvas.nativeElement;
    this.ctx.clearRect(0, 0, canvas.width, canvas.height);
    for (const r of this.rects) {
      this.ctx.strokeStyle = 'red';
      this.ctx.lineWidth = 2;
      this.ctx.fillStyle = 'rgba(255,0,0,0.3)';
      this.ctx.fillRect(r.x, r.y, r.w, r.h);
      this.ctx.strokeRect(r.x, r.y, r.w, r.h);
    }
  }

  clearDraw() {
    this.rects = [];
    this.clearCanvas();
  }

  clearCanvas() {
    if (!this.ctx) return;
    const canvas = this.drawCanvas.nativeElement;
    this.ctx.clearRect(0, 0, canvas.width, canvas.height);
  }

  saveAreaConfig(): void {
    if (!this.selectedArea) return;
    const canvas = this.drawCanvas?.nativeElement;
    if (!canvas) return;

    const camId = Number(this.selectedCameraId);
    let normalized = this.rects.map((r) => ({
      x: r.x / canvas.width,
      y: r.y / canvas.height,
      w: r.w / canvas.width,
      h: r.h / canvas.height,
    }));

    // ✅ Nếu không vẽ gì → full screen
    if (normalized.length === 0) normalized = [{ x: 0, y: 0, w: 1, h: 1 }];

    if (!this.areaConfig.cameras) this.areaConfig.cameras = {};
    this.areaConfig.cameras[camId] = {
      ...(this.areaConfig.cameras[camId] || {}),
      draw_areas: normalized,
    };

    const dataToSave = {
      ...this.areaConfig,
      draw_areas: normalized, // lưu chung để dễ load
    };

    this.configService.saveAreaConfig(this.selectedArea.id, dataToSave).subscribe({
      next: () => {
        this.snackBar.open('✅ Đã lưu cấu hình khu vực (sự kiện + vùng vẽ)', 'Đóng', {
          duration: 3000,
        });
      },
      error: (err) => console.error('[SAVE AREA CONFIG ERROR]', err),
    });
  }

  // saveAreaConfig(): void {
  // if (!this.selectedArea) return;
  // const canvas = this.drawCanvas?.nativeElement;
  // if (!canvas) return;

  // const camId = Number(this.selectedCameraId)
  //   let normalized = this.rects.map(r => ({
  //     x: r.x / canvas.width,
  //     y: r.y / canvas.height,
  //     w: r.w / canvas.width,
  //     h: r.h / canvas.height
  //   }));
  //   if (normalized.length === 0) normalized = [{ x: 0, y: 0, w: 1, h: 1 }];
  //   if (!this.areaConfig.cameras) this.areaConfig.cameras = {};
  //   this.areaConfig.cameras[camId] = this.areaConfig.cameras[camId] || {};
  //   this.areaConfig.cameras[camId].draw_areas = normalized;

  //   const dataToSave = {
  //     ...this.areaConfig,
  //     draw_areas: normalized
  //   };

  //   this.configService.saveAreaConfig(this.selectedArea.id, dataToSave).subscribe({
  //     next: () => {
  //       this.snackBar.open('✅ Đã lưu cấu hình khu vực (gồm vùng vẽ)', 'Đóng', {
  //         duration: 3000,
  //       });

  //       // 🔁 Áp dụng realtime
  //       // this.configService.applyAreaConfig(this.selectedArea.id, dataToSave).subscribe({
  //       //   next: () => this.snackBar.open('⚡ Cấu hình đã áp dụng ngay', 'Đóng', { duration: 2000 }),
  //       //   error: err => console.error('[APPLY CONFIG ERROR]', err),
  //       // });
  //     },
  //     error: (err) => console.error('[SAVE AREA CONFIG ERROR]', err),
  //   });
  // }

  onImageLoaded() {
    const canvas = this.drawCanvas?.nativeElement;
    if (!canvas) return;

    const img = canvas.parentElement?.querySelector('img') as HTMLImageElement;
    if (img) {
      canvas.width = img.clientWidth;
      canvas.height = img.clientHeight;
    } else {
      canvas.width = canvas.clientWidth;
      canvas.height = canvas.clientHeight;
    }

    const camId = Number(this.selectedCameraId);
    const camConfig = this.areaConfig?.cameras?.[camId];

    if (camConfig?.draw_areas?.length > 0) {
      this.rects = camConfig.draw_areas.map((r: any) => ({
        x: r.x * canvas.width,
        y: r.y * canvas.height,
        w: r.w * canvas.width,
        h: r.h * canvas.height,
      }));
    } else {
      // ✅ full màn hình mặc định
      this.rects = [{ x: 0, y: 0, w: canvas.width, h: canvas.height }];
    }

    this.initCanvas();
  }

  // onImageLoaded() {
  //   const canvas = this.drawCanvas?.nativeElement;
  //   if (!canvas) return;

  //   // Lấy kích thước hiển thị thực của ảnh
  //   const img = canvas.parentElement?.querySelector('img') as HTMLImageElement;
  //   if (img) {
  //     canvas.width = img.clientWidth;
  //     canvas.height = img.clientHeight;
  //   } else {
  //     canvas.width = canvas.clientWidth;
  //     canvas.height = canvas.clientHeight;
  //   }

  //   // Sau khi canvas được resize chuẩn → convert normalized → pixel để hiển thị lại vùng đã vẽ
  //   if (this.areaConfig?.draw_areas?.length > 0) {
  //     this.rects = this.areaConfig.draw_areas.map((r: any) => ({
  //       x: r.x * canvas.width,
  //       y: r.y * canvas.height,
  //       w: r.w * canvas.width,
  //       h: r.h * canvas.height
  //     }));
  //   }
  //   this.initCanvas();
  // }
  /** 🔹 Lấy trạng thái tự học ban đầu */
  loadAutoLearn(): void {
    this.faceService.getAutoLearnStatus().subscribe({
      next: (res) => (this.autoLearn = res.auto_learn),
      error: (err) => console.error('[AUTOLEARN STATUS ERROR]', err),
    });
  }

  /** 🔹 Toggle bật/tắt tự học */
  toggleAutoLearn(): void {
    const newState = !this.autoLearn;
    this.faceService.toggleAutoLearn(newState).subscribe({
      next: () => {
        this.autoLearn = newState;
        this.snackBar.open(
          `🤖 Tự học gương mặt ${newState ? 'đã bật' : 'đã tắt'}`,
          'Đóng',
          { duration: 2000 }
        );
      },
      error: (err) => console.error('[AUTOLEARN TOGGLE ERROR]', err),
    });
  }

}
