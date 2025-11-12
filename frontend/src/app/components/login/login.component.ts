import { Component } from '@angular/core';
import { Router } from '@angular/router';
import { AuthService } from '../../services/auth.service';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

@Component({
  selector: 'app-login',
  standalone: true,
  templateUrl: './login.component.html',
  imports: [CommonModule, FormsModule],
  styleUrls: ['./login.component.css']
})
export class LoginComponent {
  username = '';
  password = '';
  errorMessage = '';
  isLoading = false;

  constructor(private auth: AuthService, private router: Router) {}

  login() {
    this.errorMessage = '';
    if (!this.username || !this.password) {
      this.errorMessage = '⚠️ Vui lòng nhập đầy đủ tài khoản và mật khẩu.';
      return;
    }

    // ✅ Nếu là admin
    if (this.auth.loginAsAdmin(this.username, this.password)) {
      this.router.navigate(['/']);
      return;
    }

    // ✅ Nếu không phải admin → gọi Flask API
    this.isLoading = true;
    this.auth.loginAsUser(this.username, this.password).subscribe({
      next: (res) => {
        console.log('✅ Login success:', res);
        this.isLoading = false;

        // ✅ Lưu lại quyền từ Flask
        this.auth.setPermissions(res.permissions || []);

        // Lưu trạng thái đăng nhập
        this.auth.markUserLoggedIn();

        this.router.navigate(['/']);
      },
      error: (err) => {
        console.error('❌ Login failed:', err);
        this.isLoading = false;
        this.errorMessage = '⚠️ Đăng nhập thất bại. Vui lòng kiểm tra lại tài khoản và mật khẩu.';
      }
    });
  }
}
