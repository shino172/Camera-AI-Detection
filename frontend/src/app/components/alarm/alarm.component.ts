import { Component, OnInit } from '@angular/core';
import { CameraService, Area, Camera } from '../../services/camera.service';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';
import { AlarmService } from '../../services/alarm.service';

interface EventSchedule {
  event: string;
  start: string;
  end: string;
  enabled: boolean;
  allowed: boolean;
}

@Component({
  selector: 'app-alarm',
  standalone: true,
  imports: [FormsModule, CommonModule],
  templateUrl: './alarm.component.html',
  styleUrls: ['./alarm.component.css'],
})
export class AlarmComponent implements OnInit {
  areas: Area[] = [];
  cameras: Camera[] = [];
  selectedAreaId: number | null = null;
  selectedCameraId: number | null = null;

  // Tabs
  activeTab: 'arming' | 'linkage' | 'event' = 'arming';

  // ==============================
  // 🔹 Dữ liệu cho từng phần
  // ==============================
  schedule: { day: string; start: number; end: number }[] = [];
  eventSchedules: EventSchedule[] = [];
  linkage = {
    normal: {
      audibleWarning: true,
      sendEmail: false,
      notifySurveillance: false,
      fullScreenMonitoring: false,
    },
    triggerAlarmOutput: { A1: false, A2: false, A3: false, A4: false },
    audioLightAlarm: { audio: false, light: false },
    triggerRecording: {},
  };

  // UI control
  hours = Array.from({ length: 13 }, (_, i) => i * 2);
  dragging = false;
  dragType: 'start' | 'end' | 'range' | null = null;
  dragIndex: number | null = null;
  dragOffset = 0;
  tooltip = { visible: false, text: '', x: 0, y: -25 };
  loading = false;

  constructor(private cameraService: CameraService, private alarmService: AlarmService) {}

  ngOnInit() {
    this.loadAreas();
    this.resetSchedule();
  }

  // ==============================
  // 🔹 Load dữ liệu
  // ==============================
  loadAreas() {
    this.cameraService.getAreas().subscribe((data) => (this.areas = data));
  }

  onAreaChange() {
    if (!this.selectedAreaId) return;

    // 🟢 Load danh sách camera theo khu vực
    this.cameraService.getCamerasByArea(this.selectedAreaId).subscribe({
      next: (cams) => {
        this.cameras = cams || [];
        this.selectedCameraId = this.cameras.length > 0 ? this.cameras[0].camera_id : null;
      },
      error: (err) => console.error('[LOAD CAMERAS ERROR]', err),
    });

    // Sau khi có camera → load cấu hình báo động
    this.loadAlarmConfig();
  }


  /** 🔹 Load cấu hình theo khu vực */
  loadAlarmConfig() {
    if (!this.selectedAreaId) return;
    this.loading = true;

    this.alarmService.getAreaConfig(this.selectedAreaId).subscribe({
      next: (data) => {
        console.log('[LOAD CONFIG]', data);

        // 1️⃣ Arming schedule
        this.schedule = data?.arming_schedule?.length
          ? data.arming_schedule
          : this.defaultSchedule();

        // 2️⃣ Linkage
        this.linkage = {
          normal: {
            ...this.linkage.normal,
            ...(data?.linkage?.normal || {}),
          },
          triggerAlarmOutput: {
            ...this.linkage.triggerAlarmOutput,
            ...(data?.linkage?.triggerAlarmOutput || {}),
          },
          audioLightAlarm: {
            ...this.linkage.audioLightAlarm,
            ...(data?.linkage?.audioLightAlarm || {}),
          },
          triggerRecording: data?.linkage?.triggerRecording || {},
        };

        // 3️⃣ Event schedules
        if (data?.event_schedules && Object.keys(data.event_schedules).length > 0) {
          this.eventSchedules = Object.entries(data.event_schedules).map(([event, cfg]: any) => ({
            event,
            start: cfg.start || '08:00',
            end: cfg.end || '17:00',
            enabled: cfg.enabled ?? true,
            allowed: cfg.allowed ?? true,
          }));
        } else {
          this.eventSchedules = [
            { event: 'smoking', start: '08:00', end: '17:00', enabled: true, allowed: true },
            { event: 'checkincheckout', start: '07:30', end: '17:30', enabled: true, allowed: true },
          ];
        }

        this.loading = false;
      },
      error: (err) => {
        console.error('❌ Error loading alarm config:', err);
        this.schedule = this.defaultSchedule();
        this.loading = false;
      },
    });
  }

