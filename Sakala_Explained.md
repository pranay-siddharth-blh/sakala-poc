# Sakala, Explained Simply

*How Karnataka delivers services to citizens and handles their complaints. Written to be read once, top to bottom.*
*Facts checked 13 Oct 2026 against the Act, the Rules, official portals and news reports. Anything unconfirmed is marked.*

---

## 1. The whole thing in one minute

Imagine the government as a huge shop with thousands of counters.

- **You ask for something** (a caste certificate, a ration card, a pension, a new electricity connection). This is a **service application**. You apply through **Seva Sindhu** or a department's own website or counter.
- **The government promises a deadline** for many of these services. That promise is a law called **Sakala**. If they are late, you can appeal, and the officer can be made to pay you ₹20 a day, up to ₹500.
- **Something goes wrong and you complain** (no drinking water, pension stopped, road broken, officer not responding). This is a **grievance**. Grievances go into a separate system called **iPGRS**, also known as **Janaspandana**.
- **In 2026 a new department, Praja Seva**, took charge of both the Sakala promise and the complaint system. It also holds grievance camps every Saturday.

So keep two boxes in your head:

| | **Application (Sakala world)** | **Complaint (iPGRS world)** |
|---|---|---|
| What it is | "Please give me this service" | "Something is wrong, please fix it" |
| Where it is filed | Seva Sindhu / department portal / counter | iPGRS portal, app, 1902 call, camps |
| ID you get | Sakala / **GSC number** (15 characters, e.g. `RD855S230002185`) | **Grievance ID** |
| Who handles it | Designated Officer | **LMF** (Last Mile Functionary), escalating to **L2**, then **L3** |
| Deadline | Fixed by law for each service | Set inside the system; no law fixes it |
| If it's late | Appeal → compensation from the officer's salary | Auto-escalation to a higher officer |

**Our 9,999-row dataset is from the complaint box (iPGRS), not the application box.** Only about 14% of the rows concern a service that Sakala covers.

---

## 2. How the Karnataka government is built

Think of it as a tree with four layers.

1. **The top.**
   - The **Chief Minister** and ministers decide policy. D.K. Shivakumar has been CM since 3 June 2026.
   - The **Chief Secretary** heads all government officers. Shalini Rajneesh held the post as of June 2026.
   - The Chief Secretary also chairs the state committee that reviews grievance redressal.
2. **Secretariat departments, about 40.**
   - Examples: Revenue, Rural Development & Panchayat Raj (RDPR), Urban Development, Housing, Energy, Food & Civil Supplies.
   - Each is run by a Secretary or Principal Secretary in Bengaluru.
   - These are the "departments" (the "41-department link" on karnataka.gov.in).
3. **Line departments**, the hands that actually do the work.
   - These are directorates, commissionerates, boards and companies under each department. Example: Energy → BESCOM, MESCOM, HESCOM, GESCOM, CESC (the electricity supply companies, or ESCOMs).
   - Our data has 195 of them.
4. **Field offices**, organised by place. The state has 31 districts, about 240 taluks, then hoblis, then villages and Gram Panchayats (GPs).

**The three field chains you meet most:**

| Department | Who's who, top to bottom |
|---|---|
| **Revenue** (land, certificates, pensions) | Deputy Commissioner (**DC**, district) → Assistant Commissioner (**AC**, sub-division) → **Tahsildar** (taluk) → Revenue Inspector (hobli) → Village Administrative Officer |
| **RDPR** (villages: water, roads, housing) | Zilla Panchayat **CEO** → Taluk Panchayat Executive Officer (**EO**) → Panchayat Development Officer (**PDO**, one per GP) |
| **Urban** (towns, under the Directorate of Municipal Administration, **DMA**) | City Corporation (Commissioner) → City Municipal Council (CMC) → Town Municipal Council (TMC) / Town Panchayat (TP), run by a Chief Officer. Bengaluru now has the **Greater Bengaluru Authority (GBA)**, which replaced BBMP. |

Engineers sit beside these chains: Assistant Engineer → Assistant Executive Engineer (**AEE**) → Executive Engineer (**EE**).

> Rule of thumb: **department = what kind of problem, geography = which officer.** Some things are purely geographic. Your electricity company and bus corporation are decided by your district, not by what you say.

---

## 3. Sakala: the government's written promise

### What it is
- The **Karnataka Sakala Services Act, 2011** was passed unanimously in Dec 2011 and came into force on **2 April 2012**.
- Its original name was the "Guarantee of Services to Citizens Act". That is why the receipt number is called a **GSC number**.
- "Sakala" means "on time". Its tagline: *"The promised day won't be missed."*
- Today it covers **1,446 notified services across 114 departments and organisations** (Sakala portal). Over 43 crore applications have been tracked.
- **Sakala is not where you apply.** It is the referee: it watches the clock, records the deadline and handles appeals. You apply on **Seva Sindhu** or the department's portal.

