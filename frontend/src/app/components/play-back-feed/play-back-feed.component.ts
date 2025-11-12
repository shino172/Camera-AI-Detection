import { ChangeDetectorRef, Component } from '@angular/core';
import { SafeResourceUrl, DomSanitizer } from '@angular/platform-browser';
import { EventService } from '../../services/event.service';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { toZonedTime } from 'date-fns-tz';
import { LogFileComponent } from "../log-file/log-file.component";
import { AuthService } from '../../services/auth.service';
// import { AlarmComponent } from "../alarm/alarm.component";


@Component({
  selector: 'app-play-back-feed',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './play-back-feed.component.html',
  styleUrl: './play-back-feed.component.css'
})
export class PlayBackFeedComponent {
  /** ====== Thuộc tính chính ====== */
  nvrs: any[] = [];
  selectedNvrId: number | null = null;
  currentCamera: any = null;
  selectedDate: string = new Date().toISOString().split('T')[0];

  cameraVideos: { [key: number]: any[] } = {};
  videoUrls: { [key: string]: SafeResourceUrl } = {};
  selectedSegment: { [key: number]: any | null } = {};

  readonly Math = Math;
  /** ====== Giao diện ====== */
  activeMenu = 'playback';
  gridCols = 4;
  showLayoutMenu = false;
  showPageSizeMenu = false;
  showCameraMenu = false;

  pageSize = 8;
  currentPage = 1;
  totalPages = 1;
  paginatedSegments: any[] = [];

  loading = false;
  currentTimePercent = 0;

  dropdownOpen = { event: false };

  toggleDropdown(section: 'event') {
    this.dropdownOpen[section] = !this.dropdownOpen[section];
  }

  /** ====== Helper ====== */
  hours = Array.from({ length: 13 }, (_, i) => i * 2);
  colorPalette = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6'];

  constructor(
    private eventService: EventService,
    private sanitizer: DomSanitizer,
    private http: HttpClient,
    private cdr: ChangeDetectorRef,
    private authService: AuthService
  ) {}

  ngOnInit() {
    this.loadNvrs();
  }

    get isAdmin(): boolean {
    return this.authService.isAdmin();
  }


  /** 🔹 Load danh sách NVR và camera */
  loadNvrs() {
    this.eventService.getNvrsWithCameras().subscribe({
      next: (res) => (this.nvrs = res),
      error: (err) => console.error('Lỗi tải NVR:', err)
    });
  }

  /** 🔹 Khi chọn NVR */
  selectNvr(id: number) {
    this.selectedNvrId = id;
    const nvr = this.getSelectedNvr();
    if (!nvr?.cameras?.length) return;

    this.cameraVideos = {};
    this.selectedSegment = {};
    this.currentCamera = nvr.cameras[0];

    nvr.cameras.forEach((cam: any) => this.loadCameraSegments(cam.id));

    setTimeout(() => this.onCameraSelect(), 500);
  }

  /** 🔹 Khi chọn camera */
  selectCamera(cam: any) {
    this.currentCamera = cam;
    if (!this.cameraVideos[cam.id]) {
      this.loadCameraSegments(cam.id);
    } else {
      this.onCameraSelect();
    }
  }

  /** 🔹 Load video playback cho 1 camera */
  loadCameraSegments(cameraId: number) {
    this.loading = true;
    this.http
      .get<any[]>(`http://localhost:5000/api/events/camera/${cameraId}?date=${this.selectedDate}`)
      .subscribe({
        next: (segments) => {
          this.cameraVideos[cameraId] = segments || [];
          this.makeVideoUrls(cameraId);
          if (this.currentCamera?.id === cameraId) this.updatePagination();
          this.loading = false;
          this.cdr.detectChanges();
        },
        error: (err) => {
          console.error(`Lỗi tải video camera ${cameraId}:`, err);
          this.loading = false;
        }
      });
  }

  /** 🔹 Tạo URL an toàn */
  makeVideoUrls(cameraId: number) {
    const list = this.cameraVideos[cameraId] || [];
    list.forEach((seg) => {
      if (!seg.video_url) return;
      let url = seg.video_url.startsWith('/static/')
        ? `http://localhost:5000${seg.video_url}`
        : seg.video_url;
      this.videoUrls[`${cameraId}_${seg.id}`] =
        this.sanitizer.bypassSecurityTrustResourceUrl(url);
    });
  }

  /** 🔹 Chọn đoạn phát */
  playSegment(cameraId: number, seg: any) {
    this.selectedSegment[cameraId] = seg;
  }

  /** 🔹 Khi chọn camera — chọn clip đầu tiên */
  onCameraSelect() {
    const camId = this.currentCamera?.id;
    if (!camId) return;
    const segs = this.cameraVideos[camId] || [];
    if (segs.length > 0) {
      this.selectedSegment[camId] = segs[0];
    } else {
      this.selectedSegment[camId] = null;
    }
    this.updatePagination();
  }

