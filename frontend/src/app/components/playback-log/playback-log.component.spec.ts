import { ComponentFixture, TestBed } from '@angular/core/testing';

import { PlaybackLogComponent } from './playback-log.component';

describe('PlaybackLogComponent', () => {
  let component: PlaybackLogComponent;
  let fixture: ComponentFixture<PlaybackLogComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [PlaybackLogComponent]
    })
    .compileComponents();
    
    fixture = TestBed.createComponent(PlaybackLogComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
