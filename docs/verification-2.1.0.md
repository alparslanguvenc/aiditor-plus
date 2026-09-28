# AI-ditor Plus 2.1.0 validation

2026-09-28, macOS arm64. Test accounts and articles were synthetic, stored in disposable directories.

- 68 Python regression tests: existing accounts, ZIP, imports and desktop behavior; new Word packages, native editable tables, merged cells, PDF assets, page variants, safe tokens, citation targets and ambiguity, owner-scoped downloads.
- Four Chromium workflows: main journal workflow, save/import races, ZIP downloads, and new Word download/settings/token/persistence/mobile workflow.
- Native WebKit: login, Word and ZIP buttons, authenticated JS-to-Python save bridge, byte-preserving output, autosave and close. File picker replaced only for the disposable test destination.
- DOCX layout review: four covers with multi-page bodies (12 pages), dense bilingual cover (1 page), long table with repeating headers (5 pages). Rendered using bundled LibreOffice; every page visually inspected. Original text and editable table/paragraph structures checked separately.
- LaTeX: four covers plus an even-start long-table case compiled with Tectonic/XeTeX (16 pages total); every page visually inspected. Internal PDF links and named reference destinations inspected.
- Frozen package: actual executable generated and downloaded Word with a PDF logo (native PDFium), correct header parts and citation target; LaTeX ZIP passed CRC. This smoke check now runs before creating macOS/Windows installers.
- Microsoft Word for Mac: opens without repair or forced field-update prompt. Print preview verified page 88 on the cover and page 89 with the odd header on the next physical page. PAGE fields remain editable and update during pagination/printing.

## Compatibility boundary

Word and LaTeX do not guarantee identical line/page breaks. Long Word cover content can continue on another page rather than being cropped. Missing local fonts may be substituted. PDF image assets use their first page.

Microsoft Word uses a section's starting page number to choose its odd/even header. LibreOffice's rendered output can instead use physical page order, so an even start can reverse the apparent parity there. The exporter retains Microsoft Word's native header/section semantics. See [Microsoft's documented behavior](https://learn.microsoft.com/en-us/openspecs/office_standards/ms-oe376/66274c6b-6552-47b6-a1b1-3cfcd9c064f4).

Citation linking supports recognized APA author/year prose in article body sections. Ambiguous names/years are left unlinked; no bibliographic metadata is invented. Numeric styles, abbreviated multi-year citations, and nonstandard source lines require final editorial review. This is navigation, not scholarly reference verification.

macOS packages require macOS 13+ because of the bundled PDFium build. PDFium notices are included in dependency metadata inside the app. Windows packaging is validated by the release workflow; macOS local checks do not substitute for that CI result.
