import { ComponentFixture, TestBed } from '@angular/core/testing';

import { LogFileComponent } from './log-file.component';

describe('LogFileComponent', () => {
  let component: LogFileComponent;
  let fixture: ComponentFixture<LogFileComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [LogFileComponent]
    })
    .compileComponents();
    
    fixture = TestBed.createComponent(LogFileComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
