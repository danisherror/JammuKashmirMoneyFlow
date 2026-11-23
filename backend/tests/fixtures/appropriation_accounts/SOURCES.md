# Appropriation Accounts fixtures

Each fixture holds only the "Summary of Appropriation Accounts" pages, cut from the official
Appropriation Accounts of the Union Territory of Jammu and Kashmir (published by the CAG). The
pages were copied unchanged with `pypdfium2`, so the text layer is the original one.

Downloaded 2026-11-22.

| Fixture | Year | Pages of original | Original PDF | SHA-256 of original |
|---|---|---|---|---|
| `jk-appropriation-2021-22-summary.pdf` | 2021-22 | 11–15 | https://cag.gov.in/uploads/state_accounts_report/account-report-Appropriation-2021-22-English-08-12-2022-063aa89a8638765-77820288.pdf (also on saiindia.gov.in) | `9b66c686bf4b6c9c56bb63029699d6e18195fd5f7b8c76e1ed3ffc5f171413e7` |
| `jk-appropriation-2022-23-summary.pdf` | 2022-23 | 12–16 | https://cag.gov.in/uploads/state_accounts_report/account-report-Appropriation-2022-23-J-K-English-28-02-2024-066bf1b4e8f88f3-67986467.pdf | `0f6df1b40ca39d3703e9361b08de24f90b8a51b461867ba91a52dabc7979bcea` |
| `jk-appropriation-2023-24-summary.pdf` | 2023-24 | 9–13 | https://cag.gov.in/uploads/state_accounts_report/account-report-Appropriation-2023-24-UT-JK-English-28-03-2025-069d791c2d23943-29281571.pdf | `8c8133ea414c69513c0a6b7ebef1297f5664b0565dc8498391d04e30fa6290b8` |

The parser gives the same result on the full original PDFs as on these cut-down fixtures
(checked 2026-11-22).

## Grant-page fixtures

`jk-appropriation-<year>-grants.pdf` hold the grant pages ("GRANT NO. ..." onwards) of a few
grants per year, cut the same way from the same original PDFs (SHA-256 above), on 2026-11-22.
They have no summary pages; the tests take the summary from the `-summary.pdf` fixtures. The
grants were picked for the layout quirks they show (see `parsers/appropriation_details.py`).

| Fixture | PDF pages of original | Grants | Quirks covered |
|---|---|---|---|
| `jk-appropriation-2021-22-grants.pdf` | 28–33, 40–43, 59, 142–146, 158–160 | 2, 6, 9, 28, 34 | doubled bold glyphs, "Supplementary/ Re-appropriation", major-head name wrapped onto "Voted", non-head table (works establishment charges), withdrawn charged block, footnote in a table, missing "O" label, revenue head printed under "Capital Section" |
| `jk-appropriation-2022-23-grants.pdf` | 30–35, 41–44, 149–152 | 2, 5, 6, 32, 33 | "R" amount on the line below its label, grant with no amounts (Mining), shifted page margin, printed arithmetic error (grant 32), note numbers skipping 6 |
| `jk-appropriation-2023-24-grants.pdf` | 19–30, 117–119, 137–138, 147–148 | 1, 2, 24, 31, 36 | every note-table type, branch printed with no row, table printed without a header, "Capital Section" heading in the section block, block without a "Voted" label |

## Appendix II (recoveries) fixtures

`jk-appropriation-<year>-recoveries.pdf` hold, cut the same way from the same original PDFs
(SHA-256 above) on 2026-11-23: first the reconciliation page at the end of the summary ("Deduct
Recoveries shown in Appendix-II"), then the Appendix II pages ("Grant-wise details of estimates and
actuals in respect of recoveries adjusted in the accounts in reduction of expenditure"), left and
right pages in pairs. `tests/pdf_fixtures.py` merges them with the summary and grant-page fixtures in
the original's page order for the loader and route tests.

| Fixture | PDF pages of original | Quirks covered |
|---|---|---|
| `jk-appropriation-2021-22-recoveries.pdf` | 16, 168–169 | blank nil cells instead of "-" (grant 15 and Total, Revenue); grant name printed truncated ("Food, Civil Supplies and Consumer") |
| `jk-appropriation-2022-23-recoveries.pdf` | 17, 162–163 | amounts printed between the two lines of a wrapped grant name |
| `jk-appropriation-2023-24-recoveries.pdf` | 14, 152–155 | every grant listed, two spreads |
