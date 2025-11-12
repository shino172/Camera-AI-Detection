import { ComponentFixture, TestBed } from '@angular/core/testing';

import { AdminPermissionComponent } from './admin-permission.component';

describe('AdminPermissionComponent', () => {
  let component: AdminPermissionComponent;
  let fixture: ComponentFixture<AdminPermissionComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AdminPermissionComponent]
    })
    .compileComponents();
    
    fixture = TestBed.createComponent(AdminPermissionComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
