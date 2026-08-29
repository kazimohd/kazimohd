# Regulatory application and deadline monitor

This workflow checks official Central, Maharashtra State and MUHS pages at 7:00 PM IST every two days. It is limited to institutional proposal notices concerning:

- new MBBS colleges and increases in MBBS intake;
- new BDS colleges;
- new postgraduate Ayurveda courses;
- M.Sc. Nursing and Post Basic B.Sc. Nursing programmes; and
- MPT programmes.

The first successful check establishes the baseline. Later checks create and assign a GitHub issue to `@kazimohd` only when a new matching announcement appears. Routine counselling, student admissions, examinations, recruitment and publicity notices are excluded.

Official websites sometimes change layout, block automated requests, or publish scanned notices under generic links. Every alert must therefore be verified on the authority's website for the academic year, last date, fee, required documents, portal and later corrigenda.

No institution names, recommendation letters or private case documents are stored by this monitor. Because this repository is public, each alert contains only publicly issued regulatory information.
