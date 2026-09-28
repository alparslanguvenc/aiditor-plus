# AI-ditor Plus 2.2.0 validation

2026-09-28, macOS arm64. Synthetic journals, authors and articles were used in isolated temporary data directories. The reference article and its journal identity are not distributed with the application.

- 74 Python regression tests passed, including all five editable cover templates; true first-page footer placement; preservation of custom first-page footer content; no note repetition or numbering restart in the body; separate and long English summaries; English-only output; bottom DOI placement; citation targets, tables and authenticated downloads.
- Five Chromium workflows passed: accounts and journal workflow; save/import races; ZIP downloads; Word/settings/mobile; and the new social-science preset, thumbnail, persisted summary heading, separate editable summary, ZIP and mobile layout.
- Visual review covered 17 rendered Word pages across all five templates and standard, long-summary and English-only variants. First-page notes remain at the bottom, and body pages are clear of cover notes.
- Three new-template LaTeX examples compiled with Tectonic/XeTeX (9 pages). All pages were visually reviewed; internal reference destinations remained present. The gallery thumbnail comes from a compiled synthetic example.
- Microsoft Word for Mac opened the new DOCX without repair or forced update prompts. Print preview confirmed bottom-anchored cover notes, a separate English summary and continued numbering (89 on the cover, 90 on the next page). The test document was closed without modifying it.
- Three browser workflows also passed against the final frozen macOS executable: Word/settings/native download bytes, the new template, and ZIP download/error handling. The DMG passed `hdiutil verify`; the installed preview asset matches the final source.
- The frozen macOS executable generated DOCX with a PDF logo, real footer/header parts, separate body section, citation target and the new preview image. Its authenticated ZIP export passed archive integrity checks. This package smoke check is also required by Windows CI before installer creation.

## Boundaries

The social-science preset adapts the supplied page design; it is not a claim of pixel-identical typesetting. Word and LaTeX may wrap text differently. Very long Word cover content can continue onto a second page; text is not cropped. Cover notes too long for one page produce an actionable error. Existing downloaded DOCX files must be generated again to receive the footer correction.

Microsoft Word chooses odd/even headers from issue page numbers. LibreOffice may instead use physical page order for an even-starting document; final parity should be checked in Word or LaTeX. See the compatibility notes in [2.1.0 validation](verification-2.1.0.md).

GitHub release publication is gated by Linux/macOS/Windows regression tests, the browser workflows, and both installer jobs. Local macOS validation alone does not certify Windows packaging. The application remains MIT licensed and developed without a profit motive; existing local account data is stored outside the app bundle.
