# Legal Aid BD — Legal Reviewer Recruitment & Outreach Templates

**Document Identifier**: `DOC-REV-OUTREACH-W0-001`  
**Purpose**: Ready-to-send outreach templates for recruiting Bangladesh legal reviewers across faculty, advocates, and advanced law students.  
**Current Confirmation Status**: **NOT CONFIRMED** (Awaiting outreach dispatch and reviewer signature)  
**Fallback Operational State**: All initial annotations are strictly labeled `researcher_annotated_provisional`. No claims of lawyer-validated legal advice may be made until a formal reviewer agreement is executed.

---

## 1. Candidate Reviewer Requirements by Legal Domain

To ensure annotation quality, reviewers must meet domain-specific criteria:

| Domain | Target Statutes | Minimum Student Qualification | Minimum Professional Qualification |
|---|---|---|---|
| **Land & Tenancy** | *Premises Rent Control Act, 1991*; *Transfer of Property Act, 1882*; *State Acquisition and Tenancy Act, 1950* | Completed Land Law / Property Law with minimum Grade B+ / 3.5 GPA | Enrolled Advocate with 2+ years civil/property court practice or LL.M. researcher |
| **Consumer Protection** | *Consumer Rights Protection Act, 2009*; DNCRP Regulations | Completed Law of Torts / Special Penal Laws | Advocate with experience in Magistrate Court / DNCRP hearings or legal aid researcher |
| **Labour & Employment** | *Bangladesh Labour Act, 2006*; *Labour Rules, 2015* | Completed Labour Law coursework | Enrolled Advocate with Labour Court experience or trade union / corporate HR legal advisor |
| **Contractual Obligations** | *The Contract Act, 1872*; *Specific Relief Act, 1877* | Completed Law of Contract & Specific Relief | Enrolled Advocate in commercial/contract litigation or corporate commercial lawyer |

---

## 2. Practical Outreach Email Templates

### Template A: For Bangladesh Law Faculty Members / Senior Legal Academics

**Subject**: Collaboration on Empirical Legal NLP Research: Legal Aid Information Retrieval for Bangladesh Law

Dear [Dr. / Professor / Mr. / Ms. Last Name],

I hope this email finds you well. 

My name is [Your Name], and I am conducting an empirical research project titled **"Cross-Script and Multilingual Legal Retrieval for Bangladesh: Evaluating Banglish-Aware Retrieval, Hybrid Search, and Citation Grounding."** 

Our research investigates how machine learning retrieval architectures (lexical BM25, multilingual bi-encoders, and transliteration-aware models) perform when Bangladeshi citizens seek information using informal Banglish (Bengali in Latin script), Bangla Unicode, and English across four statutory domains: **Land & Tenancy, Consumer Protection, Labour Law, and Contract Law**.

To ensure our benchmark dataset is methodologically sound and reflects accurate Bangladesh statutory law, we are establishing a structured legal review protocol. We are seeking a qualified legal scholar or faculty member to advise on our annotation framework and review a targeted sample of statutory annotations.

**Summary of Reviewer Involvement**:
- **Week 3 (Annotation Review)**: Reviewing a shared subset of approximately 30–40 legal query scenarios to validate whether the identified statutory provisions (Act and Section) correctly govern the scenario.
- **Week 8 (Quality Audit)**: Reviewing a small sample (~20 cases) of high-stakes retrieval edge cases to evaluate claim-level citation grounding and statutory ambiguity.
- **Estimated Commitment**: ~12–16 total hours spread across two evaluation windows.

In recognition of substantive intellectual contributions to experimental design, annotation taxonomy, and statutory interpretation, co-authorship on peer-reviewed academic manuscripts (or formal institutional acknowledgment, per your preference and ICMJE guidelines) will be proudly extended.

Our complete onboarding protocol and annotation rubrics are detailed in our project documentation. Would you be open to a brief 15-minute conversation or reviewing our research protocol this week?

Thank you very much for your time, scholarship, and consideration.

Warm regards,

