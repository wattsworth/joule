import { Component, OnInit } from '@angular/core';
import {ActivatedRoute} from '@angular/router';
import {Location} from '@angular/common';
import {AppService, ModuleInfo} from '../app.service';
import {Observable} from 'rxjs';
import 'rxjs/add/operator/mergeMap';

@Component({
  selector: 'app-module-details',
  templateUrl: './module-details.component.html',
  styleUrls: ['./module-details.component.css']
})
export class ModuleDetailsComponent implements OnInit {

  public module: Observable<ModuleInfo>;

  constructor(
    private route: ActivatedRoute,
    private appService: AppService,
    private location: Location
  ) {
    this.module = null;
   }

  ngOnInit() {
    this.module = this.route.params.flatMap(params => {
      return this.appService.getModule(+params["id"]);
    })
  }
 
 
}
