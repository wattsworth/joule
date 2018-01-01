
import {HttpClient} from '@angular/common/http';
import {Injectable} from '@angular/core';
import {Observable } from 'rxjs';
import 'rxjs/add/operator/do';
import 'rxjs/add/operator/map';

import * as _ from "lodash";

@Injectable()
export class AppService {

  public data: ModuleInfo[];
  private dataLoaded: Boolean;

  constructor(private http: HttpClient){
    this.dataLoaded = false;
  }

  public loadData(): void {
   
  }
  public getModules(): Observable<ModuleInfo[]>{
    if(this.dataLoaded){
      return Observable.of(this.data);
    }
    return this.http.get<ModuleInfo[]>('/assets/data.json')
      .do(data => {
        this.data = data;
        this.dataLoaded = true;
      });
  }
  public getModule(id: number): Observable<ModuleInfo>{
    if(this.dataLoaded){
      return Observable.of(_.find(this.data, {id: id}))
    }
    return this.http.get<ModuleInfo[]>('/assets/data.json')
      .do(data => {
        this.data = data;
        this.dataLoaded = true;
      })
      .map(data => _.find(this.data, {id: id}));
  }

}

export interface ModuleInfo {
  id: number;
  name: string;
  description: string;
  inputs: string;
  outputs: string;
  stream_configs: string[];
  module_config: string;

}