  // ==============================
  // 🔹 Arming Tab
  // ==============================
  resetSchedule() {
    this.schedule = this.defaultSchedule();
  }

  defaultSchedule() {
    return [
      { day: 'Monday', start: 0, end: 24 },
      { day: 'Tuesday', start: 0, end: 24 },
      { day: 'Wednesday', start: 0, end: 24 },
      { day: 'Thursday', start: 0, end: 24 },
      { day: 'Friday', start: 0, end: 24 },
      { day: 'Saturday', start: 0, end: 24 },
      { day: 'Sunday', start: 0, end: 24 },
    ];
  }

  toggleTab(tab: 'arming' | 'linkage' | 'event') {
    this.activeTab = tab;
  }

  clearAll() {
    this.schedule.forEach((s) => {
      s.start = 0;
      s.end = 0;
    });
  }

  copyToAll() {
    const ref = this.schedule[0];
    this.schedule.forEach((s, i) => {
      if (i !== 0) {
        s.start = ref.start;
        s.end = ref.end;
      }
    });
  }

  formatHourToTime(hour: number): string {
    const clamped = Math.max(0, Math.min(24, hour));
    const h = Math.floor(clamped);
    const m = Math.floor((clamped - h) * 60);
    return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}`;
  }

  // ==============================
  // 🔹 Drag timeline
  // ==============================
  onMouseDown(index: number, event: MouseEvent) {
    const rect = (event.currentTarget as HTMLElement).getBoundingClientRect();
    const x = event.clientX - rect.left;
    const hour = (x / rect.width) * 24;
    const s = this.schedule[index];

    if (hour < s.start || hour > s.end) {
      s.start = hour;
      s.end = hour;
      this.dragType = 'end';
    } else {
      this.dragType = 'range';
      this.dragOffset = hour - s.start;
    }

    this.dragging = true;
    this.dragIndex = index;
  }

  onMouseMove(index: number, event: MouseEvent) {
    if (!this.dragging || this.dragIndex !== index) return;
    const rect = (event.currentTarget as HTMLElement).getBoundingClientRect();
    const x = event.clientX - rect.left;
    const hour = Math.max(0, Math.min(24, (x / rect.width) * 24));

    const s = this.schedule[index];

    if (this.dragType === 'start') s.start = Math.min(hour, s.end);
    else if (this.dragType === 'end') s.end = Math.max(hour, s.start);
    else if (this.dragType === 'range') {
      const width = s.end - s.start;
      let newStart = hour - this.dragOffset;
      let newEnd = newStart + width;
      if (newStart < 0) {
        newStart = 0;
        newEnd = width;
      }
      if (newEnd > 24) {
        newEnd = 24;
        newStart = 24 - width;
      }
      s.start = newStart;
      s.end = newEnd;
    }

    // Tooltip
    this.tooltip.visible = true;
    this.tooltip.x = x;
    this.tooltip.text = `${this.formatHourToTime(s.start)} - ${this.formatHourToTime(s.end)}`;
  }

  onHandleDown(index: number, type: 'start' | 'end', event: MouseEvent) {
    event.stopPropagation();
    this.dragging = true;
    this.dragType = type;
    this.dragIndex = index;
  }

  onMouseUp() {
    this.dragging = false;
    this.dragType = null;
    this.dragIndex = null;
    this.tooltip.visible = false;
  }

  // ==============================
  // 🔹 Lưu cấu hình
  // ==============================
  saveAlarm() {
    if (!this.selectedAreaId) {
      alert('⚠️ Please select an area first!');
      return;
    }

    const payload = {
      arming_schedule: this.schedule,
      linkage: this.linkage,
      event_schedules: this.buildEventSchedulePayload(),
    };

    this.alarmService.saveAreaConfig(this.selectedAreaId, payload).subscribe({
      next: () => alert('✅ Configuration saved successfully!'),
      error: (err) => {
        console.error(err);
        alert('❌ Failed to save configuration!');
      },
    });
  }

  buildEventSchedulePayload() {
    const result: Record<string, any> = {};
    this.eventSchedules.forEach((e) => {
      result[e.event] = {
        start: e.start,
        end: e.end,
        enabled: e.enabled,
        allowed: e.allowed,
      };
    });
    return result;
  }
}
