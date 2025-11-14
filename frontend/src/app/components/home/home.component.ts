
import { Component, NgZone, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { VideoFeedComponent } from "../video-feed/video-feed.component";
import { MatDialog, MatDialogModule } from '@angular/material/dialog';
import { FaceLogComponent } from "../face-log/face-log.component";
import { Router } from '@angular/router';
import { CameraService } from '../../services/camera.service';
import { EventLog, EventService } from '../../services/event.service';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { ConfigService } from '../../services/config.service';
import { FormsModule } from '@angular/forms';
import { AlarmService } from '../../services/alarm.service';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [
    CommonModule,
    VideoFeedComponent,
    MatDialogModule,
    MatSnackBarModule,
    FormsModule
  ],
  templateUrl: './home.component.html',
  styleUrls: ['./home.component.css']
})
export class HomeComponent implements OnInit {
  areas: { id: number; name: string }[] = [];
  selectedArea: any = null;
  events: EventLog[] = [];
  selectedEvent: EventLog | null = null;
  showVideo = false;
  selectedTab: 'live' | 'playback' | 'config' = 'live';
  mediaView: 'image' | 'video' = 'image';

  playbackVideos: EventLog[] = [];
  selectedPlayback: EventLog | null = null;
  selectedVideoUrl: string | null = null;
  safeVideoUrl: SafeResourceUrl | null = null;

  isLoadingPlayBack = false;
  config: any = null;
  areaConfig: any = {};

  soundEnabled = true;
  lastSoundTime = 0;
  SOUND_COOLDOWN = 3000; // ms

  private seenEvents: Map<string, number> = new Map();
  private SEEN_EVENT_TTL = 5 * 1000; // 5s ttl for seen events
  private cleanupIntervalId: any = null;

  audioSmoking = new Audio('assets/sound/tieng_chuong_nhac_nho-www_tiengdong_com.mp3');
  audioWarning = new Audio('assets/sound/tieng_chuong_nhac_nho-www_tiengdong_com.mp3');
  audioGeneral = new Audio('assets/sound/tieng_chuong_nhac_nho-www_tiengdong_com.mp3');

  constructor(
    private cameraService: CameraService,
    private eventService: EventService,
    private dialog: MatDialog,
    private router: Router,
    private sanitizer: DomSanitizer,
    private snackBar: MatSnackBar,
    private configService: ConfigService,
    private alarmService: AlarmService,
    private zone: NgZone,
    private auth: AuthService
  ) {}

  ngOnInit(): void {
    this.loadAreas();
    this.loadEvents();

    this.cleanupIntervalId = setInterval(() => this.cleanupSeenEvents(), 10 * 1000);

    this.eventService.streamEvents().subscribe({
      next: (newE) => {
        const eid = (newE && newE.id) ? String(newE.id) : null;

        if (eid) {
          const t = Date.now();
          const lastSeen = this.seenEvents.get(eid);
          if (lastSeen && (t - lastSeen) < this.SEEN_EVENT_TTL) {
            console.debug('[SSE] Duplicate event skipped (dedupe):', eid, newE.label);
            return;
          }
          this.seenEvents.set(eid, Date.now());
        }

        console.log('[SSE] Received event:', newE);

        this.zone.run(() => {
          if (this.selectedArea && Number(newE.area_id) === Number(this.selectedArea.id)) {
            this.events.unshift(newE);
            if (this.events.length > 100) this.events.pop();
          }

          this.showToast(newE);

          if (this.soundEnabled) {
            this.handleEventSound(newE);
          }
        });
      },
      error: (err) => console.error('[STREAM ERROR]', err),
    });
  }

  ngOnDestroy(): void {
    if (this.cleanupIntervalId) {
      clearInterval(this.cleanupIntervalId);
    }
  }

  private cleanupSeenEvents() {
    const now = Date.now();
    this.seenEvents.forEach((ts, id) => {
      if (now - ts > this.SEEN_EVENT_TTL * 4) {
        this.seenEvents.delete(id);
      }
    });
  }

