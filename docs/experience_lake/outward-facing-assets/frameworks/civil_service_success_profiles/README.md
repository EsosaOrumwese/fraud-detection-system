# Civil Service Success Profiles Source Capture

Created: 2026-05-03

This folder is for capturing official GOV.UK Success Profiles material as source reference for Civil Service applications.

It is not an interpretation guide and not a supporting-statement writing guide.

## Source Start Point

- Success Profiles main page: https://www.gov.uk/government/publications/success-profiles

## Pages To Capture

The main Success Profiles page points to these core pages:

1. Success Profiles main page
   - https://www.gov.uk/government/publications/success-profiles
2. Candidate overview
   - https://www.gov.uk/government/publications/success-profiles/success-profiles-candidate-overview
3. Experience
   - https://www.gov.uk/government/publications/success-profiles/success-profiles-experience
4. Strengths
   - https://www.gov.uk/government/publications/success-profiles/success-profiles-strengths
5. Civil Service behaviours
   - https://www.gov.uk/government/publications/success-profiles/success-profiles-civil-service-behaviours
6. Technical
   - https://www.gov.uk/government/publications/success-profiles/success-profiles-technical
7. Ability
   - https://www.gov.uk/government/publications/success-profiles/success-profiles-ability
8. A brief guide to competencies
   - https://www.gov.uk/guidance/a-brief-guide-to-competencies

The competency guide also links a PDF source:

- Civil Service competency framework PDF
  - https://www.gov.uk/government/uploads/system/uploads/attachment_data/file/436073/cscf_fulla4potrait_2013-2017_v2d.pdf

## Folder Structure

- `scripts/`: local crawler/extraction scripts.
- `sources/`: downloaded official source pages and any linked source files.
- `outputs/`: generated markdown capture/index files.

## Capture Method

Use `scripts/fetch_success_profiles_sources.py` to fetch the GOV.UK pages listed above and build a local markdown capture from the visible page content.

The same script also downloads the linked Civil Service competency framework PDF into `sources/`.

The generated output should preserve the source order:

1. main Success Profiles page
2. candidate overview
3. STAR/CAR competency guide
4. experience
5. strengths
6. behaviours
7. technical
8. ability

## Copyright / Reuse Note

GOV.UK content is normally published under the Open Government Licence unless otherwise stated on the page.

Keep source attribution and links in any derived reference document.
