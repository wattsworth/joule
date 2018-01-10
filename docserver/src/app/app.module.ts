import { BrowserModule } from '@angular/platform-browser';
import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import {HttpClientModule } from '@angular/common/http';
import {NoopAnimationsModule } from '@angular/platform-browser/animations';
import {HighlightJsModule } from 'angular2-highlight-js';
import {MatTabsModule} from '@angular/material/tabs';
import { MatSidenavModule } from '@angular/material/sidenav';

import { AppComponent } from './app.component';
import { AppService } from './app.service';
import { ModuleListComponent } from './module-list/module-list.component';
import { ModuleDetailsComponent } from './module-details/module-details.component';
import { SafePipe } from './safe-pipe.pipe';


const appRoutes: Routes = [
  { path: ':id',
    component: ModuleDetailsComponent
  },
  { path: '',
    redirectTo: '0',
    pathMatch: 'full'
  },
  { path: '**',
  redirectTo: '0',
  pathMatch: 'full'
}
]
@NgModule({
  declarations: [
    AppComponent,
    ModuleListComponent,
    ModuleDetailsComponent,
    SafePipe
  ],
  imports: [
    BrowserModule,
    HttpClientModule,
    MatTabsModule,
    MatSidenavModule,
    NoopAnimationsModule,
    HighlightJsModule,
    RouterModule.forRoot(
      appRoutes
    )
  ],
  providers: [ AppService ],
  bootstrap: [AppComponent]
})
export class AppModule { }
