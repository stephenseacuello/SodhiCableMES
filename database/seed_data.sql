-- SodhiCable MES v4.0 — Static Seed Data
-- 31 products, 25 WCs, 16 materials, 20 customers, 25 WOs, 34 personnel

-- PRODUCTS (31 across 9 families)
INSERT INTO products (product_id,name,family,description,conductors,awg,shield_type,jacket_type,armor_type,primary_bu,production_tier,revenue_per_kft,cost_per_kft,max_order_qty_kft) VALUES
('INST-3C16-FBS','3/C 16AWG Foil/Braid Shield PVC','A','Foil braid shielded instr',3,'16','85% Braid','PVC',NULL,'Industrial','MTS-L1',4.50,2.10,500),
('INST-3C16-TP','3/C 16AWG Shielded Twisted Pair','A','Shielded twisted pair',3,'16','Foil','PVC',NULL,'Industrial','MTS-L1',5.20,2.45,500),
('INST-6P22-OS','6-Pair 22AWG Overall Shield','A','Multi-pair overall shield',12,'22','Foil','PVC',NULL,'Infrastructure','MTS-L2',7.80,3.60,300),
('INST-12P22-OS','12-Pair 22AWG Overall Shield','A','Multi-pair overall shield',24,'22','90% Braid','PVC',NULL,'Defense','MTO',12.50,5.75,200),
('INST-2C18-FBS','2/C 18AWG Foil & Braid Shield','A','Foil braid shielded',2,'18','85% Braid','PVC',NULL,'Industrial','MTS-L1',6.30,2.85,400),
('CTRL-2C12-XA','2/C 12AWG XLPE Armored','B','XLPE armored control',2,'12',NULL,'XLPE','AIA','Infrastructure','MTS-L2',8.75,4.10,300),
('CTRL-4C12-XA','4/C 12AWG XLPE Armored','B','XLPE armored control',4,'12',NULL,'XLPE','AIA','Infrastructure','MTS-L2',12.25,5.60,250),
('CTRL-6C14-XA','6/C 14AWG XLPE Armored','B','XLPE armored control',6,'14',NULL,'XLPE','AIA','Infrastructure','MTS-L2',14.50,6.70,200),
('PWR-2/0-ARM','2/0 AWG Armored Power','B','Armored power cable',1,'2/0',NULL,'XLPE','AIA','Infrastructure','MTO',45.00,20.50,100),
('DHT-1C12-260','1/C 12AWG DHT 260C','C','Down hole 260C',1,'12',NULL,'FEP',NULL,'Oil & Gas','MTO',3.75,1.65,400),
('DHT-2C12-H2S','2/C 12AWG DHT H2S/CO2','C','H2S resistant down hole',2,'12',NULL,'FEP',NULL,'Oil & Gas','MTO',5.50,2.40,300),
('DHT-3C10-ESP','3/C 10AWG DHT ESP','C','ESP down hole',3,'10',NULL,'ETFE',NULL,'Oil & Gas','MTO',8.25,3.70,250),
('DHT-FP-FEP','DHT FlatPack 3-Tube FEP','C','FlatPack down hole',3,'12',NULL,'FEP',NULL,'Oil & Gas','MTO',15.75,7.10,150),
('LSOH-3C12-SB','3/C 12AWG LSOH Shipboard','S','Low smoke shipboard',3,'12',NULL,'LSOH',NULL,'Defense','MTO',9.50,4.60,200),
('LSOH-7C14-SB','7/C 14AWG LSOH Shipboard','S','Low smoke shipboard',7,'14',NULL,'LSOH',NULL,'Defense','MTO',13.75,6.50,150),
('SB-FIBER-4SM','4-Fiber Shipboard SM','S','Shipboard single mode fiber',4,NULL,NULL,NULL,NULL,'Defense','MTO',2.85,1.40,10000),
('FIBER-SM-FEP','SM Fiber w/ FEP Buffer','S','SM fiber FEP buffered',1,NULL,NULL,'FEP',NULL,'Defense','MTO',0.95,0.45,15000),
('UL2196-2C14','UL2196 2/C 14AWG','U','UL 2196 fire rated',2,'14',NULL,'PVC',NULL,'Infrastructure','MTS-L1',4.85,2.30,400),
('UL2196-6C10','UL2196 6/C 10AWG','U','UL 2196 fire rated',6,'10',NULL,'PVC',NULL,'Infrastructure','MTS-L2',8.90,4.20,200),
('UL2196-4C2-4C10','UL2196 Combo 4/C 2+10','U','UL 2196 combo fire rated',8,'10',NULL,'PVC',NULL,'Infrastructure','MTO',22.50,10.80,100),
('UL2196-4C12','UL2196 4/C 12AWG','U','UL 2196 fire rated',4,'12',NULL,'PVC',NULL,'Infrastructure','MTS-L1',5.75,2.80,2500),
('RHW2-2AWG','RHW-2 Single Conductor','R','RHW-2 building wire',1,'2',NULL,'XLPE',NULL,'Industrial','MTS-L1',1.95,0.90,15000),
('IC-10AWG-THHN','THHN 10AWG Building Wire','R','THHN building wire',1,'10',NULL,'Nylon',NULL,'Industrial','MTS-L1',0.65,0.28,50000),
('SOOW-4C12','SOOW 4/C 12AWG Portable','R','Portable cord',4,'12',NULL,'XLPE',NULL,'Industrial','MTS-L1',2.25,1.05,10000),
('MC-12-2','MC Cable 12/2 Aluminum Armor','R','MC cable',2,'12',NULL,'PVC','AIA','Industrial','MTS-L1',3.10,1.50,10000),
('TRAY-3C10','Tray Cable 3/C 10AWG','R','Tray cable',3,'10',NULL,'PVC',NULL,'Industrial','MTS-L1',2.75,1.30,10000),
('IC-12AWG-XLPE','12AWG XLPE 90C','I','Insulated conductor',1,'12',NULL,'XLPE',NULL,'Industrial','MTS-L1',0.45,0.18,50000),
('IC-2AWG-XLPE','2AWG XLPE 90C','I','Insulated conductor',1,'2',NULL,'XLPE',NULL,'Industrial','MTS-L1',1.20,0.55,20000),
('IC-6AWG-XLPE','6AWG XLPE 90C','I','Insulated conductor',1,'6',NULL,'XLPE',NULL,'Industrial','MTS-L1',0.75,0.32,30000),
('DHT-FP-3T','DHT FlatPack 3-Tube FEP/ETFE','D','FlatPack FEP/ETFE',3,'12',NULL,'FEP',NULL,'Oil & Gas','MTO',45.00,22.00,3000),
('MV105-500MCM','MV105 500MCM Triple Layer','M','Medium voltage cable',1,'500MCM',NULL,'XLPE',NULL,'Infrastructure','MTO',18.50,9.25,1000),
('BARE-4-0','Bare Copper 4/0 AWG','I','Bare copper conductor',1,'4/0',NULL,NULL,NULL,'Industrial','MTS-L1',8.50,4.25,5000),
('TUBE-SM-WELD','SM Fiber Welded Tube Assembly','D','Welded tube fiber assembly',1,NULL,NULL,'FEP',NULL,'Oil & Gas','MTO',8.50,4.00,5000);

