import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { FaceService } from '../../services/face.service';

@Component({
  selector: 'app-admin-permission',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './admin-permission.component.html',
  styleUrls: ['./admin-permission.component.css']
})
export class AdminPermissionComponent implements OnInit {
  users: any[] = [];
  selectedUser: any = null;
  searchTerm: string = '';

  userAccount: { username: string | null } | null = null;
  accountData = { username: '', password: '' };
  showEditForm = false;
  mode: 'individual' | 'group' = 'individual';

  // ✅ Các quyền cá nhân
  permissions = {
    viewPlaybackLog: false,
    manage_Employees: false,
    viewEventAlarm: false,
    manageSystem: false
  };

  // ✅ Các quyền nhóm — cấu trúc giống hệt permissions
  groupPermissions = {
    viewPlaybackLog: false,
    manage_Employees: false,
    viewEventAlarm: false,
    manageSystem: false
  };

  constructor(private faceService: FaceService) {}

  ngOnInit() {
    this.loadUsers();
    
  }

  // ========================= CHUYỂN CHẾ ĐỘ =========================
  toggleMode() {
    this.mode = this.mode === 'individual' ? 'group' : 'individual';
    this.selectedUser = null;
    this.users.forEach(u => (u.selected = false));
  }

  // ========================= TẢI DANH SÁCH NHÂN VIÊN =========================
  loadUsers() {
    Promise.all([
      this.faceService.getPerson().toPromise(),
      fetch('http://localhost:5000/api/user_accounts')
        .then(r => (r.ok ? r.json() : []))
        .catch(() => [])
    ])
      .then(([persons, accounts]: any[]) => {
        const accountMap = new Map<number, string>();
        (accounts || []).forEach((a: any) => {
          if (a.person_id && a.username) accountMap.set(a.person_id, a.username);
        });

        this.users = (persons || []).map((u: any) => ({
          ...u,
          selected: false,
          hasAccount: accountMap.has(u.person_id),
          accountUsername: accountMap.get(u.person_id) || null
        }));
      })
      .catch(() => {
        alert('❌ Không thể tải danh sách nhân viên hoặc tài khoản');
        this.users = [];
      });
  }

  filteredUsers() {
    return this.users.filter(u =>
      u.name?.toLowerCase().includes(this.searchTerm.toLowerCase())
    );
  }

  // ========================= TẢI / TẠO / XÓA / CẬP NHẬT TÀI KHOẢN =========================
  selectUser(u: any) {
    this.selectedUser = u;
    this.loadAccount();
    this.loadPermissions();
  }

  loadAccount() {
    fetch(`http://localhost:5000/api/users/${this.selectedUser.person_id}/account`)
      .then(res => res.json())
      .then(data => {
        this.userAccount = data;
        this.showEditForm = false;
        this.accountData = { username: '', password: '' };
      })
      .catch(() => (this.userAccount = null));
  }

