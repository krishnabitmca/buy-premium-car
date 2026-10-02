# CarScanner Release Report

## Release under test

- Branch: `feat/source-adapter-control-plane`
- Commit: `23f295ae2636291bf7f69f9f4966e313e846dfdb`
- Deployment: `dpl_8tm1trHos8HFeC4HWT7AAM6bCujo`
- Deployment URL: `https://buy-premium-7b1fqcjim-premium-car-deal-radar.vercel.app`
- Deployment state: READY
- Certification status: **NOT CERTIFIED**

## Why this release is not certified

Backend/source-planning tests and deployment health do not establish that the complete browser journey works.

A customer-visible issue has been reported with the Brand dropdown. The current release therefore remains uncertified until the browser journey is executed and the defect is reproduced/resolved.

## Current evidence

- Homepage: production endpoint responds successfully.
- Catalog API: `/api/catalog` responds HTTP 200 and returns a live brand catalog.
- Browser-level Brand dropdown: **FAIL / requires reproduction and root-cause verification**.
- Model loading: NOT TESTED end-to-end.
- Search journey: NOT CERTIFIED end-to-end.
- Full left-filter matrix: NOT CERTIFIED.
- Production browser smoke: NOT CERTIFIED.

## P0 scenarios

| ID | Scenario | Status |
|---|---|---|
| P0-001 | Homepage loads | PASS |
| P0-002 | Brand dropdown populates | FAIL |
| P0-003 | Select BMW and load BMW models | BLOCKED |
| P0-004 | Select Audi and load Audi models | BLOCKED |
| P0-005 | Select Mercedes-Benz and load models | BLOCKED |
| P0-006 | Brand + All Models search | BLOCKED |
| P0-007 | Search submission | BLOCKED |
| P0-008 | Clear All | NOT TESTED |
| P0-009 | No blocking JavaScript error | NOT TESTED |

## Search scenarios

| ID | Scenario | Status |
|---|---|---|
| S-001 | Audi / All Models / Used | NOT TESTED |
| S-002 | BMW / All Models / Used | NOT TESTED |
| S-003 | Audi / Demo | NOT TESTED |
| S-004 | Audi / Used + Demo | NOT TESTED |
| S-005 | BMW X5 / ₹30–40L | NOT TESTED |
| S-006 | Fuel × price × age | NOT TESTED |
| S-007 | Seller city × destination | NOT TESTED |
| S-008 | Invalid min > max | NOT TESTED |
| S-009 | Interstate listing with Bengaluru destination | NOT TESTED |
| S-010 | Zero-result combination | NOT TESTED |
| S-011 | Source failure isolation | NOT TESTED in production |
| S-012 | Duplicate listing handling | NOT TESTED in production |

## Visible filter coverage

The current deployed UI visibly exposes:

- Condition
- Price range
- Fuel type
- Seller location
- Age
- Destination
- Sort
- Quick filters for fuel/body type

The following previously proposed filters are **not currently visible in the deployed sidebar**:

- Transmission
- Body type as a dedicated sidebar control
- Mileage
- Seller type
- Ownership
- Features

Those must not be reported as tested UI scenarios until they exist in the customer-facing contract.

## Release decision

**NOT CERTIFIED FOR CUSTOMER RELEASE**

Reason: the primary catalog-selection journey is not verified end-to-end, and the reported Brand dropdown issue blocks downstream model/search journeys.

## Next certification sequence

1. Reproduce Brand dropdown failure in the deployed browser.
2. Capture browser console/network evidence.
3. Fix the defect.
4. Add a browser regression test for catalog loading.
5. Run P0 catalog/search journeys.
6. Run the filter matrix.
7. Run source isolation and zero-result tests.
8. Publish a new report with actual PASS/FAIL evidence.
