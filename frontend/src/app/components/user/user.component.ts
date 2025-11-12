import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { FaceEntry, FaceService } from '../../services/face.service';
import { error } from 'console';

@Component({
  selector: 'app-user',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './user.component.html',
  styleUrl: './user.component.css'
})
export class UserComponent {
  @Input() employee!: FaceEntry;
  @Output() update = new EventEmitter<any>();
  @Output() delete = new EventEmitter<number>();

  editMode: boolean = false;
  newName = '';

  constructor(private faceService: FaceService){}
  ngOnChanges() {
    if (this.employee){
      this.newName = this.employee.name
    }
  }
  enableEdit(){
    this.editMode = true
  }
  // saveChanges() {
  //   this.faceService.updateFaceName( this.employee.person_id, this.newName).subscribe({
  //     next: () => {
  //       this.employee.name = this.newName;
  //       this.update.emit(this.employee);
  //       this.editMode = false;
  //     },
  //     error: (err) => console.error('Update failed', err)
  //   })
  // }

  // deleteEmployee() {
  //   this.faceService.deleteFace(this.employee.person_id).subscribe({
  //     next: () =>{
  //       this.delete.emit(this.employee.person_id);
  //     },
  //     error: (err) => console.error('Delete failed', err)
  //   })
  // }
}