-- WORK CENTERS (25)
INSERT INTO work_centers (wc_id,name,wc_type,num_parallel,capacity_hrs_per_week,capacity_ft_per_hr,utilization_target,setup_time_min,cost_per_hr,manning) VALUES
('COMPOUND-1','Compounding (Banbury)','Compound',1,120,800,0.75,45,95,2),
('COMPOUND-2','Compounding Line 2','Compound',1,120,600,0.75,45,95,2),
('DRAW-1','Drawing Machine 1','Draw',1,120,5000,0.85,30,85,1),
('STRAND-1','Stranding Machine (7-61 wire)','Strand',1,120,3000,0.80,25,90,1),
('CV-1','CV Extrusion Line 1','CV',1,120,400,0.80,90,110,2),
('CV-2','CV Extrusion Line 2','CV',1,120,3000,0.80,75,110,2),
('CV-3','CV Extrusion Line 3','CV',1,120,300,0.80,75,110,2),
('FOIL-1','Foil Shield Application','Foil',1,120,600,0.78,20,75,1),
('TAPE-1','Tape Machine 1','Tape',1,120,700,0.82,15,70,1),
('BRAID-1','Braiding Machine 1 (16)','Braid',1,120,200,0.85,30,80,1),
('BRAID-2','Braiding Machine 2 (24)','Braid',1,120,250,0.85,30,80,1),
('BRAID-3','Braiding Machine 3 (36)','Braid',1,120,300,0.85,30,80,1),
('CABLE-1','Cabling Machine 1 (2-19)','Cable',1,120,350,0.88,25,90,1),
('CABLE-2','Cabling Machine 2 (19-37)','Cable',1,120,300,0.88,25,90,1),
('PLCV-1','Pressurized Liquid Continuous Vulcanization','Jacket',1,120,500,0.85,40,100,2),
('LPML-1','Large Poly Mold Line','Jacket',1,120,400,0.75,30,90,1),
('PX-1','Plastisol Extruder FEP/ETFE','Jacket',1,120,250,0.80,60,120,2),
('ARMOR-1','Armoring Line AIA','Armor',1,120,350,0.82,35,85,1),
('CCCW-1','Copper Continuously Corrugated Welding','CCCW',1,120,300,0.82,30,80,1),
('PT-1','Fiber Extrusion','PT',1,120,1000,0.70,20,95,1),
('COMB-1','Combine Station','Combine',1,120,400,0.80,20,75,1),
('TEST-1','Testing Lab 1','Test',2,120,NULL,0.65,10,90,2),
('TEST-2','Testing Lab 2','Test',1,120,NULL,0.65,10,90,1),
('CUT-1','Cutting Station 1','Cut',1,120,1500,0.90,10,65,1),
('PACK-1','Packaging','Pack',1,120,NULL,0.90,5,55,2),
('NJ-EXT','External NJ Welded Tube','External',1,80,100,0.50,120,150,1);

-- MATERIALS (16)
INSERT INTO materials (material_id,name,material_type,uom,unit_cost,lead_time_days,safety_stock_qty,supplier,tier) VALUES
('MAT-001','Copper Rod 14mm','Raw','kg',8.50,7,500,'Southern Copper','Tier 1'),
('MAT-002','Copper Rod 8mm','Raw','kg',9.00,7,300,'Southern Copper','Tier 1'),
('MAT-003','Tin Plating Solution','Raw','L',12.00,10,50,'ChemSupply Inc','Tier 2'),
('MAT-004','PVC Compound','Compound','kg',3.20,5,300,'PolyOne Corp','Tier 1'),
('MAT-005','XLPE Compound','Compound','kg',4.75,7,250,'Borealis','Tier 1'),
('MAT-006','FEP Compound','Compound','kg',12.50,10,150,'Chemours','Tier 1'),
('MAT-007','ETFE Compound','Compound','kg',15.00,10,100,'Chemours','Tier 1'),
('MAT-008','Steel Braid Wire','Component','kg',5.50,5,200,'Bekaert','Tier 1'),
('MAT-009','Steel Armor Strip','Component','kg',4.80,7,400,'ArcelorMittal','Tier 1'),
('MAT-010','Aluminum Foil 6um','Component','roll',22.00,3,50,'Novelis','Tier 2'),
('MAT-011','Mylar Tape','Component','roll',15.50,4,75,'DuPont','Tier 2'),
('MAT-012','Tinned Cu Drain Wire','Component','kg',11.20,5,100,'Southwire','Tier 1'),
('MAT-013','Paper Wrap','Consumable','kg',2.10,3,200,'Georgia-Pacific','Tier 3'),
('MAT-014','Polyester Tape','Component','roll',8.75,4,100,'DuPont','Tier 2'),
('MAT-015','Nylon Jacket Compound','Compound','kg',6.50,6,250,'BASF','Tier 1'),
('MAT-016','LSOH Compound','Compound','kg',5.80,7,200,'PolyOne Corp','Tier 1');

