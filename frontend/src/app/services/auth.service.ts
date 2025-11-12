import { Injectable, NgZone } from '@angular/core';
import { Router } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { tap } from 'rxjs/operators';

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private apiUrl = 'http://localhost:5000/api/auth/login';
  private isLoggedInStatus = false;
  private role: 'user' | 'admin' | null = null;
  private timeoutMinutes = 10;
  private timeoutTimer: any;

  constructor(
    private http: HttpClient,
    private router: Router,
    private ngZone: NgZone
  ) {
    const savedRole = sessionStorage.getItem('role');
    if (savedRole === 'admin' || savedRole === 'user') {
      this.isLoggedInStatus = true;
      this.role = savedRole as 'admin' | 'user';
      this.resetTimeout();
    }
    this.setupActivityListener();
  }

  /** 👑 Hardcode admin login */
  loginAsAdmin(username: string, password: string): boolean {
    if (username === 'admin' && password === '240624') {
      this.isLoggedInStatus = true;
      this.role = 'admin';
      sessionStorage.setItem('role', 'admin');
      sessionStorage.setItem('token', 'true');
      sessionStorage.setItem('username', 'admin');
      this.resetTimeout();
      return true;
    }
    return false;
  }

  /** 👤 Login user thật từ Flask API */
  loginAsUser(username: string, password: string) {
    return this.http.post<any>(this.apiUrl, { username, password }).pipe(
      tap((res) => {
        this.isLoggedInStatus = true;
        this.role = 'user';
        sessionStorage.setItem('role', 'user');
        sessionStorage.setItem('token', 'true');
        sessionStorage.setItem('username', username);
        sessionStorage.setItem('permissions', JSON.stringify(res.permissions || []));
        this.resetTimeout();
      })
    );
  }

  /** 🚪 Logout toàn hệ thống */
  logout(auto = false) {
    this.isLoggedInStatus = false;
    this.role = null;
    sessionStorage.clear();
    clearTimeout(this.timeoutTimer);
    if (auto) alert('⚠️ Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.');
    this.router.navigate(['/login']);
  }

  /** 🔐 Kiểm tra trạng thái đăng nhập */
  isLoggedIn(): boolean {
    return this.isLoggedInStatus;
  }

  /** 👑 Kiểm tra quyền admin */
  isAdmin(): boolean {
    return this.role === 'admin';
  }

  /** 👤 Lấy username */
  getUsername(): string | null {
    return sessionStorage.getItem('username');
  }

  /** 🧠 Lấy quyền thực tế */
  getPermissions(): string[] {
    try {
      return JSON.parse(sessionStorage.getItem('permissions') || '[]');
    } catch {
      return [];
    }
  }

  private permissions: string[] = [];

  setPermissions(perms: string[]) {
    this.permissions = perms;
    sessionStorage.setItem('permissions', JSON.stringify(perms));
  }
  markUserLoggedIn() {
    this.isLoggedInStatus = true;
    this.role = 'user';
    sessionStorage.setItem('role', 'user');
  }


  /** ⚙️ Các quyền động */
  canViewPlayback(): boolean {
    return this.isAdmin() || this.getPermissions().includes('VIEW_PLAYBACK');
  }

  canViewLog(): boolean {
    return this.isAdmin() || this.getPermissions().includes('VIEW_LOG');
  }

  canEditEvent(): boolean {
    return this.isAdmin() || this.getPermissions().includes('EDIT_EVENT');
  }

  canViewAlarm(): boolean {
    return this.isAdmin() || this.getPermissions().includes('VIEW_ALARM');
  }

  hasPermission(code: string): boolean {
    return this.isAdmin() || this.getPermissions().includes(code);
  }


  /** 🕓 Giám sát hoạt động */
  private setupActivityListener() {
    const reset = () => this.resetTimeout();
    window.addEventListener('mousemove', reset);
    window.addEventListener('click', reset);
    window.addEventListener('keydown', reset);
    window.addEventListener('scroll', reset);
  }

  private resetTimeout() {
    clearTimeout(this.timeoutTimer);
    if (!this.isLoggedInStatus) return;

    this.ngZone.runOutsideAngular(() => {
      this.timeoutTimer = setTimeout(() => {
        this.ngZone.run(() => this.logout(true));
      }, this.timeoutMinutes * 60 * 1000);
    });
  }

}
