#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, math, os, sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
@dataclass
class Thresholds: max_lock_acquisition_s: float; min_lock_hold_ratio: float; max_dropout_count: int; max_dropout_gap_s: float; lock_quality_percentile: float; min_lock_quality_at_percentile: float
@dataclass
class ComputedMetrics: lock_acquisition_s: float|None; lock_hold_ratio: float; dropout_count: int; max_dropout_gap_s: float; lock_quality_percentile_value: float|None; lock_quality_samples: int

def _envf(n,d):
    v=os.getenv(n); return d if v is None else float(v)
def _envi(n,d):
    v=os.getenv(n); return d if v is None else int(v)
def _as_float(v):
    try:return None if v is None else float(v)
    except: return None

def parse_args(argv):
    p=argparse.ArgumentParser()
    p.add_argument("--mode",choices=["scenario-only","full-pipeline"],default=os.getenv("VISION_LOCK_CHECK_MODE","full-pipeline"))
    p.add_argument("--tracks-jsonl",type=Path,default=Path(os.getenv("VISION_LOCK_TRACKS_JSONL","artifacts/intercept_tracker_tracks.jsonl")))
    p.add_argument("--events-jsonl",type=Path,default=Path(os.getenv("VISION_LOCK_EVENTS_JSONL","artifacts/intercept_tracker_events.jsonl")))
    p.add_argument("--scenario-summary-json",type=Path,default=Path(os.getenv("VISION_LOCK_SCENARIO_SUMMARY_JSON","artifacts/vision_lock_static_summary.json")))
    p.add_argument("--max-lock-acquisition-s",type=float,default=_envf("VISION_LOCK_MAX_ACQUISITION_S",6.0)); p.add_argument("--min-lock-hold-ratio",type=float,default=_envf("VISION_LOCK_MIN_HOLD_RATIO",0.85)); p.add_argument("--max-dropout-count",type=int,default=_envi("VISION_LOCK_MAX_DROPOUT_COUNT",2)); p.add_argument("--max-dropout-gap-s",type=float,default=_envf("VISION_LOCK_MAX_DROPOUT_GAP_S",1.0)); p.add_argument("--lock-quality-percentile",type=float,default=_envf("VISION_LOCK_QUALITY_PERCENTILE",10.0)); p.add_argument("--min-lock-quality-at-percentile",type=float,default=_envf("VISION_LOCK_MIN_QUALITY_AT_PERCENTILE",0.65))
    p.add_argument("--consistency-lock-s-tol",type=float,default=_envf("VISION_LOCK_CONSISTENCY_LOCK_S_TOL",0.30)); p.add_argument("--consistency-hold-ratio-tol",type=float,default=_envf("VISION_LOCK_CONSISTENCY_HOLD_RATIO_TOL",0.05)); p.add_argument("--consistency-dropout-gap-s-tol",type=float,default=_envf("VISION_LOCK_CONSISTENCY_DROPOUT_GAP_S_TOL",0.30)); p.add_argument("--consistency-strict",action="store_true",default=os.getenv("VISION_LOCK_CONSISTENCY_STRICT","1")=="1")
    return p.parse_args(argv)

def _loadj(p): return json.loads(p.read_text())
def _loadjl(p): return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
def _pct(vals,p):
    vals=sorted(vals); 
    if not vals: return None
    if len(vals)==1:return vals[0]
    r=(p/100)*(len(vals)-1); lo=math.floor(r); hi=math.ceil(r); w=r-lo; return vals[lo]*(1-w)+vals[hi]*w

def metrics_from_tracks(tracks, pct):
    first=None; first_lock=None; total=locked=0; dcnt=0; dmax=0.0; in_d=False; dstart=None; q=[]
    for row in tracks:
        ts=_as_float(row.get("timestamp"));
        if ts is None: continue
        if first is None: first=ts
        state=str(row.get("lock_state",""))
        if state=="LOCKED" and first_lock is None: first_lock=ts
        if state=="LOCKED":
            v=_as_float(row.get("lock_quality"));
            if v is not None:q.append(v)
        if first_lock is None: continue
        total+=1
        if state=="LOCKED":
            locked+=1
            if in_d and dstart is not None: dmax=max(dmax,max(0.0,ts-dstart)); in_d=False; dstart=None
        elif not in_d:
            in_d=True; dstart=ts; dcnt+=1
    if in_d and dstart is not None and tracks:
        t=_as_float(tracks[-1].get("timestamp"));
        if t is not None:dmax=max(dmax,max(0.0,t-dstart))
    acq=None if first is None or first_lock is None else max(0.0, first_lock-first)
    return ComputedMetrics(acq, 0.0 if total==0 else locked/total, dcnt, dmax, _pct(q,pct), len(q))