-- CUSTOMERS (20)
INSERT INTO customers (customer_id,customer_name,business_unit,contract_type,quality_level,contact) VALUES
('CUST-001','NAVSEA Washington','Defense','Government','MIL-Spec','J. Patterson'),
('CUST-002','General Dynamics','Defense','Government','MIL-Spec','R. Chen'),
('CUST-003','Raytheon Technologies','Defense','Government','MIL-Spec','S. Kumar'),
('CUST-004','Huntington Ingalls','Defense','Government','MIL-Spec','M. Johnson'),
('CUST-005','L3Harris Technologies','Defense','Government','MIL-Spec','A. Williams'),
('CUST-006','National Grid','Infrastructure','Commercial','UL-Listed','T. Brown'),
('CUST-007','Duke Energy','Infrastructure','Commercial','UL-Listed','K. Davis'),
('CUST-008','Southern Company','Infrastructure','Commercial','Standard','P. Wilson'),
('CUST-009','Eversource Energy','Infrastructure','Commercial','UL-Listed','D. Miller'),
('CUST-010','ConEdison','Infrastructure','Commercial','UL-Listed','F. Garcia'),
('CUST-011','Caterpillar Inc','Industrial','Commercial','Standard','B. Anderson'),
('CUST-012','Siemens Energy','Industrial','Commercial','Standard','H. Martinez'),
('CUST-013','ABB Ltd','Industrial','Commercial','Standard','L. Thompson'),
('CUST-014','Schneider Electric','Industrial','Commercial','Standard','N. Robinson'),
('CUST-015','Rockwell Automation','Industrial','Commercial','Standard','C. White'),
('CUST-016','Schlumberger','Oil & Gas','Commercial','API','G. Harris'),
('CUST-017','Halliburton','Oil & Gas','Commercial','API','E. Clark'),
('CUST-018','Baker Hughes','Oil & Gas','Commercial','API','V. Lewis'),
('CUST-019','Weatherford Int','Oil & Gas','Commercial','API','I. Lee'),
('CUST-020','NOV Inc','Oil & Gas','Commercial','API','O. Walker');

-- PLANTS, REEL TYPES, UNIT CONVERSIONS
INSERT INTO plants VALUES ('PLANT-RI','Rhode Island','Cranston, RI',500),('PLANT-SC','South Carolina','Greenville, SC',300),('PLANT-TX','Texas','Houston, TX',200);
INSERT INTO reel_types VALUES ('RT-24W','24in Wood Reel',2500,'Wood',15),('RT-36W','36in Wood Reel',5000,'Wood',35),('RT-48S','48in Steel Reel',10000,'Steel',85),('RT-30P','30in Plastic Reel',3000,'Plastic',8),('RT-DRUM','Bulk Drum',25000,'Steel',120);
INSERT INTO unit_conversions VALUES ('KFT','FT',1000),('FT','KFT',0.001),('FT','M',0.3048),('M','FT',3.28084),('KG','LB',2.20462),('LB','KG',0.453592);

-- ROUTINGS (10 key products)
INSERT INTO routings (product_id,sequence_num,wc_id,operation_name,process_time_min_per_100ft,setup_time_min) VALUES
-- Multi-conductor products: COMPOUND → DRAW → STRAND → CV → ... (strand step added for products with >1 conductor)
-- Single-conductor products: DRAW → CV → ... (no strand needed)
('INST-3C16-FBS',1,'COMPOUND-1','Compound',5,45),('INST-3C16-FBS',2,'DRAW-1','Draw',8,30),('INST-3C16-FBS',3,'STRAND-1','Strand',4,25),('INST-3C16-FBS',4,'CV-1','Insulate',6,45),('INST-3C16-FBS',5,'FOIL-1','Foil',4,20),('INST-3C16-FBS',6,'BRAID-1','Braid',12,30),('INST-3C16-FBS',7,'CABLE-1','Cable',10,25),('INST-3C16-FBS',8,'PLCV-1','Jacket',15,40),('INST-3C16-FBS',9,'TEST-1','Test',5,10),('INST-3C16-FBS',10,'CUT-1','Cut',3,10),('INST-3C16-FBS',11,'PACK-1','Pack',2,5),
('CTRL-2C12-XA',1,'COMPOUND-1','Compound',5,45),('CTRL-2C12-XA',2,'DRAW-1','Draw',11,30),('CTRL-2C12-XA',3,'STRAND-1','Strand',5,25),('CTRL-2C12-XA',4,'CV-1','Insulate',9,45),('CTRL-2C12-XA',5,'BRAID-2','Braid',16,30),('CTRL-2C12-XA',6,'CABLE-1','Cable',14,25),('CTRL-2C12-XA',7,'PLCV-1','Jacket',20,40),('CTRL-2C12-XA',8,'ARMOR-1','Armor',12,35),('CTRL-2C12-XA',9,'TEST-1','Test',7,10),('CTRL-2C12-XA',10,'CUT-1','Cut',5,10),('CTRL-2C12-XA',11,'PACK-1','Pack',2,5),
('DHT-1C12-260',1,'DRAW-1','Draw',7,30),('DHT-1C12-260',2,'CV-1','Insulate',5,45),('DHT-1C12-260',3,'PX-1','Jacket',10,60),('DHT-1C12-260',4,'TEST-1','Test',4,10),('DHT-1C12-260',5,'CUT-1','Cut',2,10),('DHT-1C12-260',6,'PACK-1','Pack',2,5),
('UL2196-2C14',1,'COMPOUND-1','Compound',5,45),('UL2196-2C14',2,'DRAW-1','Draw',9,30),('UL2196-2C14',3,'STRAND-1','Strand',4,25),('UL2196-2C14',4,'TAPE-1','Mica Tape',6,15),('UL2196-2C14',5,'CV-2','Insulate',7,45),('UL2196-2C14',6,'CABLE-1','Cable',11,25),('UL2196-2C14',7,'PLCV-1','Jacket',16,40),('UL2196-2C14',8,'CCCW-1','Wrap',10,30),('UL2196-2C14',9,'TEST-1','Test',6,10),('UL2196-2C14',10,'CUT-1','Cut',3,10),('UL2196-2C14',11,'PACK-1','Pack',2,5),
('IC-10AWG-THHN',1,'DRAW-1','Draw',4,20),('IC-10AWG-THHN',2,'CV-2','Insulate',3,30),('IC-10AWG-THHN',3,'TEST-1','Test',2,10),('IC-10AWG-THHN',4,'CUT-1','Cut',1,5),('IC-10AWG-THHN',5,'PACK-1','Pack',1,5),
('LSOH-3C12-SB',1,'DRAW-1','Draw',9,30),('LSOH-3C12-SB',2,'STRAND-1','Strand',5,25),('LSOH-3C12-SB',3,'CV-1','Insulate',7,45),('LSOH-3C12-SB',4,'CABLE-1','Cable',12,25),('LSOH-3C12-SB',5,'PLCV-1','Jacket',17,40),('LSOH-3C12-SB',6,'TEST-1','Test',8,10),('LSOH-3C12-SB',7,'CUT-1','Cut',4,10),('LSOH-3C12-SB',8,'PACK-1','Pack',3,5),
('IC-12AWG-XLPE',1,'DRAW-1','Draw',3,20),('IC-12AWG-XLPE',2,'CV-2','Insulate',2,30),('IC-12AWG-XLPE',3,'CUT-1','Cut',1,5),('IC-12AWG-XLPE',4,'PACK-1','Pack',1,5),
('MV105-500MCM',1,'DRAW-1','Draw',15,30),('MV105-500MCM',2,'STRAND-1','Strand',6,25),('MV105-500MCM',3,'CV-1','Insulate L1',12,45),('MV105-500MCM',4,'TAPE-1','Semi-Con',8,15),('MV105-500MCM',5,'CV-3','Insulate L2',12,45),('MV105-500MCM',6,'TEST-1','HV Test',10,10),('MV105-500MCM',7,'CUT-1','Cut',6,10),('MV105-500MCM',8,'PACK-1','Pack',4,5),
('CTRL-4C12-XA',1,'COMPOUND-1','Compound',6,45),('CTRL-4C12-XA',2,'DRAW-1','Draw',13,30),('CTRL-4C12-XA',3,'STRAND-1','Strand',6,25),('CTRL-4C12-XA',4,'CV-2','Insulate',10,45),('CTRL-4C12-XA',5,'BRAID-2','Braid',18,30),('CTRL-4C12-XA',6,'CABLE-1','Cable',16,25),('CTRL-4C12-XA',7,'PLCV-1','Jacket',22,40),('CTRL-4C12-XA',8,'ARMOR-1','Armor',14,35),('CTRL-4C12-XA',9,'TEST-1','Test',8,10),('CTRL-4C12-XA',10,'CUT-1','Cut',5,10),('CTRL-4C12-XA',11,'PACK-1','Pack',3,5),
('DHT-2C12-H2S',1,'DRAW-1','Draw',8,30),('DHT-2C12-H2S',2,'STRAND-1','Strand',4,25),('DHT-2C12-H2S',3,'CV-1','Insulate',6,45),('DHT-2C12-H2S',4,'CABLE-1','Cable',9,25),('DHT-2C12-H2S',5,'PX-1','Jacket',12,60),('DHT-2C12-H2S',6,'TEST-1','Test',5,10),('DHT-2C12-H2S',7,'CUT-1','Cut',3,10),('DHT-2C12-H2S',8,'PACK-1','Pack',2,5);

