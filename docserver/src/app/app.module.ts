import { BrowserModule } from '@angular/platform-browser';
import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import {HttpClientModule } from '@angular/common/http';

import { AppComponent } from './app.component';
import { AppService } from './app.service';
import { ModuleListComponent } from './module-list/module-list.component';
import { ModuleDetailsComponent } from './module-details/module-details.component';


const appRoutes: Routes = [
  { path: 'modules',
    component: ModuleListComponent,
  },
  { path: 'modules/:id',
    component: ModuleDetailsComponent
  },
  { path: '',
    redirectTo: '/modules',
    pathMatch: 'full'
  }
]
@NgModule({
  declarations: [
    AppComponent,
    ModuleListComponent,
    ModuleDetailsComponent
  ],
  imports: [
    BrowserModule,
    HttpClientModule,
    RouterModule.forRoot(
      appRoutes
    )
  ],
  providers: [ AppService ],
  bootstrap: [AppComponent]
})
export class AppModule { }
