import { ComponentFixture, TestBed } from '@angular/core/testing';

import { PlayBackFeedComponent } from './play-back-feed.component';

describe('PlayBackFeedComponent', () => {
  let component: PlayBackFeedComponent;
  let fixture: ComponentFixture<PlayBackFeedComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [PlayBackFeedComponent]
    })
    .compileComponents();
    
    fixture = TestBed.createComponent(PlayBackFeedComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
