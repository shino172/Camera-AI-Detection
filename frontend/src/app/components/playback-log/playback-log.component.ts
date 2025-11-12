import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { PlayBackFeedComponent } from "../play-back-feed/play-back-feed.component";
import { LogFileComponent } from "../log-file/log-file.component";

@Component({
  selector: 'app-playback-log',
  standalone: true,
  imports: [CommonModule, PlayBackFeedComponent, LogFileComponent],
  templateUrl: './playback-log.component.html',
  styleUrl: './playback-log.component.scss'
})
export class PlaybackLogComponent {
  activeTab: 'playback' | 'log' = 'playback';

  setActiveTab(tab: 'playback' | 'log') {
    this.activeTab = tab;
  }
}