-- CHANGEOVER MATRIX
INSERT INTO changeover_matrix VALUES ('A','A',15,50,0),('A','B',45,150,0),('A','C',60,200,1),('A','U',30,100,0),('A','R',20,75,0),('B','A',45,150,0),('B','B',20,75,0),('B','C',60,200,1),('B','U',40,125,0),('B','R',30,100,0),('C','A',75,250,1),('C','B',75,250,1),('C','C',25,100,0),('C','U',75,250,1),('C','R',60,200,1),('U','A',30,100,0),('U','B',40,125,0),('U','C',75,250,1),('U','U',15,50,0),('U','R',25,75,0),('R','A',20,75,0),('R','B',30,100,0),('R','C',60,200,1),('R','U',25,75,0),('R','R',10,50,0),('D','D',30,100,0),('D','A',90,300,1),('S','S',20,75,0),('I','I',10,50,0),('M','M',30,100,0);

-- BOM MATERIALS
INSERT INTO bom_materials (product_id,material_id,qty_per_kft,uom,scrap_factor) VALUES
('INST-3C16-FBS','MAT-001',15,'kg',0.03),('INST-3C16-FBS','MAT-004',8.5,'kg',0.02),('INST-3C16-FBS','MAT-010',2,'roll',0.01),('INST-3C16-FBS','MAT-008',6,'kg',0.02),('INST-3C16-FBS','MAT-012',1.5,'kg',0.01),
('CTRL-2C12-XA','MAT-001',20,'kg',0.03),('CTRL-2C12-XA','MAT-005',12,'kg',0.02),('CTRL-2C12-XA','MAT-008',8,'kg',0.02),('CTRL-2C12-XA','MAT-009',10,'kg',0.02),
('DHT-1C12-260','MAT-002',12,'kg',0.03),('DHT-1C12-260','MAT-006',5,'kg',0.02),
('UL2196-2C14','MAT-001',14,'kg',0.03),('UL2196-2C14','MAT-004',7,'kg',0.02),('UL2196-2C14','MAT-011',3,'roll',0.01),
('IC-10AWG-THHN','MAT-001',8,'kg',0.02),('IC-10AWG-THHN','MAT-004',4,'kg',0.02),('IC-10AWG-THHN','MAT-015',2,'kg',0.02),
('LSOH-3C12-SB','MAT-001',18,'kg',0.03),('LSOH-3C12-SB','MAT-016',10,'kg',0.02);

-- WORK ORDERS (25) — realistic quantities for weekly capacity
INSERT INTO work_orders (wo_id,product_id,business_unit,order_qty_kft,priority,due_date,status,created_date) VALUES
('WO-2026-001','INST-12P22-OS','Defense',2,1,'2026-04-20','Complete','2026-04-01'),
('WO-2026-002','INST-3C16-FBS','Industrial',3,3,'2026-04-22','InProcess','2026-04-02'),
('WO-2026-003','CTRL-2C12-XA','Infrastructure',2,2,'2026-04-18','Complete','2026-04-01'),
('WO-2026-004','CTRL-4C12-XA','Infrastructure',2,3,'2026-04-25','Released','2026-04-05'),
('WO-2026-005','DHT-1C12-260','Oil & Gas',3,4,'2026-04-28','Released','2026-04-07'),
('WO-2026-006','DHT-2C12-H2S','Oil & Gas',2,3,'2026-04-30','QCHold','2026-04-08'),
('WO-2026-007','UL2196-2C14','Infrastructure',5,2,'2026-04-24','InProcess','2026-04-03'),
('WO-2026-008','IC-10AWG-THHN','Industrial',25,5,'2026-05-01','Released','2026-04-10'),
('WO-2026-009','LSOH-3C12-SB','Defense',2,1,'2026-04-19','Complete','2026-03-28'),
('WO-2026-010','IC-12AWG-XLPE','Industrial',50,6,'2026-05-05','Pending','2026-04-12'),
('WO-2026-011','MV105-500MCM','Infrastructure',2,2,'2026-04-26','Released','2026-04-06'),
('WO-2026-012','INST-3C16-TP','Industrial',4,4,'2026-04-29','Pending','2026-04-11'),
('WO-2026-013','CTRL-6C14-XA','Infrastructure',2,3,'2026-04-27','Released','2026-04-09'),
('WO-2026-014','DHT-3C10-ESP','Oil & Gas',2,2,'2026-04-23','InProcess','2026-04-04'),
('WO-2026-015','SOOW-4C12','Industrial',10,5,'2026-05-03','Pending','2026-04-13'),
('WO-2026-016','PWR-2/0-ARM','Infrastructure',2,1,'2026-04-21','InProcess','2026-04-02'),
('WO-2026-017','RHW2-2AWG','Industrial',20,6,'2026-05-07','Pending','2026-04-14'),
('WO-2026-018','UL2196-4C12','Infrastructure',8,3,'2026-05-02','Released','2026-04-10'),
('WO-2026-019','LSOH-7C14-SB','Defense',2,1,'2026-04-22','Released','2026-04-05'),
('WO-2026-020','DHT-FP-FEP','Oil & Gas',2,2,'2026-04-25','Released','2026-04-08'),
('WO-2026-021','INST-6P22-OS','Infrastructure',3,3,'2026-04-28','Pending','2026-04-12'),
('WO-2026-022','MC-12-2','Industrial',12,5,'2026-05-04','Pending','2026-04-13'),
('WO-2026-023','TRAY-3C10','Industrial',15,5,'2026-05-06','Pending','2026-04-14'),
('WO-2026-024','IC-2AWG-XLPE','Industrial',30,6,'2026-05-08','Pending','2026-04-15'),
('WO-2026-025','UL2196-6C10','Infrastructure',2,2,'2026-04-30','Released','2026-04-09');