### The cast

| Role | Plain meaning |
|---|---|
| **Designated Officer (DO)** | The officer who must deliver your service (for example, the Tahsildar for a caste certificate) |
| **Competent Officer (CO)** | Hears your **first appeal**; can fine the DO |
| **Appellate Authority (AA)** | Hears your **second appeal**; Deputy Secretary rank or above |
| **Stipulated time** | The legal deadline for that service, fixed in the Schedule / Service Compendium |

### How a case runs, step by step
1. **You apply and get an acknowledgement** (Form B) with the GSC number. If documents are missing, the acknowledgement shows **no delivery date**, so the clock has not started.
2. **The clock runs** from the date of a complete application. **Public holidays don't count.**
3. **The DO delivers**, or **rejects in writing with reasons**, and tells you how to appeal.
4. **Late or rejected? You make a first appeal** to the CO within **30 days**. It is free, and you can do it through the **call centre (080-4455 4455)** using your acknowledgement number.
5. **The CO can do one of three things:** order the service, reject the appeal, or award **₹20 per day of delay, capped at ₹500**. You are paid immediately from office funds.
6. **The money is recovered from the officer.**
   - Within 15 days the CO issues a notice to the late officer.
   - The officer gets 7 days to explain.
   - The amount is then **cut from the officer's salary** and entered in **HRMS**, the employee payroll system, within 30 days.
