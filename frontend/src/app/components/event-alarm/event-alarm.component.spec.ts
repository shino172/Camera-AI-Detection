import { ComponentFixture, TestBed } from '@angular/core/testing';

import { EventAlarmComponent } from './event-alarm.component';

describe('EventAlarmComponent', () => {
  let component: EventAlarmComponent;
  let fixture: ComponentFixture<EventAlarmComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [EventAlarmComponent]
    })
    .compileComponents();
    
    fixture = TestBed.createComponent(EventAlarmComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
