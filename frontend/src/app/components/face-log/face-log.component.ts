
import { Component, OnInit } from '@angular/core';
import { FaceEntry, FaceService, PendingFace } from '../../services/face.service';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink, Routes } from "@angular/router";
import { HttpClient } from '@angular/common/http';
import { PersonInformationComponent } from "../person-information/person-information.component";

@Component({
  selector: 'app-face-log',
  standalone: true,
  imports: [CommonModule, FormsModule, PersonInformationComponent],
  templateUrl: './face-log.component.html',
  styleUrl: './face-log.component.css'
})
export class FaceLogComponent implements OnInit {
  faces: any[] = [];
  pending: (PendingFace & { tempName?: string })[ ] = [];
  loading = false;

  recognized: { person_id: number, name: string, images?: string[], avatar?: string }[] = [];

  newName: { [faceId: string]: string } = {};
  editName: { [key: number]: string } = {};

  editingPerson: any = null;

  constructor(
    private faceService: FaceService,
    private router: Router,
    private http: HttpClient,
    private route: ActivatedRoute
  ) {}

  ngOnInit(): void {
    this.loadFaces();
    // this.loadPending();
    this.loadPersons();
    setInterval(() => this.loadPending(), 5000);
  }

  loadFaces() {
    this.faceService.getFaces().subscribe(data => {
      this.faces = data;
      this.groupFacesByName();
    });
  }

  loadPending() {
    this.faceService.getPendingFaces().subscribe({
      next: (data) => {
        this.pending = data;
      },
      error: (err) => console.error("Load pending faces error:", err)
    });
  }

  assignName(pendingId: string) {
    const pending = this.pending.find(x => x.id === pendingId);
    if (!pending || !pending.tempName) return;
    this.faceService.assignPendingFace(pending.id, pending.tempName).subscribe({
      next: (res) => {
        console.log("Gán tên thành công:", res);
        this.loadFaces();
        this.loadPending();
        this.loadPersons();
        setTimeout(() => this.loadPersons(), 500)
      },
      error: (err) => console.error("Gán tên thất bại:", err)
    });
  }

  loadPersons(){
    this.faceService.getPerson().subscribe(data => {
      this.faceService.getFaces().subscribe( faces =>{
        const facesMap = new Map(faces.map( f => [f.person_id, f] ));
        this.recognized = data.map(person => ({
          person_id: person.person_id,
          name: person.name,
          avatar: person.avatar || (facesMap.get(person.person_id)?.image || null),
          images: []
        }));
      });
    });
  }
  updateName(employeeId: number) {
    const name = this.editName[employeeId];
    if (!name) return;

    this.faceService.updateFaceName(employeeId, name).subscribe(() => {
      this.recognized = this.recognized.map(r =>
        r.person_id === employeeId ? { ...r, name } : r
      );
      this.editName[employeeId] = '';
    });
  }

  openEdit(person: any) {
    this.editingPerson = { ...person };
  }

  closeEdit() {
    this.editingPerson = null;
  }

  refreshData() {
    this.loadFaces();
  }

  deleteFace(person_id: number) {
    if (!confirm("Bạn có chắc chắn muốn xóa nhân viên này và toàn bộ ảnh liên quan?"))
      return;
    this.faceService.deletePerson(person_id).subscribe({
      next: () => {
        this.faces = this.faces.filter(f => f.person_id !== person_id);
        this.recognized = this.recognized.filter(r => r.person_id !== person_id);

        if (this.editingPerson && this.editingPerson.person_id === person_id) {
          this.editingPerson = null;
        }
      },
      error: (err) => {
        console.error("Xóa nhân viên thất bại:", err);
        alert("Xóa thất bại. Kiểm tra console server để biết lỗi.");
      }
    });
  }

  deleteLearnedFace(faceId: number) {
    if (!confirm("Bạn có chắc chắn muốn xóa gương mặt này không?")) return;
    this.faceService.deleteFace(faceId).subscribe({
      next: () => {
        this.faces = this.faces.filter(f => f.id !== faceId);
        this.groupFacesByName();
      },
      error: (err) => {
        console.error("Lỗi xóa face:", err);
        alert("Xóa gương mặt thất bại. Kiểm tra console để biết chi tiết.");
      }
    });
  }

  deletePendingFace(pendingId: string) {
    if (!confirm("Bạn có chắc chắn muốn xóa gương mặt chờ này?")) return;
    this.faceService.deletePendingFace(pendingId).subscribe(() => this.loadPending());
  }

  getVideoFeedUrl(): string {
    return this.faceService.getVideoFeedUrl();
  }

  private groupFacesByName() {
    const grouped: { [id: number]: { person_id: number, name: string, images: string[], avatar?: string } } = {};

    this.faces.forEach(f => {
      if (!grouped[f.person_id]) {
        grouped[f.person_id] = {
          person_id: f.person_id,
          name: f.name,
          images: [],
          avatar: f.avatar || null
        };
      }

      if (f.image && !grouped[f.person_id].images.includes(f.image)) {
        grouped[f.person_id].images.push(f.image);
      }

      // nếu chưa có avatar thì set ảnh đầu tiên
      if (!grouped[f.person_id].avatar && f.image) {
        grouped[f.person_id].avatar = f.image;
      }
    });
    this.recognized = Object.values(grouped);
  }

  setAvatar(personId: number, img: string) {
    this.faceService.updateAvatar(personId, img).subscribe({
      next: () => {
        this.recognized = this.recognized.map(r =>
          r.person_id === personId ? { ...r, avatar: img } : r
        );
        alert("✅ Đã đặt ảnh làm avatar chính");
      },
      error: (err) => console.error("Lỗi cập nhật avatar:", err)
    });
  }

  trackByFaceId(index: number, item: PendingFace): string {
    return item.id;
  }

  goToPersonDetail(personId: number) {
    this.router.navigate(['/persons-list', personId]);
  }
}
