import { ComponentFixture, TestBed } from '@angular/core/testing';

import { PersonInformationComponent } from './person-information.component';

describe('PersonInformationComponent', () => {
  let component: PersonInformationComponent;
  let fixture: ComponentFixture<PersonInformationComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [PersonInformationComponent]
    })
    .compileComponents();
    
    fixture = TestBed.createComponent(PersonInformationComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
