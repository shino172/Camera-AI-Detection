import { ComponentFixture, TestBed } from '@angular/core/testing';

import { FaceLogComponent } from './face-log.component';

describe('FaceLogComponent', () => {
  let component: FaceLogComponent;
  let fixture: ComponentFixture<FaceLogComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [FaceLogComponent]
    })
    .compileComponents();
    
    fixture = TestBed.createComponent(FaceLogComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
