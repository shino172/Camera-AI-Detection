
import { AfterViewInit, ChangeDetectorRef, Component, Input, OnChanges, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { Camera, CameraService } from '../../services/camera.service';

@Component({
  selector: 'app-video-feed',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './video-feed.component.html',
  styleUrls: ['./video-feed.component.css']
})
export class VideoFeedComponent implements OnChanges, AfterViewInit {
  @Input() areaId!: number;
  streamUrl!: string;

  cameras: Camera[] = [];
  videoUrls: { [key: number]: SafeResourceUrl } = {};
  gridCols = 2;
  pageSize = 4;
  currentPage = 1;
  totalPages = 1;
  fullscreenCamera: Camera | null = null;
  selectedCamera: Camera | null = null;
  showLayoutMenu = false;
  showPageSizeMenu = false;
  constructor(private cameraService: CameraService, private sanitizer: DomSanitizer, private cdr: ChangeDetectorRef) {}

  ngAfterViewInit() {
    this.cdr.detectChanges();
    setTimeout (() => this.cdr.detectChanges(), 0);
  }

  ngOnChanges(): void {
    if (this.areaId) {
      this.loadCameras(this.areaId);
      setTimeout (() => this.cdr.detectChanges(), 0);
    }
  }
  get pagedCameras() {
    const start = (this.currentPage - 1) * this.pageSize;
    return this.cameras.slice(start, start + this.pageSize);
  }
  loadCameras(areaId: number) {
    this.cameraService.getCamerasByArea(areaId).subscribe( cams =>{
      this.cameras = cams;
      this.totalPages = Math.ceil(this.cameras.length / this.pageSize);
      this.videoUrls = {};
      cams.forEach( cam =>{
        this.videoUrls[cam.camera_id] =
        this.sanitizer.bypassSecurityTrustResourceUrl(
          this.cameraService.getVideoFeedUrl(cam.camera_id)
        );
      });
      this.cdr.detectChanges();
    })
  }
  changeLayout(size: number) {
    this.gridCols = size;
    this.cdr.detectChanges();
    setTimeout (() => this.cdr.detectChanges(), 0);
  }

  changePageSize(size: number) {
    this.pageSize = size;
    this.currentPage = 1;
    this.totalPages = Math.ceil(this.cameras.length / this.pageSize);
  }

  prevPage() {
    if (this.currentPage > 1) this.currentPage--;
  }

  nextPage() {
    if (this.currentPage < this.totalPages) this.currentPage++;
  }

  openFullscreen(cam: Camera) {
    this.fullscreenCamera = cam
  }
  selectCamera(cam: Camera) {
    this.fullscreenCamera = cam;
  }

  closeFullScreen() {
    this.fullscreenCamera = null;
  }

  getVideoUrl(cameraId: number): SafeResourceUrl | null {
    return this.videoUrls[cameraId] || null;
  }
  getVideoSizeClass(): string {
    switch (this.gridCols) {
      case 2: return "h-96";
      case 3: return "h-72";
      case 4: return "h-60";
      case 6: return "h-48";
      case 8: return "h-40";
      case 16: return "h-24";
      default: return "h-48";
    }
  }
}
