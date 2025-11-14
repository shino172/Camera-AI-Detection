import { Component, Input, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { EventService, EventLog } from '../../services/event.service';
import * as XLSX from 'xlsx';
import Swal from 'sweetalert2';

@Component({
  selector: 'app-log-file',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './log-file.component.html',
  styleUrls: ['./log-file.component.css']
})
export class LogFileComponent implements OnInit {

  @Input() embedded = false;

  logs: EventLog[] = [];
  filteredLogs: EventLog[] = [];
  paginatedLogs: EventLog[] = [];

  // Bộ lọc
  selectedDate: string = '';
  selectedArea: string = '';
  selectedEvent: string = '';

  // Danh sách lựa chọn
  areaOptions: string[] = [];
  eventOptions: string[] = [];

  // Phân trang
  pageSize = 6;
  currentPage = 1;
  totalPages = 0;

  constructor(private eventService: EventService) {}

  ngOnInit(): void {
    const today = new Date();
    this.selectedDate = today.toISOString().split('T')[0];
    this.loadLogs();
  }

  loadLogs(): void {
    this.eventService.getEvents(500, 0).subscribe({
      next: (data) => {
        this.logs = data;
        this.areaOptions = Array.from(
          new Set(
            data
              .map(l => l.area_name)
              .filter((a): a is string => typeof a === 'string' && a.trim() !== '')
          )
        );

        this.eventOptions = Array.from(
          new Set(
            data
              .map(l => l.label)
              .filter((e): e is string => typeof e === 'string' && e.trim() !== '')
          )
        );

        this.eventOptions = Array.from(new Set(data.map(l => l.label).filter(Boolean)));
        this.filterLogs();
      },
      error: (err) => console.error('❌ Load logs error:', err)
    });
  }

  filterLogs(): void {
    const date = this.selectedDate ? new Date(this.selectedDate) : null;
    this.filteredLogs = this.logs.filter(log => {
      const logDate = new Date(log.time);
      const matchDate = date ? logDate.toDateString() === date.toDateString() : true;
      const matchArea = this.selectedArea ? log.area_name === this.selectedArea : true;
      const matchEvent = this.selectedEvent ? log.label === this.selectedEvent : true;
      return matchDate && matchArea && matchEvent;
    });

    this.currentPage = 1;
    this.totalPages = Math.ceil(this.filteredLogs.length / this.pageSize);
    this.updatePagination();
  }

  updatePagination(): void {
    const start = (this.currentPage - 1) * this.pageSize;
    const end = start + this.pageSize;
    this.paginatedLogs = this.filteredLogs.slice(start, end);
  }

  changePage(page: number): void {
    if (page < 1 || page > this.totalPages) return;
    this.currentPage = page;
    this.updatePagination();
  }

  exportExcel(): void {
    if (!this.filteredLogs.length) {
      Swal.fire('⚠️ Không có dữ liệu để xuất.', '', 'info');
      return;
    }
    this.eventService.exportEventsToExcel(this.filteredLogs);
  }

  /** 👁️ Xem chi tiết sự kiện */
  viewDetail(log: EventLog) {
    Swal.fire({
      title: `Chi tiết sự kiện`,
      html: `
        <div class="text-left text-sm">
          <p><b>ID:</b> ${log.id}</p>
          <p><b>Camera:</b> ${log.camera_id}</p>
          <p><b>Sự kiện:</b> ${log.label}</p>
          <p><b>Thời gian:</b> ${new Date(log.time).toLocaleString()}</p>
          <p><b>Khu vực:</b> ${log.area_name || '-'}</p>
          ${
            log.image_url
              ? `<img src="${log.image_url}" style="margin-top:10px;max-width:100%;border-radius:8px;">`
              : ''
          }
        </div>`,
      width: 600,
      showConfirmButton: true,
    });
  }

  /** 🗑️ Xóa 1 log */
  deleteLog(eventId: string, ev: Event) {
    ev.stopPropagation(); // tránh kích hoạt viewDetail
    Swal.fire({
      title: 'Xác nhận xóa sự kiện?',
      icon: 'warning',
      showCancelButton: true,
      confirmButtonText: 'Xóa',
      cancelButtonText: 'Hủy',
    }).then(result => {
      if (result.isConfirmed) {
        this.eventService.deleteEvent(eventId).subscribe({
          next: () => {
            this.logs = this.logs.filter(l => l.id !== eventId);
            this.filterLogs();
            Swal.fire('🗑️ Đã xóa sự kiện', '', 'success');
          },
          error: (err) => {
            console.error(err);
            Swal.fire('❌ Lỗi khi xóa', '', 'error');
          }
        });
      }
    });
  }

  /** 🧹 Xóa tất cả log trong khu vực đang chọn */
  deleteAreaLogs() {
    if (!this.selectedArea) return;
    Swal.fire({
      title: `Xóa tất cả log khu vực "${this.selectedArea}"?`,
      icon: 'warning',
      showCancelButton: true,
      confirmButtonText: 'Xóa',
      cancelButtonText: 'Hủy',
    }).then(result => {
      if (result.isConfirmed) {
        const areaLogs = this.logs.filter(l => l.area_name === this.selectedArea);
        areaLogs.forEach(l => this.eventService.deleteEvent(l.id).subscribe());
        this.logs = this.logs.filter(l => l.area_name !== this.selectedArea);
        this.filterLogs();
        Swal.fire('🗑️ Đã xóa toàn bộ log của khu vực.', '', 'success');
      }
    });
  }

  /** 🗑️ Xóa tất cả log */
  deleteAllLogs() {
    Swal.fire({
      title: 'Xóa toàn bộ sự kiện?',
      text: 'Thao tác này không thể hoàn tác.',
      icon: 'warning',
      showCancelButton: true,
      confirmButtonText: 'Xóa tất cả',
      cancelButtonText: 'Hủy',
    }).then(result => {
      if (result.isConfirmed) {
        this.eventService.deleteAllEvents().subscribe({
          next: () => {
            this.logs = [];
            this.filteredLogs = [];
            this.paginatedLogs = [];
            Swal.fire('🗑️ Đã xóa toàn bộ sự kiện', '', 'success');
          },
          error: (err) => {
            console.error(err);
            Swal.fire('❌ Xóa thất bại', '', 'error');
          }
        });
      }
    });
  }
}
