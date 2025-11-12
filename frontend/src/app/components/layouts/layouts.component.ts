import { Component } from '@angular/core';
import { RouterModule } from "@angular/router";
import { HeaderComponent } from "../header/header.component";
import { FooterComponent } from "../footer/footer.component";
import { EventListComponent } from '../event-list/event-list.component';

@Component({
  selector: 'app-layouts',
  standalone: true,
  imports: [
    RouterModule,
    HeaderComponent
  ],
  templateUrl: './layouts.component.html',
  styleUrl: './layouts.component.css'
})
export class LayoutsComponent {

}