-- PERSONNEL (34)
INSERT INTO personnel (employee_code,employee_name,department,job_title,role,shift,certification_level,hire_date) VALUES
('EMP-001','Michael Torres','Production','Lead Operator','Operator','Day',3,'2018-03-15'),
('EMP-002','Sarah Chen','Production','CV Operator','Operator','Day',2,'2020-06-01'),
('EMP-003','James Wilson','Production','Braider Operator','Operator','Day',2,'2019-09-20'),
('EMP-004','Maria Rodriguez','Production','Cable Operator','Operator','Day',3,'2017-01-10'),
('EMP-005','David Kim','Production','Draw Operator','Operator','Day',2,'2021-02-15'),
('EMP-006','Jennifer Brown','Quality','QA Inspector','QA','Day',3,'2016-08-01'),
('EMP-007','Robert Martinez','Quality','QA Technician','QA','Day',2,'2022-01-15'),
('EMP-008','Lisa Anderson','Engineering','Process Engineer','Engineer','Day',4,'2015-05-01'),
('EMP-009','William Davis','Maintenance','Maintenance Tech','Maintenance','Day',3,'2018-11-01'),
('EMP-010','Amanda Thomas','Production','Shift Supervisor','Supervisor','Day',4,'2014-03-01'),
('EMP-011','Chris Parker','Production','Setup Technician','Setup','Day',3,'2019-04-15'),
('EMP-012','Karen White','Production','Packaging Operator','Operator','Day',1,'2023-06-01'),
('EMP-013','Anthony Lopez','Production','Lead Operator','Operator','Swing',3,'2017-07-01'),
('EMP-014','Jessica Taylor','Production','CV Operator','Operator','Swing',2,'2020-09-15'),
('EMP-015','Daniel Harris','Production','Braider Operator','Operator','Swing',2,'2019-12-01'),
('EMP-016','Michelle Clark','Quality','QA Inspector','QA','Swing',3,'2018-02-15'),
('EMP-017','Steven Lewis','Maintenance','Maintenance Tech','Maintenance','Swing',2,'2021-05-01'),
('EMP-018','Patricia Robinson','Production','Shift Supervisor','Supervisor','Swing',4,'2015-10-01'),
('EMP-019','Mark Walker','Production','Cable Operator','Operator','Swing',2,'2020-03-01'),
('EMP-020','Nancy Hall','Production','Draw Operator','Operator','Swing',1,'2023-01-15'),
('EMP-021','Brian Allen','Production','Packaging Operator','Operator','Swing',1,'2022-08-01'),
('EMP-022','Laura Young','Production','Setup Technician','Setup','Swing',2,'2020-11-01'),
('EMP-023','Kevin King','Production','Lead Operator','Operator','Night',3,'2016-04-01'),
('EMP-024','Stephanie Wright','Production','CV Operator','Operator','Night',2,'2021-07-15'),
('EMP-025','Paul Scott','Production','Braider Operator','Operator','Night',2,'2019-06-01'),
('EMP-026','Angela Green','Quality','QA Inspector','QA','Night',2,'2020-10-01'),
('EMP-027','Thomas Adams','Maintenance','Maintenance Tech','Maintenance','Night',2,'2022-03-01'),
('EMP-028','Diane Nelson','Production','Shift Supervisor','Supervisor','Night',4,'2016-12-01'),
('EMP-029','George Baker','Production','Cable Operator','Operator','Night',2,'2021-01-15'),
('EMP-030','Rachel Carter','Production','Draw Operator','Operator','Night',1,'2023-04-01'),
('EMP-031','Frank Mitchell','Management','Plant Manager','Engineer','Day',4,'2012-01-15'),
('EMP-032','Sandra Perez','Engineering','Quality Manager','Engineer','Day',4,'2013-06-01'),
('EMP-033','Richard Campbell','Engineering','Maintenance Manager','Engineer','Day',4,'2014-09-01'),
('EMP-034','Helen Morris','Engineering','Production Planner','Engineer','Day',3,'2017-04-15');

-- PERSONNEL CERTS
INSERT INTO personnel_certs (person_id,wc_id,certification_type,cert_level,issued_date,expiry_date,status) VALUES
(1,'CV-1','Extrusion',3,'2023-01-15','2027-01-15','Active'),(1,'CV-2','Extrusion',3,'2023-01-15','2027-01-15','Active'),
(2,'CV-1','Extrusion',2,'2022-09-01','2026-09-01','Active'),(3,'BRAID-1','Braiding',2,'2023-03-15','2027-03-15','Active'),
(4,'CABLE-1','Cabling',3,'2022-06-01','2026-06-01','Active'),(5,'DRAW-1','Drawing',2,'2023-05-01','2027-05-01','Active'),
(6,'TEST-1','SparkTest',3,'2022-01-15','2026-04-20','Active'),(6,'TEST-1','HipotTest',3,'2022-01-15','2026-08-15','Active'),
(7,'TEST-1','SparkTest',2,'2023-06-01','2027-06-01','Active'),(9,'DRAW-1','Maintenance',3,'2022-03-01','2026-03-01','Active'),
(11,'CV-1','Setup',3,'2022-08-01','2026-08-01','Active'),(11,'CV-2','Setup',3,'2022-08-01','2026-08-01','Active');