  // -------------------- TOAST HIỂN THỊ --------------------
  showToast(event: EventLog) {
    let message = '';
    let panelClass = ['toast-default'];

    switch (event.label) {
      case 'smoking':
        message = `🚭 Phát hiện ${event.name || 'nhân viên'} đang hút thuốc tại ${event.area_name || 'khu vực chưa xác định'}!`;
        panelClass = ['toast-warning'];
        break;

      case 'hand_to_mouth':
        message = `⚠️ Hành vi nghi vấn: ${event.name || 'Nhân viên'} đưa tay lên miệng tại ${event.area_name || 'khu vực chưa xác định'}`;
        panelClass = ['toast-info'];
        break;

      case 'person_detection':
        message = `🧍 Phát hiện người tại ${event.area_name || 'khu vực chưa xác định'}`;
        panelClass = ['toast-info'];
        break;

      case 'checkin':
        message = `✅ ${event.name || 'Nhân viên'} đã check-in tại ${event.area_name || 'khu vực'}`;
        panelClass = ['toast-success'];
        break;

      case 'checkout':
        message = `👋 ${event.name || 'Nhân viên'} đã check-out tại ${event.area_name || 'khu vực'}`;
        panelClass = ['toast-normal'];
        break;

      default:
        message = `📢 Sự kiện: ${event.label} tại ${event.area_name || 'khu vực chưa xác định'}`;
    }

    this.snackBar.open(message, 'Đóng', {
      duration: 5000,
      horizontalPosition: 'left',
      verticalPosition: 'bottom',
      panelClass
    });
  }

  handleEventSound(event: EventLog) {
    const now = Date.now();

    if (now - this.lastSoundTime < this.SOUND_COOLDOWN) {
      console.debug('[AUDIO] skipped due to cooldown');
      return;
    }

    const eid = event && event.id ? String(event.id) : null;
    if (eid && this.seenEvents.get(eid) && (now - (this.seenEvents.get(eid) || 0)) < 200) {
    }

    let soundType = '';

    switch (event.label) {
      case 'smoking':
        soundType = 'smoking';
        break;

      case 'hand_to_mouth':
        soundType = 'warning';
        break;

      case 'person_detection':
        soundType = 'person';
        break;

      case 'checkin':
      case 'checkout':
        soundType = 'normal';
        break;

      default:
        soundType = 'general';
        break;
    }

    this.playAlertSound(soundType);
    this.lastSoundTime = now;
  }

  /** -------------------- AREAS -------------------- */
  loadAreas(): void {
    this.configService.getAreas().subscribe({
      next: (res) => {
        this.areas = res || [];

        if (this.areas.length > 0 && !this.selectedArea) {
          this.selectedArea = this.areas[0];
          this.selectArea(this.selectedArea);
        }
      },
      error: (err) => console.error('[AREAS LOAD ERROR]', err),
    });
  }

  selectArea(area: any): void {
    this.selectedArea = area;

    this.configService.getAreaConfig(area.id).subscribe({
      next: (cfg) => {
        this.areaConfig = cfg || { enabled_events: [] };
        if (!this.areaConfig.enabled_events) this.areaConfig.enabled_events = [];
        this.loadEvents(area.id);
      },
      error: (err) => console.error('[AREA CONFIG LOAD ERROR]', err),
    });
  }

  getEventKeys(): string[] {
    if (!this.config || !this.config.events) return [];
    return Object.keys(this.config.events);
  }

  toggleEvent(eventId: unknown): void {
    const id = String(eventId);
    if (!this.areaConfig.enabled_events) this.areaConfig.enabled_events = [];
    const index = this.areaConfig.enabled_events.indexOf(id);
    if (index >= 0) this.areaConfig.enabled_events.splice(index, 1);
    else this.areaConfig.enabled_events.push(id);
  }

  isEventEnabled(eventId: unknown): boolean {
    return this.areaConfig.enabled_events?.includes(String(eventId));
  }

  saveAreaConfig(): void {
    if (!this.selectedArea) return;
    this.configService.saveAreaConfig(this.selectedArea.id, this.areaConfig).subscribe({
      next: () => {
        if (this.config) {
          this.config.areas = this.config.areas || {};
          this.config.areas[this.selectedArea.id] = this.areaConfig;
        }
        alert(`✅ Đã lưu cấu hình khu vực: ${this.selectedArea.name}`);
      },
      error: (err) => console.error('[AREA CONFIG SAVE ERROR]', err),
    });
  }

