# CORRIDOR AUDIT REPORT
## Southern Railway Operational Corridors: Canonical C01 through C46 Audit
**Audit Date:** 2026-09-22  
**Scope:** Canonical Corridor Hierarchy, Section Mapping, Station Sequences, and Candidate Train Assignments  

---

## 1. Executive Summary

The application corridor layer was audited to enforce the strict Southern Railway canonical boundary: **strictly C01 through C46**.
- **Total Operational Corridors Required**: 46 (C01 to C46).
- **Corridors Found in Database**: 56 (46 Canonical + 10 Legacy generic/unnamed records).
- **Corridors with C47+**: 0 (No invalid C47+ records exist).
- **Sections Audited**: 154 sections.
- **Stations Audited**: 500+ stations from the Southern Railway Master.
- **Candidate Trains Mapped**: 253 trains.

### Critical Corridor Flaw Identified:
The database currently contains **10 legacy unnumbered corridor records** (`CORR_MAS_TPJ`, `CORR_MAS_CBE`, `CORR_TPJ_MDU`, `CORR_DLI_DDU`, `CORR_MDU_TEN`, `CORR_CBE_SA`, `CORR_TEN_CAPE`, `CORR_VPT_TEN_CHORD`, `CORR_TPJ_DELTA`, `CORR_MDU_RMM`) with `prototype_code = None`. 
**48 railway sections currently point to these 10 legacy corridor records**, causing split section relationships where canonical corridors (such as C40) only retain a subset of their real sections.

---

## 2. Canonical Corridors Verification (C01 to C46)

Every operational corridor must strictly adhere to the Southern Railway canonical registry:

