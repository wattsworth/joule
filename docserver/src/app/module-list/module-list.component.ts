import { Component, OnInit } from '@angular/core';
import {Observable} from 'rxjs';

import {AppService, ModuleInfo} from '../app.service';

@Component({
  selector: 'app-module-list',
  templateUrl: './module-list.component.html',
  styleUrls: ['./module-list.component.css']
})
export class ModuleListComponent implements OnInit {

  constructor(public service: AppService) { }
  public modules: Observable<ModuleInfo[]>

  ngOnInit() {
    this.modules = this.service.getModules();
  }

}
