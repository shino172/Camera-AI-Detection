import { Component } from '@angular/core';
import { FaceLogComponent } from "../face-log/face-log.component";
import { PersonsListComponent } from '../persons-list/persons-list.component';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-management-employees',
  standalone: true,
  imports: [FaceLogComponent, PersonsListComponent, CommonModule],
  templateUrl: './management-employees.component.html',
  styleUrl: './management-employees.component.scss'
})
export class ManagementEmployeesComponent {
  activeTab: 'list' | 'face' = 'list';

  /** Chuyển tab hiện tại */
  switchTab(tab: 'list' | 'face') {
    this.activeTab = tab;
  }
}