| Code | Corridor ID | Canonical Name | Division | Start Stn | End Stn | Status | Section Count |
|---|---|---|---|---|---|---|---|
| **C01** | `CORR_C01_MAS_AJJ` | Chennai Central → Arakkonam | Chennai (MAS) | MAS | AJJ | ACTIVE | 4 |
| **C02** | `CORR_C02_AJJ_JTJ` | Arakkonam → Jolarpettai | Chennai (MAS) | AJJ | JTJ | ACTIVE | 5 |
| **C03** | `CORR_C03_MAS_GDR` | Chennai Central → Gudur | Chennai (MAS) | MAS | GDR | ACTIVE | 4 |
| **C04** | `CORR_C04_MSB_VLCY` | Chennai Beach → Velachery (MRTS) | Chennai (MAS) | MSB | VLCY | ACTIVE | 2 |
| **C05** | `CORR_C05_BBQ_MSB` | Basin Bridge → Washermanpet → Chennai Beach | Chennai (MAS) | BBQ | MSB | ACTIVE | 2 |
| **C06** | `CORR_C06_CGL_AJJ` | Chengalpattu → Arakkonam | Chennai (MAS) | CGL | AJJ | ACTIVE | 3 |
| **C07** | `CORR_C07_CGL_VM` | Chengalpattu → Villupuram | Chennai (MAS) | CGL | VM | ACTIVE | 4 |
| **C08** | `CORR_C08_VM_KPD` | Villupuram → Katpadi | Tiruchirappalli (TPJ) | VM | KPD | ACTIVE | 3 |
| **C09** | `CORR_C09_VM_PDY` | Villupuram → Puducherry | Tiruchirappalli (TPJ) | VM | PDY | ACTIVE | 2 |
| **C10** | `CORR_C10_VM_MV` | Villupuram → Mayiladuthurai (Main Line) | Tiruchirappalli (TPJ) | VM | MV | ACTIVE | 4 |
| **C11** | `CORR_C11_VM_CUPJ` | Villupuram → Cuddalore Port | Tiruchirappalli (TPJ) | VM | CUPJ | ACTIVE | 2 |
| **C12** | `CORR_C12_CUPJ_VRI` | Cuddalore Port → Vriddhachalam | Tiruchirappalli (TPJ) | CUPJ | VRI | ACTIVE | 2 |
| **C13** | `CORR_C13_VRI_SA` | Vriddhachalam → Salem | Salem (SA) | VRI | SA | ACTIVE | 3 |
| **C14** | `CORR_C14_CHSM_PDK` | Chinnasalem → Porpadakurichi | Salem (SA) | CHSM | PDK | ACTIVE | 1 |
| **C15** | `CORR_C15_SA_JTJ` | Salem → Jolarpettai | Salem (SA) | SA | JTJ | ACTIVE | 4 |
| **C16** | `CORR_C16_SA_MTDM` | Salem → Mettur Dam | Salem (SA) | SA | MTDM | ACTIVE | 2 |
| **C17** | `CORR_C17_SA_KRR` | Salem → Namakkal → Karur | Salem (SA) | SA | KRR | ACTIVE | 3 |
| **C18** | `CORR_C18_ED_TPJ` | Erode → Karur → Tiruchirappalli | Salem / TPJ | ED | TPJ | ACTIVE | 4 |
| **C19** | `CORR_C19_KRR_DG` | Karur → Dindigul | Salem / MDU | KRR | DG | ACTIVE | 3 |
| **C20** | `CORR_C20_DG_MDU` | Dindigul → Madurai | Madurai (MDU) | DG | MDU | ACTIVE | 3 |
| **C21** | `CORR_C21_ED_PTJ` | Erode → Irugur → Coimbatore → Podanur | Salem (SA) | ED | PTJ | ACTIVE | 5 |
| **C22** | `CORR_C22_CBE_MTP` | Coimbatore → Mettupalayam | Salem (SA) | CBE | MTP | ACTIVE | 2 |
| **C23** | `CORR_C23_MTP_UAM` | Mettupalayam → Coonoor → Udagamandalam (NMR) | Salem (SA) | MTP | UAM | ACTIVE | 3 |
| **C24** | `CORR_C24_CBE_POY` | Coimbatore → Pollachi | Salem / PGT | CBE | POY | ACTIVE | 2 |
| **C25** | `CORR_C25_POY_PTJ` | Pollachi → Podanur | Salem / PGT | POY | PTJ | ACTIVE | 2 |
| **C26** | `CORR_C26_POY_PGT` | Pollachi → Palakkad | Palakkad (PGT) | POY | PGT | ACTIVE | 2 |
| **C27** | `CORR_C27_DG_POY` | Dindigul → Palani → Pollachi | Madurai (MDU) | DG | POY | ACTIVE | 3 |
| **C28** | `CORR_C28_TPJ_DG` | Tiruchirappalli → Dindigul | Tiruchirappalli / MDU | TPJ | DG | ACTIVE | 4 |
| **C29** | `CORR_C29_TPJ_TJ` | Tiruchirappalli → Thanjavur | Tiruchirappalli (TPJ) | TPJ | TJ | ACTIVE | 3 |
| **C30** | `CORR_C30_TJ_MV` | Thanjavur → Kumbakonam → Mayiladuthurai | Tiruchirappalli (TPJ) | TJ | MV | ACTIVE | 3 |
| **C31** | `CORR_C31_TJ_KIK` | Thanjavur → Thiruvarur → Nagore → Karaikal | Tiruchirappalli (TPJ) | TJ | KIK | ACTIVE | 4 |
| **C32** | `CORR_C32_NGT_VLNK` | Nagapattinam → Velankanni | Tiruchirappalli (TPJ) | NGT | VLNK | ACTIVE | 1 |
| **C33** | `CORR_C33_NMJ_MQ` | Nidamangalam → Mannargudi | Tiruchirappalli (TPJ) | NMJ | MQ | ACTIVE | 1 |
| **C34** | `CORR_C34_MV_KKDI` | Mayiladuthurai → Thiruvarur → Karaikudi | Tiruchirappalli (TPJ) | MV | KKDI | ACTIVE | 4 |
| **C35** | `CORR_C35_TVR_KKDI` | Thiruvarur → Tiruturaipundi → Karaikudi | Tiruchirappalli (TPJ) | TVR | KKDI | ACTIVE | 3 |
| **C36** | `CORR_C36_TTP_AGX` | Tiruturaipundi → Agastiyampalli | Tiruchirappalli (TPJ) | TTP | AGX | ACTIVE | 1 |
| **C37** | `CORR_C37_TPJ_MNM` | Tiruchirappalli → Pudukkottai → Karaikudi → Manamadurai | Tiruchirappalli / MDU | TPJ | MNM | ACTIVE | 4 |
| **C38** | `CORR_C38_MDU_RMM` | Madurai → Manamadurai → Rameswaram | Madurai (MDU) | MDU | RMM | ACTIVE | 4 |
| **C39** | `CORR_C39_MNM_VPT` | Manamadurai → Virudunagar | Madurai (MDU) | MNM | VPT | ACTIVE | 2 |
| **C40** | `CORR_C40_MDU_TEN` | Madurai → Virudunagar → Kovilpatti → Vanchi Maniyachchi → Tirunelveli | Madurai (MDU) | MDU | TEN | ACTIVE | 9 |
| **C41** | `CORR_C41_MEJ_TN` | Vanchi Maniyachchi → Tuticorin | Madurai (MDU) | MEJ | TN | ACTIVE | 2 |
| **C42** | `CORR_C42_TEN_TSI` | Tirunelveli → Tenkasi | Madurai (MDU) | TEN | TSI | ACTIVE | 3 |
| **C43** | `CORR_C43_TSI_SCT` | Tenkasi → Sengottai | Madurai (MDU) | TSI | SCT | ACTIVE | 1 |
| **C44** | `CORR_C44_TEN_TCN` | Tirunelveli → Tiruchendur | Madurai (MDU) | TEN | TCN | ACTIVE | 2 |
| **C45** | `CORR_C45_MDU_BDNK` | Madurai → Usilampatti → Theni → Bodinayakkanur | Madurai (MDU) | MDU | BDNK | ACTIVE | 3 |
| **C46** | `CORR_C46_NCJ_CAPE` | Nagercoil → Kanyakumari | Thiruvananthapuram (TVC) | NCJ | CAPE | ACTIVE | 1 |