  /** 🔹 Cập nhật phân trang clip */
  updatePagination() {
    const segs = this.cameraVideos[this.currentCamera?.id] || [];
    this.totalPages = Math.ceil(segs.length / this.pageSize) || 1;
    const start = (this.currentPage - 1) * this.pageSize;
    const end = start + this.pageSize;
    this.paginatedSegments = segs.slice(start, end);
  }

  /** 🔹 Thay đổi layout (co giãn grid) */
  toggleLayoutMenu() {
    this.showLayoutMenu = !this.showLayoutMenu;
  }

  changeLayout(size: number) {
    this.gridCols = size;
    this.showLayoutMenu = false;
    this.updatePagination();
  }

  /** 🔹 Thay đổi số lượng clip/trang */
  changePageSize(size: number) {
    this.pageSize = size;
    this.currentPage = 1;
    this.showPageSizeMenu = false;
    this.updatePagination();
  }

  /** 🔹 Phân trang clip */
  nextPage() {
    if (this.currentPage < this.totalPages) {
      this.currentPage++;
      this.updatePagination();
    }
  }

  prevPage() {
    if (this.currentPage > 1) {
      this.currentPage--;
      this.updatePagination();
    }
  }

  /** 🔹 Reload tất cả khi đổi ngày */
  reloadAllCameraSegments() {
    const nvr = this.getSelectedNvr();
    if (!nvr?.cameras) return;
    this.cameraVideos = {};
    this.selectedSegment = {};
    nvr.cameras.forEach((cam: any) => this.loadCameraSegments(cam.id));
    if (this.currentCamera) {
      setTimeout(() => this.onCameraSelect(), 800);
    }
  }

  /** ====== Timeline ====== */
  getSegmentPosition(start: string): number {
    const localDate = toZonedTime(start, 'Asia/Ho_Chi_Minh');
    const midnight = new Date(localDate);
    midnight.setHours(0, 0, 0, 0);
    const secondsSinceStart = (localDate.getTime() - midnight.getTime()) / 1000;
    return (secondsSinceStart / (24 * 3600)) * 100;
  }

  getSegmentWidth(start: string, end: string): number {
    const s = new Date(start).getTime();
    const e = new Date(end).getTime();
    const diff = (e - s) / (24 * 3600 * 1000) * 100;
    return Math.max(0.3, diff);
  }

  seekToTime(event: MouseEvent) {
    const bar = event.currentTarget as HTMLElement;
    const rect = bar.getBoundingClientRect();
    const percent = ((event.clientX - rect.left) / rect.width) * 100;
    this.currentTimePercent = percent;

    const totalSeconds = 24 * 3600;
    const selectedSeconds = (percent / 100) * totalSeconds;
    this.seekAllVideos(selectedSeconds);
  }

  seekAllVideos(targetSeconds: number) {
    const nvr = this.getSelectedNvr();
    if (!nvr) return;
    nvr.cameras.forEach((cam: any) => {
      const seg = this.cameraVideos[cam.id]?.find((s) => {
        const start =
          new Date(s.start_time).getHours() * 3600 +
          new Date(s.start_time).getMinutes() * 60;
        const end =
          new Date(s.end_time).getHours() * 3600 +
          new Date(s.end_time).getMinutes() * 60;
        return targetSeconds >= start && targetSeconds <= end;
      });
      if (seg) this.playSegment(cam.id, seg);
    });
    this.cdr.detectChanges();
  }

  /** ====== Tiện ích khác ====== */
  calcDuration(start: string, end: string): string {
    const diff = (new Date(end).getTime() - new Date(start).getTime()) / 1000;
    const m = Math.floor(diff / 60);
    const s = Math.floor(diff % 60);
    return `${m}p ${s}s`;
  }

  getVideoUrl(cameraId: number, segId: string): SafeResourceUrl | null {
    return this.videoUrls[`${cameraId}_${segId}`] || null;
  }

  getSelectedNvr() {
    return this.nvrs.find((n) => n.id === this.selectedNvrId);
  }

  getNvrName(id: number | null): string {
    return this.nvrs.find((n) => n.id === id)?.name || '';
  }

  /** ====== UI điều hướng ====== */
  backToNvrList() {
    this.selectedNvrId = null;
    this.currentCamera = null;
    this.cameraVideos = {};
    this.selectedSegment = {};
  }

  /** Điều hướng menu */
  selectMenu(menu: string) {
    // Nếu không phải admin và bấm vào Event hoặc Alarm → chặn
    if (!this.isAdmin && (menu === 'configuration' || menu === 'alarm')) {
      alert('🚫 Bạn không có quyền truy cập phần này. Chỉ quản trị viên mới được phép thay đổi cấu hình.');
      return;
    }
    this.activeMenu = menu;
  }
  get emptySlots(): number[] {
    const count = Math.max(this.pageSize - this.paginatedSegments.length, 0);
    return Array.from({ length: count });
  }

}