  /** -------------------- EVENTS -------------------- */
  loadEvents(areaId?: number) {
    const id = areaId || this.selectedArea?.id;
    if (!id) {
      this.events = [];
      return;
    }

    this.eventService.getEvents(100, 0, id).subscribe({
      next: (data) => {
        this.events = data;
      },
      error: (err) => {
        console.error('[EVENTS LOAD ERROR]', err);
        this.events = [];
      }
    });
  }

  openEvent(e: EventLog) {
    this.selectedEvent = e;
    this.showVideo = true;
    this.mediaView = 'image';

    this.safeVideoUrl = e.video_url
      ? this.sanitizer.bypassSecurityTrustResourceUrl(
          e.video_url.startsWith('http') ? e.video_url : `http://localhost:5000${e.video_url}`
        )
      : null;
  }

  closeEvent() {
    this.selectedEvent = null;
    this.showVideo = false;
    this.safeVideoUrl = null;
  }

  convertToLocalTime(utcTime: string): string {
    const d = new Date(utcTime);
    return d.toLocaleString('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh' });
  }

  /** -------------------- PLAYBACK -------------------- */
  selectTab(tab: 'live' | 'playback' | 'config') {
    this.selectedTab = tab;
    if (tab === 'playback') {
      this.loadPlaybackVideos();
    }
  }

  loadPlaybackVideos() {
    this.eventService.getEvents(100, 0).subscribe(events => {
      this.playbackVideos = events.filter(e => e.video_url);
    });
  }

  playVideo(video: EventLog) {
    this.eventService.getPlayback(video.id).subscribe({
      next: (res) => {
        const fullUrl = res.playback_url.startsWith('http')
          ? res.playback_url
          : `http://localhost:5000${res.playback_url}`;
        this.safeVideoUrl = this.sanitizer.bypassSecurityTrustResourceUrl(fullUrl);
        this.selectedPlayback = { ...video, video_url: fullUrl };
      },
      error: (err) => {
        console.error('Playback error:', err);
        alert('Không tìm thấy video playback!');
      }
    });
  }

  closePlayback() {
    this.selectedPlayback = null;
  }

  loadConfig(): void {
    this.configService.getConfig().subscribe({
      next: (cfg) => {
        this.config = cfg || { system: {}, events: {}, areas: {} };
        if (!this.config.system) this.config.system = {};
        if (!this.config.events) this.config.events = {};
        if (!this.config.areas) this.config.areas = {};
      },
      error: (err) => console.error('[CONFIG LOAD ERROR]', err),
    });
  }

  saveConfig(): void {
    if (!this.config) return;
    this.configService.saveConfig(this.config).subscribe({
      next: () => alert('✅ Đã lưu cấu hình hệ thống!'),
      error: (err) => console.error('[CONFIG SAVE ERROR]', err),
    });
  }

  /** -------------------- MEDIA HANDLING -------------------- */
  getImageUrl(e: EventLog): string {
    if (!e.image_url) return 'assets/no-image.jpg';
    if (e.image_url.startsWith('/static/')) {
      return `http://localhost:5000${e.image_url}`;
    }
    return e.image_url;
  }

  playAlertSound(type: string) {
    let audio: HTMLAudioElement;

    switch (type) {
      case 'smoking':
        audio = this.audioSmoking;
        break;

      case 'hand_to_mouth':
      case 'person_detection':
        audio = this.audioWarning;
        break;

      case 'checkin':
      case 'checkout':
        audio = this.audioWarning;
        break;

      case 'scan_qr':
          audio = this.audioWarning;
          break;

      default:
        audio = this.audioGeneral;
        break;
    }

    // reset và play
    audio.currentTime = 0;
    audio.play()
      .then(() => console.log('[AUDIO] Played:', type))
      .catch(err => console.warn('[AUDIO ERROR]', err));
  }

  getRoleLabel(): string {
    if (this.auth.isAdmin()) return 'Admin';
    const permissions = this.auth.getPermissions();
    if (permissions.length === 0) return 'User';
    if (permissions.includes('VIEW_PLAYBACKLOG')) return 'Playback User';
    if (permissions.includes('EVENT_ALARM')) return 'Event Operator';
    if (permissions.includes('MANAGE_EMPLOYEES')) return 'Event Operator';
    if (permissions.includes('MANAGE_SYSTEM')) return 'System Manager';

    return 'User';
  }

}
