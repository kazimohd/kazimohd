# Regulatory application and deadline monitor

This workflow checks official Central, Maharashtra State and MUHS pages at approximately **7:00 PM IST every two days**. It is limited to institutional proposal notices concerning:

- new MBBS colleges and increases in MBBS intake;
- new BDS colleges;
- new postgraduate Ayurveda courses;
- M.Sc. Nursing and Post Basic B.Sc. Nursing programmes; and
- MPT programmes.

The first successful check establishes the baseline. Later checks remain silent unless a new matching announcement appears. When one is found, the workflow creates a dedicated alert pull request and requests review from `@kazimohd`, so GitHub can send an account/email/mobile notification according to the user's GitHub notification settings.

Routine counselling, student admissions, examinations, recruitment, results and publicity notices are excluded. The workflow monitors NMC, NDC, NCISM, INC, NCAHP public pages, MUHS, Maharashtra Medical Education and Drugs Department, DMER, Maharashtra Nursing Council and Maharashtra State OT/PT Council.

Official websites sometimes change layout, block automated requests, or publish scanned notices under generic links. Every alert must therefore be verified on the authority's official website for the academic year, last date, fee, required documents, portal and later corrigenda.

No institution names, recommendation letters or private case documents are stored by this monitor. Because this repository is public, every alert contains only publicly issued regulatory information.
