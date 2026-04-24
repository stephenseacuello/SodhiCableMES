#!/usr/bin/env python3
"""SodhiCable MES v4.0 — Seed Data Generator for event/reading tables."""
import random, math
from datetime import datetime, timedelta
random.seed(42)
BASE = datetime(2026, 4, 1)
def dt(d): return d.strftime("%Y-%m-%d %H:%M:%S")
def dd(d): return d.strftime("%Y-%m-%d")

def gen_spc():
    lines = []
    mu, sigma, usl, lsl = 0.0253, 0.0003, 0.0262, 0.0244
    ucl, lcl = mu+3*sigma, mu-3*sigma
    for i in range(120):
        sg = i//5+1; t = BASE+timedelta(hours=i*0.5)
        m = mu + (0.0003 if 60<=i<80 else 0.0012 if i==42 else 0.0007 if 85<=i<=87 else 0)
        v = round(random.gauss(m, sigma), 5)
        s = "OOC" if v>usl or v<lsl else "Warning" if v>mu+2*sigma or v<mu-2*sigma else "OK"
        r = "Rule1_BeyondLimit" if s=="OOC" else "None"
        lines.append(f"INSERT INTO spc_readings (wo_id,wc_id,measurement_date,parameter_name,measured_value,subgroup_id,usl,lsl,ucl,cl,lcl,rule_violation,status) VALUES ('WO-2026-002','DRAW-1','{dt(t)}','WireDiameter_in',{v},{sg},{usl},{lsl},{ucl:.5f},{mu},{lcl:.5f},'{r}','{s}');")
    for i in range(60):
        t = BASE+timedelta(hours=i)
        v = round(random.gauss(0.032, 0.001), 4)
        s = "OK" if abs(v-0.032)<0.003 else "OOC"
        lines.append(f"INSERT INTO spc_readings (wo_id,wc_id,measurement_date,parameter_name,measured_value,subgroup_id,usl,lsl,status) VALUES ('WO-2026-007','CV-1','{dt(t)}','InsulationThickness_in',{v},{i//5+1},0.035,0.029,'{s}');")
    return "\n".join(lines)

def gen_spark():
    lines = []
    reels = [f"R-{4500+i}" for i in range(50)]
    wos = ["WO-2026-002","WO-2026-003","WO-2026-005","WO-2026-007"]
    for i in range(80):
        t = BASE+timedelta(hours=i*2, minutes=random.randint(0,59))
        v = round(random.uniform(2.5,4.0),2)
        if i in [23,35,47,61]:
            lines.append(f"INSERT INTO spark_test_log (reel_id,wo_id,wc_id,footage_at_fault_ft,voltage_kv,result,timestamp) VALUES ('{reels[i%50]}','{wos[i%4]}','TEST-1',{round(random.uniform(1200,1400),1)},{v},'FAIL','{dt(t)}');")
        else:
            lines.append(f"INSERT INTO spark_test_log (reel_id,wo_id,wc_id,footage_at_fault_ft,voltage_kv,result,timestamp) VALUES ('{reels[i%50]}','{wos[i%4]}','TEST-1',NULL,{v},'PASS','{dt(t)}');")
    return "\n".join(lines)

def gen_downtime():
    lines = []; cats = [("Breakdown",10,30,180),("Setup",10,15,90),("MaterialWait",5,10,90),("QualityHold",4,10,60),("PM",5,30,120),("NoOrders",3,15,60),("Other",3,10,45)]
    causes = {"Breakdown":["Motor failure","Belt snap","Sensor fault","Drawing die wear","Bearing seizure"],"Setup":["Product changeover","Die change","Color change"],"MaterialWait":["Copper rod delayed","Compound shortage"],"QualityHold":["Spark test fail","Diameter OOS"],"PM":["Calibration","Lubrication"],"NoOrders":["No orders"],"Other":["Training","Safety meeting"]}
    wcs = ["DRAW-1","CV-1","CV-2","BRAID-1","CABLE-1","PLCV-1","TEST-1","ARMOR-1"]
    for cat,cnt,mn,mx in cats:
        for j in range(cnt):
            wc = "DRAW-1" if cat=="Breakdown" and j<4 else random.choice(wcs)
            s = BASE+timedelta(days=random.randint(0,14),hours=random.randint(6,22)); dur=random.randint(mn,mx); e=s+timedelta(minutes=dur)
            lines.append(f"INSERT INTO downtime_log (wc_id,start_time,end_time,duration_min,category,cause) VALUES ('{wc}','{dt(s)}','{dt(e)}',{dur},'{cat}','{random.choice(causes[cat])}');")
    return "\n".join(lines)

