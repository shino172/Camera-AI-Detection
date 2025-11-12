import { Component, OnInit } from '@angular/core';
import { EventLog, EventService } from '../../services/event.service';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { error } from 'console';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.css'
})
export class DashboardComponent implements OnInit{
  events: EventLog[]=[]
  filteredEvents: EventLog[]=[]
  searchText: string =''
  searchDate: string =''

  constructor(private eventService: EventService){}

  ngOnInit(): void {
    this.loadEvents()
    this.eventService.streamEvents().subscribe(newE => {
      this.events.unshift(newE);
      if(this.events.length > 50) this.events.pop()
    })
  }

  loadEvents(): void{
    this.eventService.getEvents().subscribe(data=>{
      this.events = data;
      this.filteredEvents = data
    })
  }
  filter(): void {
    this.filteredEvents = this.events.filter(e => {
      const matchName = this.searchText ?
        e.name?.toLowerCase().includes(this.searchText.toLowerCase()) : true;
      const matchDate = this.searchDate ?
        e.time?.includes(this.searchDate) : true;
      return matchName && matchDate;
    });
  }

  deleteEvent(event: EventLog) {
    if (!event.id) {
      console.error("Event không có id", event);
      return;
    }

    if (confirm(`Bạn có chắc muốn xóa sự kiện lúc ${event.time}?`)) {
      this.eventService.deleteEvent(event.id).subscribe({
        next: () => {
          this.events = this.events.filter(e => e.id !== event.id);
          this.filteredEvents = this.filteredEvents.filter(e => e.id !== event.id);
          alert("Đã xóa sự kiện thành công ✅");
        },
        error: err => {
          console.error("Xóa thất bại:", err);
          alert("❌ Lỗi khi xóa sự kiện!");
        }
      });
    }
  }
  deleteAll() {
    if (confirm("Bạn có chắc chắn muốn xóa TẤT CẢ sự kiện?")) {
      this.eventService.deleteAllEvents().subscribe({
        next: () => {
          this.events = [];
          this.filteredEvents = [];
          alert("Đã xoá tất cả sự kiện ✅");
        },
        error: err => {
          console.error("Xóa tất cả thất bại:", err);
          alert("❌ Lỗi khi xoá tất cả sự kiện!");
        }
      });
    }
  }




}
