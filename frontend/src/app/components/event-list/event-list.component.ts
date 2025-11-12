import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { EventLog, EventService } from '../../services/event.service';
import Swal from 'sweetalert2';
import { ActivatedRoute } from '@angular/router';

@Component({
  selector: 'app-event-list',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './event-list.component.html',
  styleUrl: './event-list.component.css'
})
export class EventListComponent implements OnInit {
  events: EventLog[] = [];
  currentCount = 0;
  attendanceEvents: EventLog[]=[]
  smokingEvents: EventLog []=[]
  activeTab: 'attendance' | 'smoking' = 'attendance'
  pageSize = 3
  attendancePage=1
  smokingPage=1
  selectedEvent: EventLog | null = null;
  showVideo = false;
  isLoadingPlayBack = false;
  selectedVideoUrl: string | null = null;

  constructor(
    private eventService: EventService,
    private route: ActivatedRoute
  ) {}

  ngOnInit(): void {
    this.loadEvents();

    this.eventService.streamEvents().subscribe(newE => {
      this.addEvent(newE);
    });

    this.route.queryParams.subscribe(params =>{
      const eventId = params['id'];
      const type = params['type'];

        if(type === 'attendance' || type === 'smoking'){
          this.activeTab = type;
        }
        if(eventId){
          setTimeout(() => this.scrollToEvent(eventId), 300)
        }
    })

    setInterval(() => {
      this.loadEvents();
    }, 5000);
  }

  loadEvents(): void {
    this.eventService.getEvents().subscribe({
      next: (data) => {
        const sorted = data.sort(
          (a, b) => new Date(b.time).getTime() - new Date(a.time).getTime()
        );
        this.events = sorted;
        this.attendanceEvents = sorted.filter(
          e => e.label === 'checkin' || e.label === 'checkout'
        );
        this.smokingEvents = sorted.filter(
          e => e.label === 'smoking' || e.label === 'hand_to_mouth'
        );
      },
      error: (err) => console.error('Lỗi lấy events:', err)
    });
  }

  closePlayBack(){
    this.selectedEvent = null;
  }
  scrollToEvent(eventId: string) {
    const el = document.getElementById(`event-${eventId}`);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      el.classList.add('bg-yellow-100');
      setTimeout(() => el.classList.remove('bg-yellow-100'), 3000);
    }
  }
  getAttendanceEvent(){
    return this.events.filter(e => e.label === 'checkin' || e.label === 'checkout')
  }
  getSmokingEvent(){
    return this.events.filter(e=> e.label === 'smoking'|| e.label === 'hand_to_mouth')
  }
  get attendanceTotalPages():number{
    return Math.ceil(this.attendanceEvents.length / this.pageSize) ||1;
  }
  get smokingTotalPages():number {
    return Math.ceil(this.smokingEvents.length / this.pageSize) ||1;
  }
  get attendancePageData() {
    const start = (this.attendancePage - 1) * this.pageSize;
    return this.attendanceEvents.slice(start, start + this.pageSize);
  }
  get smokingPageData() {
    const start = (this.smokingPage - 1) * this.pageSize;
    return this.smokingEvents.slice(start, start + this.pageSize);
  }
  changePage(tab: 'attendance' | 'smoking', dir: number) {
    if (tab === 'attendance') {
      const newPage = this.attendancePage + dir;
      if (newPage >= 1 && newPage <= this.attendanceTotalPages) {
        this.attendancePage = newPage;
      }
    } else {
      const newPage = this.smokingPage + dir;
      if (newPage >= 1 && newPage <= this.smokingTotalPages) {
        this.smokingPage = newPage;
      }
    }
  }
  private addEvent(e: EventLog) {
    if (e.label === 'checkin' || e.label === 'checkout') {
      this.attendanceEvents.unshift(e);
      if (this.attendanceEvents.length > 50) this.attendanceEvents.pop();
    } else if (e.label === 'smoking' || e.label === 'hand_to_mouth') {
      this.smokingEvents.unshift(e);
      if (this.smokingEvents.length > 50) this.smokingEvents.pop();
    }
  }
  convertToLocalTime(utcTime: string): string {
    const d = new Date(utcTime);
    return d.toLocaleString('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh' });  // Convert it to the Vietnam timezone
  }

  openEvent(event: EventLog) {
    console.log('Video URL:', event.video_url);
    this.selectedEvent = event;
    this.showVideo = false;
  }

  closeEvent() {
    this.selectedEvent = null;
  }
  showAlert(event: EventLog){
    if (event.label === "smoking") {
      Swal.fire({
        title: `🚨 Phát hiện ${event.name} có hành vi vi phạm!`,
        icon: 'warning',
        confirmButtonText:'OK'
      });

    } else if (event.label === "hand_to_mouth") {
      Swal.fire({
        title: `🚨 Phát hiện ${event.name} có hành vi nghi vấn!`,
        icon: 'warning',
        confirmButtonText: 'OK'
      });
    }
      else if (event.label === "checkin") {
      Swal.fire({
        title: `✅ ${event.name} đã check-in`,
        icon: 'success',
        confirmButtonText: 'OK'
      });
    } else if (event.label === "checkout") {
      Swal.fire({
        title: `👋 ${event.name} đã check-out`,
        icon: 'info',
        confirmButtonText: 'OK'
      });
    } else if (event.label === "face_detected") {
      Swal.fire({
        title: `👤 Nhận diện: ${event.name}`,
        icon: 'info',
        confirmButtonText: 'OK'
      });
    }
  }
  deleteEvent(eventId: string){
    this.eventService.deleteEvent(eventId).subscribe({
      next: (res) => {
        // cập nhật lại danh sách sau khi xoá
        this.events = this.events.filter(e => e.id !== eventId);
        Swal.fire('🗑️ Đã xoá sự kiện', '', 'success');
      },
      error: (err) => {
        console.error('Xoá sự kiện lỗi:', err);
        Swal.fire('❌ Xoá thất bại', '', 'error');
      }
    });
  }
  deleteAllEvents(){
    this.eventService.deleteAllEvents().subscribe({
      next: (res) => {
        this.events = [];
        Swal.fire('🗑️ Đã xoá tất cả sự kiện', '', 'success');
      },
      error: (err) => {
        console.error('Xoá tất cả sự kiện lỗi:', err);
        Swal.fire('❌ Xoá tất cả thất bại', '', 'error');
      }
    });
  }
}