  createAccount() {
    if (!this.accountData.username || !this.accountData.password)
      return alert('⚠️ Nhập đầy đủ tên đăng nhập và mật khẩu!');

    fetch(`http://localhost:5000/api/users/${this.selectedUser.person_id}/account`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(this.accountData)
    })
      .then(res => res.json())
      .then(() => {
        alert('✅ Tạo tài khoản thành công!');
        this.selectedUser.hasAccount = true;
        this.selectedUser.accountUsername = this.accountData.username;
        this.loadAccount();
      })
      .catch(err => alert('❌ Lỗi tạo tài khoản: ' + err.message));
  }

  updateAccount() {
    if (!this.accountData.password)
      return alert('⚠️ Nhập mật khẩu mới trước khi lưu!');

    const payload = {
      password: this.accountData.password,
      username: this.userAccount?.username
    };

    fetch(`http://localhost:5000/api/users/${this.selectedUser.person_id}/account`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
      .then(res => res.json())
      .then(() => {
        alert('🔑 Cập nhật mật khẩu thành công!');
        this.loadAccount();
        this.showEditForm = false;
      })
      .catch(err => alert('❌ Lỗi cập nhật mật khẩu: ' + err.message));
  }

  deleteAccount() {
    if (!confirm('⚠️ Bạn có chắc muốn xóa tài khoản này không?')) return;

    fetch(`http://localhost:5000/api/users/${this.selectedUser.person_id}/account`, {
      method: 'DELETE'
    })
      .then(res => res.json())
      .then(() => {
        alert('🗑️ Đã xóa tài khoản nhân viên!');
        this.userAccount = null;
        this.selectedUser.hasAccount = false;
      })
      .catch(err => alert('❌ Lỗi khi xóa tài khoản: ' + err.message));
  }

  // ========================= QUẢN LÝ PHÂN QUYỀN =========================
  loadPermissions() {
    fetch(`http://localhost:5000/api/users/${this.selectedUser.person_id}/permissions`)
      .then(res => res.json())
      .then((codes: string[]) => {
        this.permissions = {
          viewPlaybackLog: codes.includes('VIEW_PLAYBACKLOG'),
          manage_Employees: codes.includes('MANAGE_EMPLOYEES'),
          viewEventAlarm: codes.includes('EVENT_ALARM'),
          manageSystem: codes.includes('MANAGE_SYSTEM')
        };
      })
      .catch(() => {
        this.permissions = {
          viewPlaybackLog: false,
          manage_Employees: false,
          viewEventAlarm: false,
          manageSystem: false
        };
      });
  }

  savePermissions() {
    const codes = this.mapPermissionsToCodes(this.permissions);

    fetch(`http://localhost:5000/api/users/${this.selectedUser.person_id}/permissions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ codes })
    })
      .then(res => res.json())
      .then(() => alert('💾 Lưu phân quyền thành công!'))
      .catch(err => alert('❌ Lỗi lưu quyền: ' + err.message));
  }

  // ========================= NHÓM QUYỀN =========================
  hasSelectedPermissions(): boolean {
    return Object.values(this.groupPermissions).some(v => v === true);
  }

  applyGroupPermission() {
    const selectedUsers = this.users.filter(u => u.selected && u.hasAccount);
    const codes = this.mapPermissionsToCodes(this.groupPermissions);

    if (selectedUsers.length === 0)
      return alert('⚠️ Vui lòng chọn ít nhất 1 nhân viên có tài khoản!');
    if (codes.length === 0)
      return alert('⚠️ Vui lòng chọn ít nhất 1 quyền cần cấp!');

    const confirmMsg = `Xác nhận cấp quyền (${codes.join(', ')}) cho ${selectedUsers.length} nhân viên?`;
    if (!confirm(confirmMsg)) return;

    const updates = selectedUsers.map(u =>
      fetch(`http://localhost:5000/api/users/${u.person_id}/permissions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ codes })
      }).then(res => res.json())
    );

    Promise.all(updates)
      .then(() => {
        alert(`✅ Đã cấp quyền (${codes.join(', ')}) cho ${selectedUsers.length} nhân viên!`);
        this.users.forEach(u => (u.selected = false));
        // reset trạng thái group
        this.groupPermissions = {
          viewPlaybackLog: false,
          manage_Employees: false,
          viewEventAlarm: false,
          manageSystem: false
        };
      })
      .catch(err => alert('❌ Lỗi khi cấp quyền nhóm: ' + err.message));
  }

  // ========================= HÀM CHUYỂN QUYỀN SANG MÃ CODE =========================
  private mapPermissionsToCodes(perms: any): string[] {
    return Object.entries(perms)
      .filter(([_, val]) => val)
      .map(([key]) => {
        switch (key) {
          case 'viewPlaybackLog': return 'VIEW_PLAYBACKLOG';
          case 'manage_Employees': return 'MANAGE_EMPLOYEES';
          case 'viewEventAlarm': return 'EVENT_ALARM';
          case 'manageSystem': return 'MANAGE_SYSTEM';
          default: return '';
        }
      })
      .filter(c => !!c);
  }
}