def gen_process():
    lines = []
    for i in range(200):
        t = BASE+timedelta(minutes=i*5)
        m = 375.0+(i-120)*0.05 if 120<=i<=160 else 383.0 if i==95 else 375.0
        v = round(random.gauss(m,2.0),1)
        lines.append(f"INSERT INTO process_data_live (wc_id,parameter,value,timestamp) VALUES ('CV-1','Temperature_F',{v},'{dt(t)}');")
    for i in range(100):
        t = BASE+timedelta(minutes=i*10); v=round(random.gauss(3000,50))
        lines.append(f"INSERT INTO process_data_live (wc_id,parameter,value,timestamp) VALUES ('CV-2','LineSpeed_fpm',{v},'{dt(t)}');")
    for i in range(100):
        t = BASE+timedelta(minutes=i*8); v=round(random.gauss(45,3),1)
        lines.append(f"INSERT INTO process_data_live (wc_id,parameter,value,timestamp) VALUES ('DRAW-1','Tension_lbf',{v},'{dt(t)}');")
    return "\n".join(lines)

def gen_lots():
    lines = []
    compounds = [("CB-0330","MAT-001","WO-2026-002"),("CB-0331","MAT-001","WO-2026-003"),("CB-0332","MAT-004","WO-2026-007"),("CB-0333","MAT-005","WO-2026-004"),("CB-0334","MAT-006","WO-2026-005")]
    for out,mat,wo in compounds:
        t = BASE+timedelta(hours=random.randint(0,48))
        lines.append(f"INSERT INTO lot_tracking (output_lot,input_lot,input_material_id,wo_id,qty_consumed,uom,tier_level,transaction_time) VALUES ('{out}','{mat}','{mat}','{wo}',{random.randint(100,500)},'kg','MTS-L1','{dt(t)}');")
    for wl in ["WL-0330-A","WL-0330-B","WL-0330-C","WL-0330-D","WL-0330-E"]:
        t = BASE+timedelta(hours=random.randint(24,72))
        lines.append(f"INSERT INTO lot_tracking (output_lot,input_lot,wo_id,qty_consumed,uom,tier_level,transaction_time) VALUES ('{wl}','CB-0330','WO-2026-002',{random.randint(50,200)},'kft','MTS-L2','{dt(t)}');")
    for i,(cb,_,wo) in enumerate(compounds[1:],1):
        for j in range(3):
            t = BASE+timedelta(hours=random.randint(24,96))
            lines.append(f"INSERT INTO lot_tracking (output_lot,input_lot,wo_id,qty_consumed,uom,tier_level,transaction_time) VALUES ('WL-{cb[3:]}-{chr(65+j)}','{cb}','{wo}',{random.randint(50,150)},'kft','MTS-L2','{dt(t)}');")
    for k,fl in enumerate(["FL-2026-001","FL-2026-002","FL-2026-003"]):
        t = BASE+timedelta(hours=random.randint(72,120))
        lines.append(f"INSERT INTO lot_tracking (output_lot,input_lot,wo_id,qty_consumed,uom,tier_level,transaction_time) VALUES ('{fl}','WL-0330-{chr(65+k)}','WO-2026-002',{random.randint(20,80)},'kft','MTO','{dt(t)}');")
    return "\n".join(lines)

def gen_scrap():
    lines = []; causes = [("STARTUP",8,100,800),("CHANGEOVER",6,50,300),("SPARK_FAULT",5,50,150),("OD_EXCURSION",5,50,150),("MATERIAL_DEFECT",3,50,300),("COMPOUND_BLEED",3,50,200)]
    wos = ["WO-2026-002","WO-2026-003","WO-2026-004","WO-2026-007","WO-2026-014"]
    wcs = ["DRAW-1","CV-1","CV-2","BRAID-1","CABLE-1","PLCV-1"]
    for cause,cnt,mn,mx in causes:
        for j in range(cnt):
            t = BASE+timedelta(days=random.randint(0,14),hours=random.randint(6,22))
            lines.append(f"INSERT INTO scrap_log (wo_id,wc_id,cause_code,quantity_ft,timestamp) VALUES ('{random.choice(wos)}','{random.choice(wcs)}','{cause}',{random.randint(mn,mx)},'{dt(t)}');")
    return "\n".join(lines)