7. **Still unhappy? You make a second appeal** to the AA within **60 days**. (The website FAQ wrongly says 30; that figure is the officer's own appeal period.)
8. **Bad track record.**
   - An officer who defaults **more than 7 times** gets an emailed show-cause notice and an enquiry.
   - The government must then act within a month.
   - An officer with zero defaults gets an appreciation letter in their record.
9. Every office must put up a **Sakala notice board** listing services, documents, deadlines and who to appeal to.

### Changes over time
- **2014 amendment:** the ₹20/day penalty also applies to COs and AAs who sit on appeals. It added the HRMS salary debit and the more-than-7-defaults enquiry.
- **2026 amendment** (passed by the Assembly on 27 Aug 2026; Council passage and Governor's assent *not yet confirmed*):
  - Compensation rates can be changed by notification.
  - The government can revise appeal orders itself.
  - A cost can be imposed on citizens who file **malicious or vexatious complaints**, but only after a hearing.

### What Sakala bosses watch
Their review reports track:
- overdue applications;
- rejection percentage, which is very high for pensions in some taluks;
- delayed disposals;
- offices with 7+ defaults;
- offices with zero applications;
- notice-board compliance.

---

## 4. Where people actually apply

| Name | What it is |
|---|---|
| **Seva Sindhu** | The state's main online portal for applying for services. Run by the **EDCS** directorate (Electronic Delivery of Citizen Services) under DPAR (e-Governance). |
| **Seva One / "Namma Seve"** | A single-login front door to many services; it appears on Seva Sindhu. Its exact link to the new Namma Seva app is unclear. |
| **Grama One** | Village service centres where an operator applies on your behalf |
| **Karnataka One / Bangalore One** | The same idea in towns and cities |
| **AJSK / Nadakacheri** | Hobli-level Revenue counters for certificates and pensions. Their receipt numbers start with **RD**; that is the Sakala number. |
| **Department portals** | Bhoomi (land records: RTC/Pahani), Kaveri (property registration), e-Swathu (village property, Form 9/11A), e-Khata (town property), and the ESCOM sites |
| **Citizen Service Centre (CSC)** | In our data, mostly **operators keying in petitions** at Grama One / Karnataka One counters, including at camps |

Useful IDs:
- **Family ID (Kutumba):** a household identity record.
- **FRUITS ID:** a farmer registry ID.
- **Aadhaar.**

---

## 5. iPGRS / Janaspandana: the complaint system

### What it is
- **iPGRS** stands for **Integrated Public Grievance Redressal System**. Its public brand is **Janaspandana**, meaning "people's response".
- It came out of a High Court order and a 2020 Government Order, and went live on **1 Nov 2021**.
- It is owned by the **Centre for e-Governance** and built by the **Centre for Smart Governance**. It runs on .NET/MSSQL in the State Data Centre.
- It covers 40+ departments, 250+ line departments and **17,000+ LMFs mapped down to GP level**.
- **Governance:** the **Chief Secretary chairs the State Level Review Committee**, and DCs chair the district committees.

*(Not to be confused with **Jana Spandana**, the CM's public-hearing events. Petitions from those events also get typed into iPGRS.)*

### How a citizen files
1. Register with a mobile number and OTP, using a Family ID or FRUITS ID if available.
2. Tick a box confirming the complaint is **not** about RTI, a court/sub-judice matter, a religious matter, a suggestion, or a government employee's own service matter. Those are excluded.
3. **Pick six dropdowns by hand:** Department → Line Department → Service → Grievance → Category → Sub-category. A keyword search helps, and there is a note: "can't find it? call 1902".
   **This manual picking is the pain point our POC fixes.** Citizens and operators pick wrong categories, as the government itself has said.
4. Give the **location of the problem**: district, taluk, village/GP, address, **pin code**.
5. Write the complaint (750 characters on the web form), attach files up to 2 MB, and submit. You get a **Grievance ID** and an SMS.

Other ways in:
- **1902 helpline**: operators type an English summary ("CITIZEN SAYS THAT…").
- **Mobile app.**
- **Walk-in centres and camps.**
- **CPGRAMS**: central-government complaints about Karnataka flow in, and replies flow back.

### LMF, L2, L3: who gets your complaint
- **LMF = Last Mile Functionary = L1.** The nearest field officer responsible for that problem in that place. Examples: the PDO of your GP for water, the Tahsildar for land records, the ESCOM AEE for power.
- **L2.** The next officer up, for example the Taluk Panchayat EO or an Executive Engineer.
- **L3.** The top level, for example the DC or ZP CEO.
- **Escalation is automatic:**
  - If L1 doesn't resolve the complaint in time, it jumps to L2's login, then to L3's.
  - After closure, the call centre phones the citizen for feedback. An unhappy citizen can escalate **twice**.
  - The exact days allowed per level are **not published**. A 2023 CM directive said 15 days.
- **ATR = Action Taken Report.** The officer's written account of what they did. It is **mandatory at every level** and is sent to the citizen as an SMS link.
- **Requests vs. grievances.** A "General Request" or "PrajaSeva Request" goes straight to the Department Secretary or Head of Department, not to an LMF. That is why some complaints sit with state-level desks.

> **Don't mix the ladders.** LMF → L2 → L3 is iPGRS escalation.
> Designated Officer → Competent Officer → Appellate Authority is the Sakala legal appeal.
> They are different things, run by different rules.

---

## 6. Praja Seva: the new boss and the Saturday camps

- **Praja Seva Department** ("Citizen Service Department"). The Cabinet approved it on **20 June 2026**.
  - It brings together the **Sakala Mission**, the **Public Grievances division** and **Administrative Reforms** under one roof.
  - Principal Secretary: **Harsha Gupta** (posted 3 July 2026).
  - The Sakala website now says "Department of Citizen Services".
- **Praja Seva Abhiyana / Andolana** is a campaign of grievance camps.
  - The CM launched it on **5 Sept 2026** at Kudligi; 26,387 complaints were logged at launch.
  - Camps run on **Saturdays** at taluk and hobli level. District in-charge ministers come on the **1st and 3rd Saturdays**; reports of MLAs taking the 2nd and 4th are unconfirmed.
  - Every department sets up a counter, and **Grama One / Karnataka One staff type petitions into iPGRS** on the spot.
  - Petitions are **reviewed the following Wednesday**: Tahsildar/EO 9–11 am, AC 11–1, DC 3–5 pm.
  - Rejections must give reasons within 21 days.
- **What they've announced for the future:**
  - **AI to route complaints to the right department.**
  - **iPGRS 2.0.**
  - A common citizen login.
  - A **"Namma Seva" app** with **5-star service ratings**, where a low rating means the officer must explain. Its launch is not yet confirmed.

---

## 7. One story that ties it all together

1. Lakshmamma, 68, applies at her hobli's Nadakacheri for an old-age pension (**Sandhya Suraksha**). She gets an RD/GSC number. **This is the Sakala world**, and the pension sanction has a legal deadline.
2. The pension is sanctioned, but money stops arriving after three months. That is not a Sakala delay; it is a payment problem. She goes to the **Saturday Praja Seva camp**.
3. A Grama One operator types her complaint into **iPGRS**. The operator picks Revenue → Directorate of Social Security & Pensions → Old-Age Schemes → … and her taluk. **This is the iPGRS world.**
4. The complaint lands with the **LMF**, the Tahsildar. If it's not resolved in time, it goes to L2, then L3. The officer files an **ATR**; the call centre rings her for feedback.
5. On **Wednesday** the Tahsildar, the AC and then the DC review the camp's pending petitions. The **Chief Secretary's** committee looks at the statewide picture.
6. If her *original application* had been late beyond the legal deadline, she could have appealed under **Sakala** and received up to ₹500 from the officer's salary.

---

## 8. Reading our dataset with this knowledge

| Column | What it really means |
|---|---|
| Department / Line Department / Service / Grievance / SubCat1 / SubCat2 | The six dropdowns a citizen or operator picked by hand |
| Service Type (Sakala / Non Sakala) | Whether that service is covered by the Sakala law (14% are) |
| District / Taluk / GP-Village | Where the problem is; this decides which LMF gets it |
| Status | InProcess, Closed by Officer, Resolved (Feedback Taken), or Registered & Sent for Scrutiny (the last only for Mobile App complaints, where someone checks the citizen's chosen category) |
| Officer Role (LMF / L2 / L3) | The level of the officer currently holding the complaint |
| Pending with / Closed By | The actual officer, written as designation-place (e.g. "Tahsildar-Grade 1-Hunsur") |
| Grievance Source | The channel. "Praja Seva Abhiyana" = Saturday camps; 3 Oct 2026 was a Saturday, hence 5,005 rows that day. |

---

## 9. Glossary (A to Z)

| Term | Meaning |
|---|---|
| **AA** | Appellate Authority; hears the second Sakala appeal |
| **AC** | Assistant Commissioner; revenue officer over a sub-division |
| **AEE / EE** | Assistant Executive Engineer / Executive Engineer |
| **AJSK** | Atal Ji Janasnehi Kendra, also called Nadakacheri; revenue service counter |
| **ATR** | Action Taken Report; the officer's written account of what they did |
| **Bhoomi** | Land-records system that issues RTC/Pahani |
| **CDPO** | Child Development Project Officer (Women & Child Development) |
| **CO** | Competent Officer; hears the first Sakala appeal and can fine the officer |
| **CPGRAMS** | Central government's grievance portal; linked to iPGRS |
| **CS** | Chief Secretary; head of the state's civil service |
| **DC** | Deputy Commissioner; head of a district |
| **DO** | Designated Officer; must deliver the Sakala service |
| **DPAR** | Department of Personnel & Administrative Reforms; e-Governance sits under it |
| **EDCS** | Electronic Delivery of Citizen Services directorate; runs Seva Sindhu |
| **EO** | Executive Officer of a Taluk Panchayat |
| **ESCOM** | Electricity supply company (BESCOM, MESCOM, HESCOM, GESCOM, CESC), decided by district |
| **GBA** | Greater Bengaluru Authority; replaced BBMP |
| **GSC number** | Sakala application number ("Guarantee of Services to Citizens") |
| **Gruha Lakshmi / Gruha Jyothi / Yuva Nidhi / Anna Bhagya / Shakti** | The five "guarantee" welfare schemes, which generate many complaints |
| **HRMS** | Government employee payroll/HR system; where Sakala salary debits are recorded |
| **Hobli** | A cluster of villages within a taluk |
| **iPGRS / Janaspandana** | The state grievance system |
| **Khata / e-Khata** | Property ownership record in towns |
| **LGD** | Local Government Directory; official codes for districts, taluks and GPs |
| **LMF (L1)** | Last Mile Functionary; first field officer for a complaint |
| **L2 / L3** | Escalation levels above the LMF |
| **Mutation** | Updating land ownership in records after sale or inheritance ("pouthi khata" is inheritance) |
| **PDO** | Panchayat Development Officer; runs a Gram Panchayat |
| **Podi / Tatkal Podi** | Sub-dividing a land survey number into individual plots |
| **Praja Seva** | New department (2026) over Sakala and grievances; also the Saturday camps |
| **RTC / Pahani** | Record of Rights, Tenancy and Crops; the basic land document |
| **Sakala** | The 2011 law guaranteeing deadlines for notified services |
| **Sandhya Suraksha** | State old-age pension scheme |
| **Seva Sindhu** | The main portal for applying for services |
| **Service Compendium** | Official list of every Sakala service and its deadline (latest dated 5 May 2026) |
| **Tahsildar** | Head of a taluk's revenue office |
| **ZP CEO** | Chief Executive Officer of a Zilla (district) Panchayat |

---

### Five things an expert never gets wrong
1. **Application ≠ complaint.** Sakala deadlines and compensation apply only to notified service applications that have a GSC number.
2. **LMF/L2/L3 ≠ DO/CO/AA.** The first is complaint escalation; the second is legal appeal.
3. **Location decides the officer**, and the location of the problem matters, not the citizen's home address.
4. **"Closed by Officer" doesn't mean the problem is solved.** Only 64 of 9,999 rows have citizen feedback.
5. **The government has already said it wants AI routing.** What wins its trust is AI that stays inside the official lists, explains itself and lets officers correct it.
