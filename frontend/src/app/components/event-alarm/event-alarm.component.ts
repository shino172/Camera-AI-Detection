import { Component } from '@angular/core';
import { ConfigurationComponent } from "../configuration/configuration.component";
import { AlarmComponent } from "../alarm/alarm.component";
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-event-alarm',
  standalone: true,
  imports: [ConfigurationComponent, AlarmComponent, CommonModule],
  templateUrl: './event-alarm.component.html',
  styleUrl: './event-alarm.component.scss'
})
export class EventAlarmComponent {
  activeTab: 'config' | 'alarm' = 'config';

}