**[Your Full Name]**  
Lead AI Research Engineer, Legal Aid BD Project  
[Your Institution / Contact Information]  
[Your Phone Number / Email Address]  

---

### Template B: For Enrolled Advocates (Supreme Court or District Bar)

**Subject**: Invitation to Review Legal Aid AI Benchmark: Statutory Retrieval for Bangladesh Citizens

Dear Advocate [Last Name],

I hope you are having a productive week.

I am writing to invite you to participate as an expert legal advisor for **Legal Aid BD**, an independent research project evaluating how AI legal retrieval systems can accurately find Bangladesh statutory provisions when everyday citizens ask questions in **Bangla, Banglish, and English**.

We are currently validating our core statutory corpus across four practical legal areas:
1. *Land & Tenancy* (Premises Rent Control Act, Transfer of Property Act)
2. *Labour & Employment* (Bangladesh Labour Act, 2006)
3. *Consumer Protection* (Consumer Rights Protection Act, 2009)
4. *Contracts* (The Contract Act, 1872)

**What the Role Involves**:
- We have created realistic factual scenarios representing common citizen legal problems.
- We need a practicing advocate to verify whether the designated legal sections (e.g., Section 18 of the Premises Rent Control Act, Section 26 of the Labour Act) genuinely address the user's issue.
- Verify whether system-generated legal answers accurately quote the law without inventing ("hallucinating") sections.
- **Time Commitment**: Approximately 2–3 hours per week across two specific milestones (total ~10–12 hours).

We adhere strictly to legal research ethics: your review does not constitute legal counsel, creates no client liability, and is purely for benchmark validation. Your contributions can be credited via formal academic co-authorship or acknowledgment.

If you are interested in contributing to legal informatics in Bangladesh, I would be grateful for the opportunity to send you our brief 2-page reviewer protocol.

Best regards,

**[Your Full Name]**  
Legal Aid BD Research Team  
[Your Contact Information]  

---

### Template C: For Advanced Law Students / Legal Interns (LL.B. 3rd/4th Year or LL.M.)

**Subject**: Research Contributor Opportunity: Benchmark Annotation for Bangladesh Legal AI

Dear [Student Name],

I am reaching out regarding an opportunity to contribute to a research project on legal information retrieval and artificial intelligence for Bangladesh law (**Legal Aid BD**).

We are constructing a gold-standard multilingual legal benchmark across **Land, Consumer, Labour, and Contract Law**. We are selecting motivated 3rd/4th-year LL.B. students or LL.M. candidates to serve as **Tier 1 Legal Annotators**.

**What You Will Do**:
- Work with statutory texts from `bdlaws.minlaw.gov.bd` to map citizen legal questions (written in Bangla, Banglish, and English) to the exact Acts and Sections that govern them.
- Document any statutory ambiguities or gaps where the law is silent or subject to judicial interpretation.
- Gain hands-on experience at the intersection of Bangladesh statutory law and artificial intelligence research.

**Commitment & Recognition**:
- Approximately 12–15 hours during Week 3 of the project.
- Formal Certificate of Research Contribution, formal acknowledgment in published academic papers, and detailed reference letters for graduate study applications.

If you have completed relevant coursework in Property Law, Labour Law, or Contract Law and are interested, please reply with your current year of study and a brief mention of the legal subjects you have completed.

Sincerely,

**[Your Full Name]**  
Legal Aid BD Project  
[Your Contact Information]  

---

## 3. Explicit Remaining Actions to Achieve "VERIFIED COMPLETE" on Task 0.1

1. **Dispatch Outreach**: Send Template A, B, or C to candidate reviewers across the University of Dhaka, BRAC University, Chittagong University, or the Supreme Court Bar Association.
2. **Execute Reviewer Agreement**: Obtain a countersigned copy of `docs/reviewer_protocol.md` from at least one reviewer.
3. **Log Confirmed Profile**: Record the reviewer's qualifications, Bar enrollment status, and verified domains in Section 2 of `docs/reviewer_protocol.md`.
4. **Transition from Fallback**: Once confirmed, update the benchmark labeling tier from `researcher_annotated_provisional` to `lawyer_validated`.
