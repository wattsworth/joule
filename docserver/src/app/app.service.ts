
import {HttpClient} from '@angular/common/http';
import {Injectable} from '@angular/core';
import {Observable } from 'rxjs';
import { environment } from '../environments/environment';

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

  public getModules(): Observable<ModuleInfo[]>{
    if(this.dataLoaded){
      return Observable.of(this.data);
    }
    return this.http.get<ModuleInfo[]>(environment.dataURL)
      .do(data => {
        this.data = this.generateIDs(data);
        this.dataLoaded = true;
      });
  }
  public getModule(id: number): Observable<ModuleInfo>{
    if(this.dataLoaded){
      return Observable.of(_.find(this.data, {id: id}))
    }
    return this.http.get<ModuleInfo[]>(environment.dataURL)
      .do(data => {
        this.data = this.generateIDs(data);
        this.dataLoaded = true;
      })
      .map(data => _.find(this.data, {id: id}));
  }

  private generateIDs(data: ModuleInfo[]): ModuleInfo[]{
    let id = 0;
    return data.reduce( (r,m) => {
      m.id = id;
      id += 1;
      r.push(m);
      return r;
    },[])
  }
}

export interface ModuleInfo {
  id: number;
  name: string;
  author: string;
  license: string;
  url: string;
  description: string;
  inputs: string;
  outputs: string;
  usage: string;
  stream_configs: StreamConfig[];
  module_config: string;
}
export interface StreamConfig {
  name: string;
  config: string;
}