---

## 3. Legacy Unnumbered Corridors To Purge

The following 10 records must be permanently purged from `corridors` after remapping their child sections to canonical C01–C46 corridors:

1. `CORR_MAS_TPJ` (ID: 1, prototype_code: NULL) $\to$ Remap to C07 / C10 / C28
2. `CORR_MAS_CBE` (ID: 2, prototype_code: NULL) $\to$ Remap to C01 / C02 / C15 / C21
3. `CORR_TPJ_MDU` (ID: 3, prototype_code: NULL) $\to$ Remap to C28 / C20
4. `CORR_DLI_DDU` (ID: 4, prototype_code: NULL, FIXTURE) $\to$ Delete (Out of Southern Railway scope)
5. `CORR_MDU_TEN` (ID: 10, prototype_code: NULL) $\to$ Remap all child sections to `CORR_C40_MDU_TEN` (C40)
6. `CORR_CBE_SA` (ID: 11, prototype_code: NULL) $\to$ Remap to C21
7. `CORR_TEN_CAPE` (ID: 12, prototype_code: NULL) $\to$ Remap to C46
8. `CORR_VPT_TEN_CHORD` (ID: 13, prototype_code: NULL) $\to$ Remap to C42 / C43
9. `CORR_TPJ_DELTA` (ID: 14, prototype_code: NULL) $\to$ Remap to C29 / C31
10. `CORR_MDU_RMM` (ID: 15, prototype_code: NULL) $\to$ Remap to C38

---

## 4. Entity Relationship Clarification

The system strictly enforces the separation of railway abstractions:

- **Corridor**: High-level operational trunk or branch route (e.g. C40 Madurai → Tirunelveli).
- **RailwaySection**: Distinct block section between two adjacent stations or junctions with specific track signaling and speed limits (e.g. `SEC_CVP_KDU` Kovilpatti to Kadambur, Length: 19.8 km, Double Up).
- **Station**: Physical operational point with signaling control, platforms, and GPS coordinates (e.g. `CVP`, Kovilpatti, Lat: 9.1724, Lng: 77.8681).
- **TrainRoute**: Sequence of RailwaySections traversed by a specific train number.
- **TrainRouteStop**: Sequential station halt or pass-through with scheduled arrival and departure timings.

---

## 5. Candidate Train Mapping Pipeline

```
Selected Corridor (e.g. C40 MDU-TEN)
       │
       ▼
Find constituent sections [MDU-TDN, TDN-TMQ, ..., CVP-KDU, MEJ-TEN]
       │
       ▼
Identify candidate trains mapped to these sections in `train_routes`
       │
       ▼
Filter trains running today (check day of week against `running_days`)
       │
       ▼
Deduplicate train numbers
       │
       ▼
Query Live API only for today's active candidate trains
```
This avoids global queries across the entire national railway network and prevents API quota exhaustion.
