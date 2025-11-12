import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../../services/auth.service';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';

@Component({
  selector: 'app-header',
  standalone: true,
  imports: [CommonModule, RouterLink, FormsModule, ReactiveFormsModule],
  templateUrl: './header.component.html',
  styleUrls: ['./header.component.css']
})
export class HeaderComponent {
  dropdownOpen = false;

  constructor(public auth: AuthService, private router: Router) {}

  /** Toggle dropdown user menu */
  toggleDropdown() {
    this.dropdownOpen = !this.dropdownOpen;
  }

  /** Đăng xuất hệ thống */
  logout() {
    this.dropdownOpen = false;
    this.auth.logout();
  }

  /** Lấy tên người dùng đang đăng nhập */
  getUsername(): string {
    const username = this.auth.getUsername();
    return username ? username : 'Guest';
  }

  /** Mô tả rõ vai trò người dùng hiện tại */
  getRoleLabel(): string {
    if (!this.auth.isLoggedIn()) return '';
    if (this.auth.isAdmin()) return 'Administrator';

    const perms = this.auth.getPermissions();

    if (perms.includes('MANAGE_SYSTEM')) return 'System Manager';
    if (perms.includes('EVENT_ALARM')) return 'Event & Alarm Operator';
    if (perms.includes('VIEW_PLAYBACKLOG')) return 'Playback Viewer';
    if (perms.includes('MANAGE_EMPLOYEES')) return 'Management Employees';
    return 'User';
  }

  /** Kiểm tra xem người dùng có quyền cụ thể không */
  hasPermission(code: string): boolean {
    return this.auth.isAdmin() || this.auth.getPermissions().includes(code);
  }
}