def eval_fail(m,t,s):
    f=[]; st=str(s.get("status","")).lower().strip()
    if st and st!="success": f.append(f"scenario status is {st!r}")
    if m.lock_acquisition_s is None or m.lock_acquisition_s>t.max_lock_acquisition_s: f.append("lock acquisition threshold failed")
    if m.lock_hold_ratio<t.min_lock_hold_ratio: f.append("lock hold ratio too low")
    if m.dropout_count>t.max_dropout_count: f.append("dropout count too high")
    if m.max_dropout_gap_s>t.max_dropout_gap_s: f.append("dropout gap too long")
    if m.lock_quality_percentile_value is None or m.lock_quality_percentile_value<t.min_lock_quality_at_percentile: f.append("lock quality percentile too low")
    return f

def main(argv):
    a=parse_args(argv); t=Thresholds(a.max_lock_acquisition_s,a.min_lock_hold_ratio,a.max_dropout_count,a.max_dropout_gap_s,a.lock_quality_percentile,a.min_lock_quality_at_percentile)
    req=[a.scenario_summary_json] + ([] if a.mode=="scenario-only" else [a.tracks_jsonl,a.events_jsonl])
    miss=[str(p) for p in req if not p.exists()]
    if miss: print("[vision-lock-check] error: missing artifacts\n  - "+"\n  - ".join(miss)); return 2
    s=_loadj(a.scenario_summary_json); tracks=[] if a.mode=="scenario-only" else _loadjl(a.tracks_jsonl)
    m = ComputedMetrics(_as_float(s.get("time_to_lock_s_scenario_estimate")), _as_float(s.get("lock_hold_ratio_scenario_estimate")) or 0.0,0,_as_float(s.get("max_gap_s_scenario_estimate")) or 0.0,None,0) if a.mode=="scenario-only" else metrics_from_tracks(tracks,a.lock_quality_percentile)
    print("[vision-lock-check] computed metrics:")
    print(f"  checker_mode: {a.mode}"); print(f"  lock_acquisition_s: {m.lock_acquisition_s}"); print(f"  lock_hold_ratio: {m.lock_hold_ratio:.4f}"); print(f"  dropout_count: {m.dropout_count}"); print(f"  max_dropout_gap_s: {m.max_dropout_gap_s:.3f}")
    if a.mode=="full-pipeline":
      print("[vision-lock-check] consistency_check:")
      deltas=[]
      for key,tol in [("time_to_lock_s_scenario_estimate",a.consistency_lock_s_tol),("lock_hold_ratio_scenario_estimate",a.consistency_hold_ratio_tol),("max_gap_s_scenario_estimate",a.consistency_dropout_gap_s_tol)]:
        sv=_as_float(s.get(key)); mv={"time_to_lock_s_scenario_estimate":m.lock_acquisition_s,"lock_hold_ratio_scenario_estimate":m.lock_hold_ratio,"max_gap_s_scenario_estimate":m.max_dropout_gap_s}[key]
        if sv is None or mv is None: continue
        d=abs(sv-mv); deltas.append((key,d,tol))
        status="PASS" if d<=tol else ("FAIL" if a.consistency_strict else "WARN")
        print(f"  {key}: scenario={sv} stream={mv} delta={d:.4f} tol={tol:.4f} => {status}")
      bad=[x for x in deltas if x[1]>x[2]]
      print(f"  consistency_result: {'PASS' if not bad else ('FAIL' if a.consistency_strict else 'WARN')}")
    fails=eval_fail(m,t,s)
    if a.mode=="full-pipeline" and a.consistency_strict and any(abs((_as_float(s.get(k)) or 0)-v)>tol for k,v,tol in [("time_to_lock_s_scenario_estimate",m.lock_acquisition_s or 0,a.consistency_lock_s_tol),("lock_hold_ratio_scenario_estimate",m.lock_hold_ratio,a.consistency_hold_ratio_tol),("max_gap_s_scenario_estimate",m.max_dropout_gap_s,a.consistency_dropout_gap_s_tol)] if _as_float(s.get(k)) is not None):
      fails.append("consistency check divergence exceeded tolerance")
    if a.mode=="scenario-only": fails=[x for x in fails if "quality" not in x and "dropout count" not in x]
    if fails:
      print("[vision-lock-check] FAIL"); [print(f"  - {x}") for x in fails]; return 1
    print("[vision-lock-check] PASS"); return 0
if __name__=='__main__': raise SystemExit(main(sys.argv[1:]))