-- EQUIPMENT (23)
INSERT INTO equipment (equipment_code,description,work_center_id,equipment_type,manufacturer,install_date,last_pm_date,next_pm_date,calibration_due,calibration_freq_days,status) VALUES
-- Compounding
('EQ-COMP-01','Banbury Mixer 200L','COMPOUND-1','Mixer','Farrel Pomini','2018-06-15','2026-03-15','2026-04-15','2026-05-01',90,'Active'),
('EQ-COMP-02','Compounding Line 2 Mixer','COMPOUND-2','Mixer','Farrel Pomini','2021-02-01','2026-03-20','2026-04-20','2026-05-10',90,'Active'),
-- Drawing
('EQ-DRAW-01','Multi-Wire Drawing 24-die','DRAW-1','Die','Niehoff','2019-01-10','2026-04-01','2026-05-01','2026-04-20',60,'Active'),
('EQ-DRAW-02','Drawing Capstan Motor','DRAW-1','Motor','Niehoff','2019-01-10','2026-03-28','2026-04-28','2026-06-01',180,'Active'),
-- STRAND-1: payoff creel + stranding machine + takeup
('EQ-STRAND-PAY','STRAND-1 Multi-Payoff Creel (7-61 bobbins)','STRAND-1','Motor','Cortinovis','2018-05-01','2026-04-01','2026-05-01',NULL,NULL,'Active'),
('EQ-STRAND-01','Stranding Machine 7-61 Wire','STRAND-1','Motor','Cortinovis','2018-05-01','2026-04-03','2026-05-03','2026-05-15',90,'Active'),
('EQ-STRAND-TU','STRAND-1 Takeup','STRAND-1','Motor','Skaltek','2018-05-01','2026-04-05','2026-05-05',NULL,NULL,'Active'),
-- CV-1: 2 extruders + payoff + caterpillar + takeup
('EQ-CV1-EXT1','CV-1 Primary Extruder (insulation)','CV-1','Screw','Davis-Standard','2017-03-20','2026-03-20','2026-04-20','2026-05-15',90,'Active'),
('EQ-CV1-EXT2','CV-1 Secondary Extruder (jacket/stripe)','CV-1','Screw','Davis-Standard','2017-03-20','2026-03-25','2026-04-25','2026-05-15',90,'Active'),
('EQ-CV1-PAY','CV-1 Payoff (single conductor)','CV-1','Motor','Niehoff','2017-03-20','2026-04-01','2026-05-01',NULL,NULL,'Active'),
('EQ-CV1-CAT','CV-1 Caterpillar Haul-Off','CV-1','Motor','Maillefer','2017-03-20','2026-04-05','2026-05-05','2026-06-01',180,'Active'),
('EQ-CV1-TU','CV-1 Takeup Reel Stand','CV-1','Motor','Skaltek','2017-03-20','2026-04-08','2026-05-08',NULL,NULL,'Active'),
('EQ-CV1-CVT','CV-1 CV Tube (cooling/curing trough)','CV-1','Vessel','Maillefer','2017-03-20','2026-03-18','2026-04-18','2026-05-01',90,'Active'),
-- CV-2: 1 extruder + payoff + caterpillar + takeup + CV tube
('EQ-CV2-EXT1','CV-2 Extruder (high-speed 3000fpm)','CV-2','Screw','Davis-Standard','2020-08-01','2026-04-05','2026-05-05','2026-06-01',90,'Active'),
('EQ-CV2-PAY','CV-2 Payoff (single conductor)','CV-2','Motor','Niehoff','2020-08-01','2026-04-02','2026-05-02',NULL,NULL,'Active'),
('EQ-CV2-CAT','CV-2 Caterpillar Haul-Off','CV-2','Motor','Maillefer','2020-08-01','2026-04-06','2026-05-06','2026-06-15',180,'Active'),
('EQ-CV2-TU','CV-2 Takeup Reel Stand','CV-2','Motor','Skaltek','2020-08-01','2026-04-10','2026-05-10',NULL,NULL,'Active'),
('EQ-CV2-CVT','CV-2 CV Tube (cooling/curing trough)','CV-2','Vessel','Maillefer','2020-08-01','2026-03-22','2026-04-22','2026-05-10',90,'Active'),
-- CV-3: 2 extruders + 2 payoffs + caterpillar + takeup + CV tube
('EQ-CV3-EXT1','CV-3 Primary Extruder','CV-3','Screw','Davis-Standard','2022-01-15','2026-04-02','2026-05-02','2026-05-20',90,'Active'),
('EQ-CV3-EXT2','CV-3 Secondary Extruder','CV-3','Screw','Davis-Standard','2022-01-15','2026-04-05','2026-05-05','2026-05-20',90,'Active'),
('EQ-CV3-PAY1','CV-3 Payoff 1 (conductor A)','CV-3','Motor','Niehoff','2022-01-15','2026-04-01','2026-05-01',NULL,NULL,'Active'),
('EQ-CV3-PAY2','CV-3 Payoff 2 (conductor B)','CV-3','Motor','Niehoff','2022-01-15','2026-04-01','2026-05-01',NULL,NULL,'Active'),
('EQ-CV3-CAT','CV-3 Caterpillar Haul-Off','CV-3','Motor','Maillefer','2022-01-15','2026-04-08','2026-05-08','2026-06-15',180,'Active'),
('EQ-CV3-TU','CV-3 Takeup Reel Stand','CV-3','Motor','Skaltek','2022-01-15','2026-04-10','2026-05-10',NULL,NULL,'Active'),
('EQ-CV3-CVT','CV-3 CV Tube (cooling/curing trough)','CV-3','Vessel','Maillefer','2022-01-15','2026-03-25','2026-04-25','2026-05-15',90,'Active'),
-- PLCV-1: 3 extruders + 2 payoffs + caterpillar + takeup + CV tube
('EQ-PLCV-EXT1','PLCV Primary Extruder (inner jacket)','PLCV-1','Screw','Davis-Standard','2017-11-01','2026-03-28','2026-04-28','2026-05-15',90,'Active'),
('EQ-PLCV-EXT2','PLCV Secondary Extruder (insulation)','PLCV-1','Screw','Davis-Standard','2017-11-01','2026-04-01','2026-05-01','2026-05-15',90,'Active'),
('EQ-PLCV-EXT3','PLCV Tertiary Extruder (outer jacket)','PLCV-1','Screw','Davis-Standard','2019-06-01','2026-04-03','2026-05-03','2026-05-20',90,'Active'),
('EQ-PLCV-PAY1','PLCV Payoff 1 (core assembly)','PLCV-1','Motor','Niehoff','2017-11-01','2026-04-05','2026-05-05',NULL,NULL,'Active'),
('EQ-PLCV-PAY2','PLCV Payoff 2 (drain wire)','PLCV-1','Motor','Niehoff','2017-11-01','2026-04-05','2026-05-05',NULL,NULL,'Active'),
('EQ-PLCV-CAT','PLCV Caterpillar Haul-Off','PLCV-1','Motor','Maillefer','2017-11-01','2026-04-06','2026-05-06','2026-06-01',180,'Active'),
('EQ-PLCV-TU','PLCV Takeup Reel Stand','PLCV-1','Motor','Skaltek','2017-11-01','2026-04-08','2026-05-08',NULL,NULL,'Active'),
('EQ-PLCV-CVT','PLCV CV Tube (pressurized curing)','PLCV-1','Vessel','Maillefer','2017-11-01','2026-03-15','2026-04-15','2026-04-30',60,'Active'),
-- LPML-1: 3 extruders + 2 payoffs + caterpillar + takeup
('EQ-LPML-EXT1','LPML Primary Extruder','LPML-1','Screw','Davis-Standard','2021-05-01','2026-04-01','2026-05-01','2026-05-20',90,'Active'),
('EQ-LPML-EXT2','LPML Secondary Extruder','LPML-1','Screw','Davis-Standard','2021-05-01','2026-04-03','2026-05-03','2026-05-20',90,'Active'),
('EQ-LPML-EXT3','LPML Tertiary Extruder (outer)','LPML-1','Screw','Davis-Standard','2021-05-01','2026-04-05','2026-05-05','2026-05-20',90,'Active'),
('EQ-LPML-PAY1','LPML Payoff 1','LPML-1','Motor','Niehoff','2021-05-01','2026-04-02','2026-05-02',NULL,NULL,'Active'),
('EQ-LPML-PAY2','LPML Payoff 2','LPML-1','Motor','Niehoff','2021-05-01','2026-04-02','2026-05-02',NULL,NULL,'Active'),
('EQ-LPML-CAT','LPML Caterpillar Haul-Off','LPML-1','Motor','Maillefer','2021-05-01','2026-04-06','2026-05-06','2026-06-15',180,'Active'),
('EQ-LPML-TU','LPML Takeup Reel Stand','LPML-1','Motor','Skaltek','2021-05-01','2026-04-08','2026-05-08',NULL,NULL,'Active'),
-- PX-1: 1 extruder + payoff + caterpillar + takeup
('EQ-PX1-EXT1','PX-1 FEP/ETFE Extruder','PX-1','Screw','Davis-Standard','2020-03-01','2026-04-10','2026-05-10','2026-06-01',90,'Active'),
('EQ-PX1-PAY','PX-1 Payoff','PX-1','Motor','Niehoff','2020-03-01','2026-04-08','2026-05-08',NULL,NULL,'Active'),
('EQ-PX1-CAT','PX-1 Caterpillar Haul-Off','PX-1','Motor','Maillefer','2020-03-01','2026-04-09','2026-05-09','2026-06-15',180,'Active'),
('EQ-PX1-TU','PX-1 Takeup Reel Stand','PX-1','Motor','Skaltek','2020-03-01','2026-04-12','2026-05-12',NULL,NULL,'Active'),
-- PT-1: 1 extruder (fiber draw tower) + payoff + caterpillar + takeup
('EQ-PT1-EXT1','PT-1 Fiber Draw Tower','PT-1','Screw','Rosendahl','2021-09-01','2026-04-05','2026-05-05','2026-05-20',60,'Active'),
('EQ-PT1-PAY','PT-1 Preform Payoff','PT-1','Motor','Rosendahl','2021-09-01','2026-04-03','2026-05-03',NULL,NULL,'Active'),
('EQ-PT1-CAT','PT-1 Capstan Haul-Off','PT-1','Motor','Rosendahl','2021-09-01','2026-04-07','2026-05-07','2026-06-01',180,'Active'),
('EQ-PT1-TU','PT-1 Fiber Takeup Spool','PT-1','Motor','Rosendahl','2021-09-01','2026-04-10','2026-05-10',NULL,NULL,'Active'),
-- Shielding & Braiding
('EQ-FOIL-01','Foil Wrap Applicator','FOIL-1','Motor','Maillefer','2019-07-01','2026-04-10','2026-05-10','2026-06-15',180,'Active'),
('EQ-BRAID-01','16-Carrier Braider','BRAID-1','Bearing','Wardwell','2017-09-01','2026-04-08','2026-05-08','2026-07-01',180,'Active'),
('EQ-BRAID-02','24-Carrier Braider','BRAID-2','Bearing','Wardwell','2018-04-01','2026-04-10','2026-05-10','2026-07-01',180,'Active'),
('EQ-BRAID-03','36-Carrier Braider','BRAID-3','Bearing','Wardwell','2020-11-01','2026-04-12','2026-05-12','2026-07-15',180,'Active'),
-- Cabling & Assembly
('EQ-CABLE1-PAY','CABLE-1 Payoff (multi-conductor)','CABLE-1','Motor','Cortinovis','2016-06-01','2026-04-01','2026-05-01',NULL,NULL,'Active'),
('EQ-CABLE-01','Cabling Machine 2-19 conductors','CABLE-1','Motor','Cortinovis','2016-06-01','2026-04-02','2026-05-02','2026-05-10',90,'Active'),
('EQ-CABLE1-TU','CABLE-1 Takeup Reel Stand','CABLE-1','Motor','Skaltek','2016-06-01','2026-04-05','2026-05-05',NULL,NULL,'Active'),
('EQ-CABLE2-PAY','CABLE-2 Payoff (multi-conductor)','CABLE-2','Motor','Cortinovis','2019-03-01','2026-04-02','2026-05-02',NULL,NULL,'Active'),
('EQ-CABLE-02','Cabling Machine 19-37 conductors','CABLE-2','Motor','Cortinovis','2019-03-01','2026-04-04','2026-05-04','2026-05-15',90,'Active'),
('EQ-CABLE2-TU','CABLE-2 Takeup Reel Stand','CABLE-2','Motor','Skaltek','2019-03-01','2026-04-06','2026-05-06',NULL,NULL,'Active'),
-- Armoring
('EQ-ARMOR-01','AIA Armoring Line','ARMOR-1','Motor','Niehoff','2018-02-15','2026-03-22','2026-04-22','2026-06-15',180,'Active'),
('EQ-CCCW-01','CCCW Welding Head','CCCW-1','Motor','Nexans','2019-10-01','2026-04-05','2026-05-05','2026-06-01',90,'Active'),
-- Testing
('EQ-TEST-01','Spark Tester 15kV AC/DC','TEST-1','Sensor','Clinton Instrument','2020-01-15','2026-04-12','2026-05-12','2026-04-18',30,'Active'),
('EQ-TEST-02','Hipot Tester 50kV DC','TEST-1','Sensor','Hipotronics','2019-08-01','2026-04-12','2026-05-12','2026-04-25',30,'Active'),
('EQ-TEST-03','DC Resistance Bridge','TEST-2','Sensor','Megger','2020-06-01','2026-04-15','2026-05-15','2026-04-22',30,'Active'),
('EQ-TEST-04','Laser Diameter Gauge','TEST-1','Sensor','Zumbach','2021-01-15','2026-04-10','2026-05-10','2026-04-20',30,'Active'),
-- Cut & Pack
('EQ-CUT-PAY','CUT-1 Payoff Reel Stand','CUT-1','Motor','Skaltek','2020-06-15','2026-04-06','2026-05-06',NULL,NULL,'Active'),
('EQ-CUT-01','Auto Cut & Coil Station','CUT-1','Motor','Schleuniger','2020-06-15','2026-04-08','2026-05-08','2026-06-01',180,'Active'),
('EQ-CUT-02','Footage Encoder Wheel','CUT-1','Sensor','Skaltek','2020-06-15','2026-04-10','2026-05-10','2026-04-25',30,'Active'),
('EQ-CUT-TU','CUT-1 Takeup / Reel Coiler','CUT-1','Motor','Skaltek','2020-06-15','2026-04-12','2026-05-12',NULL,NULL,'Active'),
('EQ-PACK-01','Reel Wrapper & Palletizer','PACK-1','Motor','Skaltek','2021-08-01','2026-04-12','2026-05-12',NULL,NULL,'Active');

