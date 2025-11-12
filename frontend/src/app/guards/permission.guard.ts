import { Injectable } from '@angular/core';
import { CanActivate, ActivatedRouteSnapshot, Router } from '@angular/router';
import { AuthService } from '../services/auth.service';

@Injectable({ providedIn: 'root' })
export class PermissionGuard implements CanActivate {
  constructor(private auth: AuthService, private router: Router) {}

  canActivate(route: ActivatedRouteSnapshot): boolean {
    const requiredPermission = route.data['permission'] as string;

    if (!requiredPermission) return true;
    if (this.auth.isAdmin()) return true;

    const perms = this.auth.getPermissions();
    if (perms.includes(requiredPermission)) return true;

    alert('🚫 Bạn không có quyền truy cập vào chức năng này!');
    this.router.navigate(['/']);
    return false;
  }
}
