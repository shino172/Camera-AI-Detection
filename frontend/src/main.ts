import { bootstrapApplication, provideClientHydration } from '@angular/platform-browser';
import { appConfig } from './app/app.config';
import { AppComponent } from './app/app.component';
import { HttpClientModule, provideHttpClient } from '@angular/common/http';
import { EventService } from './app/services/event.service';
import { importProvidersFrom } from '@angular/core';
import { MatDialog } from '@angular/material/dialog';
import { provideAnimations } from '@angular/platform-browser/animations';
import { provideRouter } from '@angular/router';
import { routes } from './app/app.routes';

bootstrapApplication(AppComponent, {
    providers: [
      provideRouter(routes),
      // provideClientHydration(),
      importProvidersFrom(HttpClientModule),
      provideAnimations(),
      MatDialog,
      // MatSnackBar
    ]
})
  .catch((err) => console.error(err));
