import { Routes } from '@angular/router';
import { EventAlarmComponent } from './components/event-alarm/event-alarm.component';
import { EventListComponent } from './components/event-list/event-list.component';
import { HomeComponent } from './components/home/home.component';
import { LayoutsComponent } from './components/layouts/layouts.component';
import { LoginComponent } from './components/login/login.component';
import { AuthGuard } from './guards/auth.guard';
import { AdminManagerComponent } from './components/admin-manager/admin-manager.component';
import { FaceLogComponent } from './components/face-log/face-log.component';
import { AdminPermissionComponent } from './components/admin-permission/admin-permission.component';
import { PermissionGuard } from './guards/permission.guard';
import { ManagementEmployeesComponent } from './components/management-employees/management-employees.component';
import { PlaybackLogComponent } from './components/playback-log/playback-log.component';

export const routes: Routes = [
  { path: 'login', component: LoginComponent },

  {
    path: '',
    component: LayoutsComponent,
    canActivate: [AuthGuard],
    children: [
      { path: 'home', component: HomeComponent },

      // 🎥 Playback (VIEW_PLAYBACK)
      { path: 'playback', component: PlaybackLogComponent, canActivate: [PermissionGuard], data: { permission: 'VIEW_PLAYBACKLOG' } },

      // ⚙️ Event + Alarm (EVENT-ALARM)
      { path: 'event-alarm', component: EventAlarmComponent, canActivate: [PermissionGuard], data: { permission: 'EVENT_ALARM' } },

      // 👥 Danh sách nhân viên (MANAGE_EMPLOYEES)
      { path:'manage-employees', component: ManagementEmployeesComponent, canActivate: [PermissionGuard], data: { permission: 'MANAGE_EMPLOYEES' } },
      // { path: 'persons-list', component: PersonsListComponent, canActivate: [PermissionGuard], data: { permission: 'MANAGE_EMPLOYEES' } },
      // { path: 'persons-list/:id', component: PersonsListComponent, canActivate: [PermissionGuard], data: { permission: 'MANAGE_EMPLOYEES' } },

      // 🧰 Quản lý hệ thống
      { path: 'admin-manager', component: AdminManagerComponent, canActivate: [PermissionGuard], data: { permission: 'MANAGE_SYSTEM' } },

      // 🔐 Phân quyền
      { path: 'admin-permission', component: AdminPermissionComponent, canActivate: [PermissionGuard], data: { permission: 'MANAGE_SYSTEM' } },

      // 🧠 Nhận diện khuôn mặt
      { path: 'face-recognize', component: FaceLogComponent, canActivate: [PermissionGuard], data: { permission: 'MANAGE_SYSTEM' } },

      // 👤 User profile
      { path: 'event-list', component: EventListComponent  },

      { path: '', redirectTo: 'home', pathMatch: 'full' },
      { path: '**', redirectTo: 'home' }
    ]
  }
];
