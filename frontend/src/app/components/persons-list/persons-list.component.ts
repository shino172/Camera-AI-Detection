import { Component, ElementRef, OnInit, ViewChild } from '@angular/core';
import { FaceService, FaceEntry } from '../../services/face.service';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';

interface PersonDetail {
  person_id: number;
  name: string;
  email?: string;
  phone?: string;
  department?: string;
  position?: string;
  created_at?: string;
  avatar?: string;
}

@Component({
  selector: 'app-persons-list',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './persons-list.component.html',
})
export class PersonsListComponent implements OnInit {
  persons: PersonDetail[] = [];
  selectedPerson: PersonDetail | null = null;
  selectedImage: File | null = null;
  previewImage: string | null = null;

  constructor(
    private faceService: FaceService,
    private route: ActivatedRoute
  ) {}

  ngOnInit(): void {
    this.loadPersons();
  }

  loadPersons() {
    this.faceService.getPerson().subscribe({
      next: (personsData) => {
        this.persons = personsData.map(p => ({
          ...p,
          avatar: p.avatar || ''
        }));

        const id = this.route.snapshot.paramMap.get('id');
        if (id) {
          this.selectedPerson = this.persons.find(p => p.person_id === +id) || null;
        }
      },
      error: (err) => console.error('Error loading persons:', err)
    });
  }

  selectPerson(person: PersonDetail) {
    this.selectedPerson = { ...person };
    this.selectedImage = null;
    this.previewImage = null;
  }

  createNewPerson() {
    this.selectedPerson = {
      person_id: 0,
      name: '',
      email: '',
      phone: '',
      department: '',
      position: '',
      avatar: ''
    };
    this.previewImage = null;
  }

  onImageSelected(event: any) {
    const file = event.target.files[0];
    if (!file) return;
    this.selectedImage = file;
    const reader = new FileReader();
    reader.onload = (e: any) => (this.previewImage = e.target.result);
    reader.readAsDataURL(file);
  }


  toBase64(file: File): Promise<string> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result!.toString().split(',')[1]);
      reader.onerror = (error) => reject(error);
      reader.readAsDataURL(file);
    });
  }

  deletePerson(personId: number) {
    if (!confirm('Bạn có chắc muốn xóa nhân viên này?')) return;
    this.faceService.deletePerson(personId).subscribe({
      next: () => {
        alert('🗑️ Xóa thành công!');
        this.loadPersons();
        this.selectedPerson = null;
      },
      error: (err) => alert('❌ Lỗi khi xóa: ' + err.message)
    });
  }
  @ViewChild('avatarInput') avatarInput!: ElementRef<HTMLInputElement>;
  selectedAvatarFile: File | null = null;

  // Khi click vào ảnh => mở hộp chọn file
  triggerAvatarUpload() {
    this.avatarInput.nativeElement.click();
  }

  // Khi chọn ảnh xong => hiển thị preview
  onAvatarSelected(event: any) {
    const file = event.target.files[0];
    if (!file) return;
    this.selectedAvatarFile = file;
    const reader = new FileReader();
    reader.onload = (e: any) => (this.previewImage = e.target.result);
    reader.readAsDataURL(file);
  }

  async updatePerson() {
    if (!this.selectedPerson) return;
    const { person_id, ...data } = this.selectedPerson;

    try {
      if (this.selectedAvatarFile) {
        const base64 = await this.toBase64(this.selectedAvatarFile);
        const res = await this.faceService.uploadAvatar(base64).toPromise();
        data.avatar = res.image_url;
      }

      if (person_id === 0) {
        const base64 = this.previewImage ? this.previewImage.split(',')[1] : undefined;
        this.faceService.manualAddPerson(data.name, base64).subscribe({
          next: () => {
            alert('✅ Nhân viên mới đã được thêm.');
            this.loadPersons();
          },
          error: (err) => alert('❌ Lỗi khi thêm nhân viên: ' + err.message)
        });
      } else {
        this.faceService.updatePerson(person_id, data).subscribe({
          next: () => {
            alert('✅ Cập nhật thông tin thành công!');
            this.loadPersons();
          },
          error: (err) => alert('❌ Lỗi khi cập nhật: ' + err.message)
        });
      }
    } catch (error: any) {
      alert('❌ Lỗi upload ảnh: ' + error.message);
    }
  }

}