-- SHIPPING COSTS
INSERT INTO shipping_costs VALUES ('PLANT-RI','CUST-001',5),('PLANT-RI','CUST-006',6.5),('PLANT-RI','CUST-011',8),('PLANT-RI','CUST-016',12),('PLANT-SC','CUST-006',8),('PLANT-SC','CUST-011',6),('PLANT-SC','CUST-016',9),('PLANT-TX','CUST-016',5),('PLANT-TX','CUST-017',4.5),('PLANT-TX','CUST-018',5);

-- PACKAGING SPECS
INSERT INTO packaging_specs (customer_id,product_id,reel_type_id,label_format,box_qty,special_instructions) VALUES
('CUST-001','INST-12P22-OS','RT-48S','MIL-STD',1,'Desiccant required'),
('CUST-001','LSOH-3C12-SB','RT-48S','MIL-STD',1,'Wooden crate'),
('CUST-006','CTRL-2C12-XA','RT-36W','UL-Standard',2,NULL),
('CUST-006','UL2196-2C14','RT-36W','UL-Standard',4,NULL),
('CUST-011','IC-10AWG-THHN','RT-DRUM','Generic',1,NULL),
('CUST-016','DHT-1C12-260','RT-48S','Customer-Specific',1,'Heat shrink wrap');

