import { Injectable } from '@angular/core';
import { CanActivate, Router } from '@angular/router';
import { AuthService } from '../services/auth.service';

@Injectable({
  providedIn: 'root'
})
export class AdminGuard implements CanActivate {
  constructor(private auth: AuthService, private router: Router) {}

  canActivate(): boolean {
    if (!this.auth.isAdmin()) {
      alert('🚫 Chỉ quản trị viên mới được phép truy cập!');
      this.router.navigate(['/home']);
      return false;
    }
    return true;
  }
}