def gen_events():
    lines = []; types = ["WO_Started","WO_Completed","Changeover","Alarm","Hold","Dispatch","SPC_OOC"]
    wcs = ["DRAW-1","CV-1","CV-2","BRAID-1","CABLE-1","PLCV-1","TEST-1"]
    wos = ["WO-2026-002","WO-2026-003","WO-2026-004","WO-2026-005","WO-2026-007","WO-2026-009","WO-2026-014","WO-2026-016"]
    for i in range(60):
        t = BASE+timedelta(hours=i*4,minutes=random.randint(0,59)); et=random.choice(types); wc=random.choice(wcs); wo=random.choice(wos)
        lines.append(f"INSERT INTO events (wo_id,wc_id,event_type,event_time,details) VALUES ('{wo}','{wc}','{et}','{dt(t)}','Event {i+1}: {et} on {wc}');")
    return "\n".join(lines)

def gen_env():
    lines = []; wcs=["CV-1","CV-2","PLCV-1","PX-1"]; shifts=["Day","Swing","Night"]
    for i in range(80):
        t = BASE+timedelta(hours=i*4); wc=wcs[i%4]
        temp = 195.0 if i==35 else round(random.gauss(175,8),1)
        hum = 72.0 if i==52 else round(random.gauss(45,10),1)
        s = "Alarm" if temp>190 or temp<160 else "Warning" if temp>185 or temp<165 or hum>60 or hum<30 else "OK"
        lines.append(f"INSERT INTO environmental_readings (wc_id,timestamp,temperature_f,humidity_pct,shift,status) VALUES ('{wc}','{dt(t)}',{temp},{hum},'{shifts[(i//8)%3]}','{s}');")
    return "\n".join(lines)

def gen_reels():
    lines = []; rts=["RT-24W","RT-36W","RT-48S","RT-30P","RT-DRUM"]; mx={"RT-24W":2500,"RT-36W":5000,"RT-48S":10000,"RT-30P":3000,"RT-DRUM":25000}
    prods=["INST-3C16-FBS","CTRL-2C12-XA","DHT-1C12-260","UL2196-2C14","IC-10AWG-THHN"]
    wos=["WO-2026-002","WO-2026-003","WO-2026-005","WO-2026-007","WO-2026-008"]
    for i in range(50):
        rt=rts[i%5]; r=random.random()
        if r<0.1: st,ft="Empty",0
        elif r<0.4: st="InUse"; ft=round(random.uniform(0.1,0.6)*mx[rt])
        elif r<0.7: st="Full"; ft=round(random.uniform(0.7,1.0)*mx[rt])
        elif r<0.9: st="Shipped"; ft=mx[rt]
        else: st="Returned"; ft=round(random.uniform(0.5,0.9)*mx[rt])
        t = BASE+timedelta(days=random.randint(-7,7))
        lines.append(f"INSERT INTO reel_inventory (reel_id,reel_type_id,wo_id,lot_id,product_id,footage_ft,status,created_date) VALUES ('R-{4500+i}','{rt}','{wos[i%5]}','LOT-{4500+i}','{prods[i%5]}',{ft},'{st}','{dd(t)}');")
    return "\n".join(lines)

def gen_shifts():
    lines = []; wcs=["CV-1","DRAW-1"]
    for day in range(7):
        d = BASE+timedelta(days=day)
        for wc in wcs:
            a=round(random.uniform(0.82,0.95),3); p=round(random.uniform(0.80,0.95),3); q=round(random.uniform(0.95,0.99),3); o=round(a*p*q,3)
            out=random.randint(2000,8000); scr=round(out*(1-q)); dt_min=round((1-a)*480)
            lines.append(f"INSERT INTO shift_reports (shift_date,shift_code,wc_id,oee_availability,oee_performance,oee_quality,oee_overall,total_output_ft,total_scrap_ft,total_downtime_min) VALUES ('{dd(d)}','Day','{wc}',{a},{p},{q},{o},{out},{int(scr)},{int(dt_min)});")
    return "\n".join(lines)

def generate_all():
    return "\n".join(["-- Generated seed data (seed=42)",gen_spc(),"",gen_spark(),"",gen_downtime(),"",gen_process(),"",gen_lots(),"",gen_scrap(),"",gen_events(),"",gen_env(),"",gen_reels(),"",gen_shifts()])

if __name__ == "__main__":
    print(generate_all())