-- RECIPES
INSERT INTO recipes (recipe_code,description,product_id,work_center_id,version,status,effective_date) VALUES
('RCP-CV1-FBS','CV1 Recipe INST-3C16-FBS','INST-3C16-FBS','CV-1',3,'Approved','2025-06-01'),
('RCP-CV1-XA','CV1 Recipe CTRL-2C12-XA','CTRL-2C12-XA','CV-1',2,'Approved','2025-09-15'),
('RCP-PX1-DHT','PX1 Recipe DHT-1C12-260','DHT-1C12-260','PX-1',1,'Approved','2026-01-10'),
('RCP-PLCV-UL','PLCV1 Recipe UL2196-2C14','UL2196-2C14','PLCV-1',2,'Approved','2025-11-01'),
('RCP-CV2-THHN','CV2 Recipe IC-10AWG-THHN','IC-10AWG-THHN','CV-2',4,'Approved','2025-03-15');
INSERT INTO recipe_parameters (recipe_id,parameter_name,parameter_value,uom,lower_limit,upper_limit,control_type) VALUES
(1,'Zone1_Temp',350,'F',340,360,'SPC'),(1,'Zone2_Temp',365,'F',355,375,'SPC'),(1,'Line_Speed',400,'fpm',350,450,'SPC'),
(2,'Zone1_Temp',380,'F',370,390,'SPC'),(2,'Line_Speed',350,'fpm',300,400,'SPC'),
(3,'Zone1_Temp',580,'F',570,590,'SPC'),(3,'Die_Pressure',3500,'psi',3200,3800,'Alarm'),
(4,'Zone1_Temp',355,'F',345,365,'SPC'),(4,'Line_Speed',500,'fpm',450,550,'SPC'),
(5,'Zone1_Temp',345,'F',335,355,'SPC'),(5,'Line_Speed',3000,'fpm',2800,3200,'SPC');

-- KPI DEFINITIONS
INSERT INTO kpi_definitions (kpi_name,formula,uom,target,frequency,category) VALUES
('OEE','A x P x Q','%',85,'Shift','Performance'),('FPY','Product(1-defect_k)','%',97,'Shift','Quality'),
('Schedule Adherence','On-time/Total','%',90,'Daily','Scheduling'),('Labor Efficiency','Earned/Actual hrs','%',85,'Shift','Labor'),
('MTBF','Uptime/Failures','hours',500,'Weekly','Maintenance'),('MTTR','Repair/Repairs','hours',2,'Weekly','Maintenance'),
('Scrap Rate','Scrap/Total','%',3,'Shift','Quality'),('PM Compliance','Done/Scheduled','%',95,'Weekly','Maintenance');
