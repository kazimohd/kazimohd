# Regulatory application, deadline and extension monitor

This workflow checks official Central, Maharashtra State and MUHS pages at approximately **7:00 PM IST every two days**. It is limited to institutional proposal notices concerning:

- new MBBS colleges and increases in MBBS intake;
- new BDS colleges;
- new postgraduate Ayurveda courses;
- M.Sc. Nursing and Post Basic B.Sc. Nursing programmes; and
- MPT programmes.

In addition to fresh application notices, it explicitly monitors whether any relevant **last date, application window, proposal-submission date, portal period or late-fee date is extended, revised or reopened**. It also detects relevant corrigenda, addenda and revised schedules in English, Marathi and Hindi.

The first successful check establishes the baseline. Later checks remain silent unless a new matching announcement or relevant date extension appears. When one is found, the workflow creates a dedicated alert pull request and requests review from `@kazimohd`, so GitHub can send an account, email or mobile notification according to the user's GitHub notification settings.

Routine counselling, student admissions, examinations, recruitment, results and publicity notices—including extensions limited to those matters—are excluded. The workflow monitors NMC, NDC, NCISM, INC, NCAHP public pages, MUHS, Maharashtra Medical Education and Drugs Department, DMER, Maharashtra Nursing Council and Maharashtra State OT/PT Council.

Every extension alert should be checked on the original authority website for the academic year, original last date, extended last date, late-fee period, fee, required documents, portal and any later corrigendum.

No institution names, recommendation letters or private case documents are stored by this monitor. Because this repository is public, every alert contains only publicly issued regulatory information.
