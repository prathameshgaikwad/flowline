# Flowline Standards Packs

**Status: POC rule packs. Not a compliance certificate. A licensed engineer and the local authority govern the design.**

Flowline v1 ships two small, cited rule packs so the same design can be checked under an India-first profile and a US profile. Each rule in the UI and report names its source. The packs intentionally cover only the checks the MVP can measure.

## Sources

- **NBC 2016 Part 3** — Development Control Rules and General Building Requirements. Room minimums for WC/bathroom; door widths; accessibility. Bureau of Indian Standards.
- **NBC 2016 Part 9** — Plumbing Services. Minimum soil/waste/vent sizes, stack and drainage provisions.
- **IS 1742:1983** — Code of practice for building drainage. Drain gradients and drainage design principles.
- **IS 5329:1983** — Code of practice for sanitary pipework above ground for buildings.
- **IS 2064:1993** — Code of practice for selection, installation, and maintenance of sanitary appliances. Fixture spacing and heights.
- **IPC 2021/2024 Chapter 4** — Fixture clearances (405.3.1) and shower compartments (421.4).
- **IPC Chapter 7** — Drainage fixture units (Table 709.1).
- **IPC Chapter 9** — Vent distances (Table 909.1).
- **Indian Plumbing Association (IPA) guidance** — Practical drainage slopes and installation notes. Used as a cross-check, not as code.

Links used during research:

- https://law.resource.org/pub/in/bis/S03/is.1742.1983.pdf
- https://www.bis.gov.in/standards/national-building-code/
- https://codes.iccsafe.org/s/IPC2018P5/chapter-4-fixtures-faucets-and-fixture-fittings/IPC2018P5-Ch04-Sec405.3.1
- https://up.codes/viewer/general-services-administration/ipc-2024/chapter/4/fixtures-faucets-and-fixture-fittings
- https://up.codes/viewer/knoxville/ipc-2024/chapter/9/vents
- https://home4.nyc.gov/assets/buildings/codes-pdf/cons_codes_2022/2022PC_Chapter7_SanitaryDrainageWBwm.pdf

## India pack (`india_nbc_2016`)

| Rule | Value used | Source |
|---|---|---|
| WC-only room | >= 1.1 m2, >= 0.9 m wide | NBC 2016 Part 3 |
| Bathroom-only room | >= 1.8 m2 | NBC 2016 Part 3 |
| Combined bath + WC | >= 2.8 m2, >= 1.2 m wide | NBC 2016 Part 3 |
| Clear height | >= 2.2 m (not measured in 2D) | NBC 2016 Part 3 |
| Door clear width | >= 750 mm | NBC 2016 Part 3 |
| WC center to side wall | >= 380 mm; target 400-450 mm | IPC 405.3.1; IS 2064 practice |
| WC clear in front | >= 533 mm; target 600 mm | IPC 405.3.1 |
| Fixture center-to-center | >= 762 mm | IPC 405.3.1 |
| Basin center to side wall | >= 380 mm; target 450-500 mm | IPC 405.3.1; IS 2064 |
| Basin clear in front | >= 533 mm; target 700 mm | IPC 405.3.1; Indian practice |
| Shower zone | >= 762 x 762 mm; target 900 x 900 mm | IPC 421.4 |
| Shower access | >= 559 mm clear | IPC 421.4.2 |
| WC branch | 100 mm soil | NBC 2016 Part 9; IS 1742 |
| Basin branch | 40 mm waste | NBC 2016 Part 9 |
| Shower branch | 50 mm waste | NBC 2016 Part 9 |
| Kitchen sink branch | 50 mm waste | NBC 2016 Part 9 |
| Vent | 50 mm minimum | NBC 2016 Part 9 |
| Stack | 100 mm minimum for a WC | NBC 2016 Part 9; IS 5329 |
| Horizontal slope, 100 mm | 1:50 to 1:100; default 1:60 | IS 1742; IPA cross-check |
| Horizontal slope, 40-50 mm | 1:40 to 1:60; default 1:50 | IS 1742; IPA cross-check |
| Fixture units | WC 4, basin 1, shower 2 (informational) | IPC 709.1 cross-check |

Note: published Indian sources differ on the exact minimum gradient (IS 1742 table values, IPA recommendations, and common practice). Flowline uses the conservative 1:50-1:100 band for 100 mm and records the selected slope in the report. Verify the local authority's requirement before construction.

## US pack (`us_ipc_2021`)

| Rule | Value used | Source |
|---|---|---|
| WC center to side wall | >= 381 mm | IPC 405.3.1 |
| WC clear in front | >= 533 mm | IPC 405.3.1 |
| WC compartment | >= 762 mm wide x 1524 mm deep | IPC 405.3.1 |
| Fixture center-to-center | >= 762 mm | IPC 405.3.1 |
| Basin center to side wall | >= 381 mm | IPC 405.3.1 |
| Basin clear in front | >= 533 mm | IPC 405.3.1 |
| Shower zone | >= 762 x 762 mm; >= 0.58 m2 | IPC 421.4 |
| Shower access | >= 559 mm | IPC 421.4.2 |
| WC branch | 76 mm (3 in) | IPC drainage table |
| Basin branch | 32 mm (1.25 in) | IPC drainage table |
| Shower branch | 50 mm (2 in) | IPC drainage table |
| Vent | 32 mm minimum | IPC 906.2 |
| Stack | 76 mm minimum in v1; final size per DFU table | IPC Chapter 7 |
| Horizontal slope | 20.8 mm/m (1/4 in/ft) for small; 10.4 mm/m (1/8 in/ft) for 3 in+ | IPC 704 |
| Fixture units | WC 3-4, basin 1, shower 2 | IPC 709.1 |
| Trap-to-vent distance | 1.5 m (32 mm), 1.8 m (40 mm), 2.4 m (50 mm) | IPC 909.1 |

## Assumptions in v1

- Only drainage is designed. Water supply and vent piping are not modeled.
- Every fixture is assumed to have a trap and an individual branch to the stack.
- The stack is assumed to continue vertically and terminate above the roof; no stack vent geometry is drawn.
- A branch longer than 3 m without a modeled vent produces a WARNING, not an ERROR.
- Room height is not checked in a 2D plan.
- Pipe capacity is checked by minimum branch size; full DFU stack sizing is a later feature.
- Clearance checks use fixture footprints and simplified rectangles, not manufacturer geometry.

## Disclaimer shown in the UI and reports

> Flowline is a design assistant. It checks a small, cited rule pack, not the full code. Local amendments, manufacturer instructions, structural constraints, and a licensed engineer's review govern the issued design.
