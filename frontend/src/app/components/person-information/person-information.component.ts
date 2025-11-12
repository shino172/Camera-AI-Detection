import { CommonModule } from '@angular/common';
import { HttpClient, HttpClientModule } from '@angular/common/http';
import { Component, EventEmitter, Input, Output } from '@angular/core';
import { FormBuilder, FormGroup, FormsModule, ReactiveFormsModule, Validators } from '@angular/forms';
import { error } from 'console';
import { FaceService } from '../../services/face.service';

@Component({
  selector: 'app-person-information',
  standalone: true,
  imports: [FormsModule, CommonModule, ReactiveFormsModule, HttpClientModule],
  templateUrl: './person-information.component.html',
  styleUrls: ['./person-information.component.css']
})
export class PersonInformationComponent {
  @Input() person: any;
  @Output() closed = new EventEmitter<void>();
  @Output() updated = new EventEmitter<void>();

  form: FormGroup;

  constructor(private fb: FormBuilder, private faceService: FaceService) {
    this.form = this.fb.group({
      name: ['', Validators.required],
      email: [''],
      phone: [''],
      department: [''],
      position: ['']
    });
  }

  ngOnChanges() {
    if (this.person) {
      this.form.patchValue(this.person);
    }
  }

  save() {
    if (this.form.invalid) return;

    this.faceService.updatePerson(this.person.person_id, this.form.value)
      .subscribe({
        next: () => {
          alert("Cập nhật thông tin thành công!");
          this.updated.emit();
          this.closed.emit();
        },
        error: (err) => {
          console.error("Cập nhật thông tin thất bại:", err);
          alert("Cập nhật thất bại!");
        }
      });
  }

  close() {
    this.closed.emit();
  }
}
