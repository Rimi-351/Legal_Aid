#!/usr/bin/env python3
"""
scripts/build_multilingual_benchmark.py
----------------------------------------
Constructs the Week 3 multilingual legal evaluation benchmark (200 queries,
50 scenarios across 4 legal domains and 4 linguistic modalities).
Enforces scenario-grouped anti-leakage splitting into dev (70%) and held-out test (30%).
"""
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
import os
import json
from pathlib import Path
from typing import List, Dict, Any, Tuple

# Define the 50 comprehensive scenarios grounded in Bangladesh statutory law
SCENARIOS: List[Dict[str, Any]] = [
    # =========================================================================
    # DOMAIN 1: LAND & TENANCY (15 Scenarios -> 60 queries)
    # =========================================================================
    {
        "scenario_id": "SCENARIO_LAND_01",
        "domain": "land_tenancy",
        "split": "dev",
        "expected_provisions": ["PRCA1991_S18", "PRCA1991_S13"],
        "single_or_multi": "multi",
        "sufficient_evidence": True,
        "criteria": "Landlord cannot evict tenant arbitrarily if tenant pays standard rent determined under law.",
        "queries": {
            "bn_unicode": "বাড়িওয়ালা কি ইচ্ছামত ভাড়া বাড়িয়ে আমাকে বাড়ি থেকে উচ্ছেদ করতে পারবে?",
            "banglish": "Bariwala ki iccha moto rent barate parbe ebong evict korte parbe?",
            "en": "Can a landlord arbitrarily increase the rent and subsequently evict the tenant?",
            "code_mixed": "Landlord iccha moto rent hike kore tenant ke evict korle ki remedy pabo?"
        }
    },
    {
        "scenario_id": "SCENARIO_LAND_02",
        "domain": "land_tenancy",
        "split": "dev",
        "expected_provisions": ["TPA1882_S54"],
        "single_or_multi": "single",
        "sufficient_evidence": True,
        "criteria": "Sale of tangible immovable property valued at 100 taka or upwards requires registered instrument.",
        "queries": {
            "bn_unicode": "জমি বা স্থাবর সম্পত্তি হস্তান্তরের ক্ষেত্রে কি দলিল রেজিস্ট্রি করা বাধ্যতামূলক?",
            "banglish": "Jomi ba flat sell korle deed registration kora ki mandatory?",
            "en": "Is registration of a deed mandatory to transfer ownership of immovable property?",
            "code_mixed": "Immovable property ba land transfer korar shomoy registration deed kora ki compulsory?"
        }
    },
    {
        "scenario_id": "SCENARIO_LAND_03",
        "domain": "land_tenancy",
        "split": "dev",
        "expected_provisions": ["PRCA1991_S19"],
        "single_or_multi": "single",
        "sufficient_evidence": True,
        "criteria": "Every landlord must issue a written receipt for rent received; failure is penal.",
        "queries": {
            "bn_unicode": "ভাড়াটিয়া ভাড়া প্রদান করিলে বাড়িওয়ালার কি লিখিত রশিদ প্রদান করার বাধ্যবাধকতা আছে?",
            "banglish": "Bari bhara dile bariwala ki written receipt dite baddho?",
            "en": "Is a landlord legally obligated to issue a written money receipt upon receiving house rent?",
            "code_mixed": "Tenant rent pay korle landlord written rent receipt dite baddho ki na?"
        }
    },
    {
        "scenario_id": "SCENARIO_LAND_04",
        "domain": "land_tenancy",
        "split": "dev",
        "expected_provisions": ["TPA1882_S106"],
        "single_or_multi": "single",
        "sufficient_evidence": True,
        "criteria": "In absence of written contract, manufacturing lease terminable by 6 months notice, others by 15 days.",
        "queries": {
            "bn_unicode": "চুক্তিপত্র না থাকিলে স্থাবর সম্পত্তির ইজারা বা ভাড়া অবসানের জন্য কত দিনের নোটিশ দিতে হইবে?",
            "banglish": "Written contract na thakle lease terminate korte koto diner notice dite hoy?",
            "en": "How many days notice is required to terminate an immovable property lease without written contract?",
            "code_mixed": "Lease agreement na thakle property tenancy terminate korte koto diner prior notice lagbe?"
        }
    },
    {
        "scenario_id": "SCENARIO_LAND_05",
        "domain": "land_tenancy",
        "split": "dev",
        "expected_provisions": ["PRCA1991_S21"],
        "single_or_multi": "single",
        "sufficient_evidence": True,
        "criteria": "If landlord refuses rent, tenant may deposit rent with the Rent Controller within prescribed time.",
        "queries": {
            "bn_unicode": "বাড়িওয়ালা ভাড়া নিতে অস্বীকার করিলে ভাড়াটিয়া কোথায় ভাড়া জমা দিতে পারে?",
            "banglish": "Bariwala jodi bhara nite na chay tahole tenant kothay rent deposit korbe?",
            "en": "Where can a tenant deposit rent if the landlord refuses to accept the monthly payment?",
            "code_mixed": "Landlord monthly rent accept na korle Rent Controller er kache deposit kora jabe ki?"
        }
    },
    {
        "scenario_id": "SCENARIO_LAND_06",
        "domain": "land_tenancy",
        "split": "dev",
        "expected_provisions": ["TPA1882_S53A"],
        "single_or_multi": "single",
        "sufficient_evidence": True,
        "criteria": "Doctrine of part performance protects transferee in possession under written contract.",
        "queries": {
            "bn_unicode": "সম্পত্তি বিক্রয়ের চুক্তি অনুসারে দখল পাইলে ক্রেতাকে কি বিক্রেতা বেদখল করিতে পারে?",
            "banglish": "Jomi kenar chukti kore dokhol pele seller ki buyer ke bedokhol korte parbe?",
            "en": "Can a seller evict a buyer who obtained possession under a written contract of sale?",
            "code_mixed": "Sale agreement kore land possession nile seller ki buyer ke unlawful evict korte parbe?"
        }
    },
    {
        "scenario_id": "SCENARIO_LAND_07",
        "domain": "land_tenancy",
        "split": "dev",
        "expected_provisions": ["PRCA1991_S7"],
        "single_or_multi": "single",
        "sufficient_evidence": True,
        "criteria": "Landlord cannot demand premium, salami, or advance exceeding one month rent without controller approval.",
        "queries": {
            "bn_unicode": "বাড়ি ভাড়া বাবদ বাড়িওয়ালা কি এক মাসের অধিক অগ্রিম ভাড়া বা সালামি দাবি করিতে পারে?",
            "banglish": "Bariwala ki ek masher beshi advance rent ba salami daabi korte parbe?",
            "en": "Can a house owner demand advance rent or salami exceeding one month's rent?",
            "code_mixed": "Landlord advance rent hishebe 1 month er beshi security deposit ba salami demand korte pare?"
        }
    },
    {
        "scenario_id": "SCENARIO_LAND_08",
        "domain": "land_tenancy",
        "split": "dev",
        "expected_provisions": ["TPA1882_S108"],
        "single_or_multi": "single",
        "sufficient_evidence": True,
        "criteria": "Rights and liabilities of lessor and lessee regarding quiet enjoyment and repairs.",
        "queries": {
            "bn_unicode": "ইজারাদাতার অনুমতি ব্যতীত ইজারাগ্রহীতা কি সম্পত্তিতে স্থায়ী অবকাঠামো নির্মাণ করিতে পারিবে?",
            "banglish": "Landlord er permission chara tenant ki permanent structure build korte parbe?",
            "en": "Can a lessee build permanent structures on leased land without lessor's consent?",
            "code_mixed": "Lessor consent chara lessee ki leased property te permanent structure banate parbe?"
        }
    },
    {
        "scenario_id": "SCENARIO_LAND_09",
        "domain": "land_tenancy",
        "split": "dev",
        "expected_provisions": ["PRCA1991_S15"],
        "single_or_multi": "single",
        "sufficient_evidence": True,
        "criteria": "Determination of standard rent by Rent Controller based on municipal tax and market rate.",
        "queries": {
            "bn_unicode": "ভাড়াটিয়া ও বাড়িওয়ালার মধ্যে ভাড়ার পরিমাণ লইয়া বিরোধ দেখা দিলে মানসম্মত ভাড়া কে নির্ধারণ করিবে?",
            "banglish": "Rent niye dispute hole standard rent kothay determine kora hoy?",
            "en": "Who has the legal authority to fix standard rent in case of dispute between tenant and landlord?",
            "code_mixed": "House rent dispute hole standard rent determine korar authority kar ache?"
        }
    },
    {
        "scenario_id": "SCENARIO_LAND_10",
        "domain": "land_tenancy",
        "split": "dev",
        "expected_provisions": [],
        "single_or_multi": "none",
        "sufficient_evidence": False,
        "criteria": "Out of scope: Agricultural tenancy record of rights ceiling governed under uncollected SAT Act provisions.",
        "queries": {
            "bn_unicode": "কৃষি জমির ক্ষেত্রে খতিয়ান সংশোধনের জন্য ভূমি আপিল বোর্ডে আবেদনের তামাদি কত দিন?",
            "banglish": "Krishi jomir khatian shongshodhon korte appeal board e koto diner moddhe apply korte hoy?",
            "en": "What is the limitation period to apply to the Land Appeal Board for correction of agricultural khatian?",
            "code_mixed": "Agricultural land er khatian correction er appeal limitation time koto din?"
        }
    },
    # Land & Tenancy Test Scenarios (Held-out 5 Scenarios -> 20 queries)
    {
        "scenario_id": "SCENARIO_LAND_11",
        "domain": "land_tenancy",
        "split": "test",
        "expected_provisions": ["TPA1882_S54"],
        "single_or_multi": "single",
        "sufficient_evidence": True,
        "criteria": "Definition of sale as transfer of ownership in exchange for price paid or promised.",
        "queries": {
            "bn_unicode": "স্থাবর সম্পত্তি বিক্রয় বলিতে আইনে কী বুঝায় এবং মূল্য পরিশোধের শর্ত কী?",
            "banglish": "Immovable property bikri bolte ki bujhay ebong price payment er shoroto ki?",
            "en": "How is sale of immovable property legally defined regarding price paid or promised?",
            "code_mixed": "Property sale er statutory definition ki and consideration price kibhabe treat kora hoy?"
        }
    },
    {
        "scenario_id": "SCENARIO_LAND_12",
        "domain": "land_tenancy",
        "split": "test",
        "expected_provisions": ["PRCA1991_S18"],
        "single_or_multi": "single",
        "sufficient_evidence": True,
        "criteria": "Bona fide requirement of landlord for building or rebuilding as ground for eviction.",
        "queries": {
            "bn_unicode": "বাড়িওয়ালার নিজস্ব বসবাসের বা বাড়ি পুনর্নির্মাণের প্রয়োজনে কি ভাড়াটিয়া উচ্ছেদের আদেশ দেওয়া যায়?",
            "banglish": "Bariwala jodi nijer thakar jonno ba rebuild korar jonno eviction chay legal ki na?",
            "en": "Can a landlord obtain an eviction decree on the ground of bona fide personal use or rebuilding?",
            "code_mixed": "Landlord er personal requirement ba building reconstruction er ground e eviction pabe ki?"
        }
    },
    {
        "scenario_id": "SCENARIO_LAND_13",
        "domain": "land_tenancy",
        "split": "test",
        "expected_provisions": ["TPA1882_S106"],
        "single_or_multi": "single",
        "sufficient_evidence": True,
        "criteria": "Notice to quit must be in writing, signed by lessor, and delivered personally or by post.",
        "queries": {
            "bn_unicode": "ইজারা অবসানের নোটিশ কীভাবে প্রদান করিতে হয় এবং উহা কি ডাকযোগে পাঠানো আবশ্যক?",
            "banglish": "Lease termination notice kivabe deliver korte hoy ebong registered post lagbe ki na?",
            "en": "What are the statutory requirements for the delivery and service of a lease termination notice?",
            "code_mixed": "Property tenancy termination notice service korar legal rules ki?"
        }
    },
    {
        "scenario_id": "SCENARIO_LAND_14",
        "domain": "land_tenancy",
        "split": "test",
        "expected_provisions": ["PRCA1991_S13"],
        "single_or_multi": "single",
        "sufficient_evidence": True,
        "criteria": "Excess rent paid above standard rent cannot be recovered by landlord and must be refunded.",
        "queries": {
            "bn_unicode": "আইনসম্মত ভাড়ার অতিরিক্ত অর্থ বাড়িওয়ালা গ্রহণ করিলে ভাড়াটিয়া কি তাহা ফেরত পাইবে?",
            "banglish": "Standard rent er theke beshi taka bariwala nile oita ki refund daabi kora jay?",
            "en": "Can a tenant claim a refund or adjustment if the landlord collected rent in excess of standard rent?",
            "code_mixed": "Landlord standard rent er cheye excessive rent collect korle refund claim kora jabe ki?"
        }
    },
    {
        "scenario_id": "SCENARIO_LAND_15",
        "domain": "land_tenancy",
        "split": "test",
        "expected_provisions": [],
        "single_or_multi": "none",
        "sufficient_evidence": False,
        "criteria": "Out of scope: Partition suit jurisdiction under Partition Act 1893 not in statutory corpus.",
        "queries": {
            "bn_unicode": "শরিকি সম্পত্তিতে বাটোয়ারা মোকদ্দমায় কমিশন ফিস কে বহন করিবে?",
            "banglish": "Shoriki jomite batowara mamlay advocate commissioner fee kar dite hoy?",
            "en": "Who is legally responsible to bear commissioner fees in a joint property partition suit?",
            "code_mixed": "Joint property partition suit a advocate commissioner fees dispute kivabe solve hoy?"
        }
    },

    # =========================================================================
    # DOMAIN 2: EMPLOYMENT & LABOUR (13 Scenarios -> 52 queries)
    # =========================================================================
    {
        "scenario_id": "SCENARIO_LABOUR_01",
        "domain": "employment_labour",
        "split": "dev",
        "expected_provisions": ["BLA2006_S২৬"],
        "single_or_multi": "single",
        "sufficient_evidence": True,
        "criteria": "Termination of permanent worker requires 120 days notice or pay in lieu plus compensation.",
        "queries": {
            "bn_unicode": "চাকরির বয়স শেষ না হতেই মালিক নোটিশ ছাড়া স্থায়ী শ্রমিক বরখাস্ত করিলে কত দিনের মজুরি পাইবেন?",
            "banglish": "Chakri theke notice chara terminate korle koto diner salary pabo labour law onujayi?",
            "en": "How many days notice or compensation must an employer provide to terminate a permanent worker?",
            "code_mixed": "Employer permanent worker ke notice period chara discharge korle severance salary koto pabe?"
        }
    },
    {
        "scenario_id": "SCENARIO_LABOUR_02",
        "domain": "employment_labour",
        "split": "dev",
        "expected_provisions": ["BLAA2013_S৭"],
        "single_or_multi": "single",
        "sufficient_evidence": True,
        "criteria": "No worker shall be dismissed without being found guilty of misconduct upon inquiry.",
        "queries": {
            "bn_unicode": "অসদাচরণের অভিযোগের তদন্ত না করিয়া কি কোনো শ্রমিককে সরাসরি বরখাস্ত করা যাইবে?",
            "banglish": "Misconduct er inquiry chara kono factory worker ke direct dismiss kora jay ki?",
            "en": "Can a worker be dismissed without holding an inquiry and proving them guilty of misconduct?",
            "code_mixed": "Misconduct charge a probe committee inquiry na kore worker ke terminate kora legal ki?"
        }
    },
    {
        "scenario_id": "SCENARIO_LABOUR_03",
        "domain": "employment_labour",
        "split": "dev",
        "expected_provisions": ["BLA2006_S২৭"],
        "single_or_multi": "single",
        "sufficient_evidence": True,
        "criteria": "Retirement age for workers is 60 years with full terminal gratuity benefits.",
        "queries": {
            "bn_unicode": "বাংলাদেশ শ্রম আইন অনুযায়ী শ্রমিকের অবসর গ্রহণের বয়স কত এবং গ্র্যাচুইটি কীভাবে পাইবেন?",
            "banglish": "Labour law te worker er retirement age koto ebong gratuity pabe kivabe?",
            "en": "What is the statutory retirement age for industrial workers and their entitlement to gratuity?",
            "code_mixed": "Industrial worker der retirement age koto years and retirement benefits ki ki thake?"
        }
    },
    {
        "scenario_id": "SCENARIO_LABOUR_04",
        "domain": "employment_labour",
        "split": "dev",
        "expected_provisions": ["BLA2006_S২৩"],
        "single_or_multi": "single",
        "sufficient_evidence": True,
        "criteria": "Worker convicted of criminal offense or guilty of misconduct may be dismissed without notice.",
        "queries": {
            "bn_unicode": "শ্রমিক ফৌজদারি অপরাধে সাজাপ্রাপ্ত হইলে মালিক কি নোটিশ ব্যতিরেকে বরখাস্ত করিতে পারেন?",
            "banglish": "Worker criminal court e convict hole malik ki notice chara dismiss korte pare?",
            "en": "Can an employer dismiss a worker without notice if the worker is convicted of a criminal offense?",
            "code_mixed": "Factory employee criminal case e convicted hole employer instant dismissal korte pare?"
        }
    },
    {
        "scenario_id": "SCENARIO_LABOUR_05",
        "domain": "employment_labour",
        "split": "dev",
        "expected_provisions": ["BLAA2013_S২"],
        "single_or_multi": "single",
        "sufficient_evidence": True,
        "criteria": "Definition of worker amended to include contractual and subcontracted workers.",
        "queries": {
            "bn_unicode": "২০১৩ সালের সংশোধনী অনুযায়ী ঠিকাদারের অধীনে কর্মরত শ্রমিক কি মূল আইনের সুবিধা পাইবেন?",
            "banglish": "2013 amendment onujayi sub-contractor er worker ki Labour Act er rights pabe?",
            "en": "Are subcontracted workers covered under the amended definition of worker in the 2013 Labour Act?",
            "code_mixed": "Contractor er under e temporary workers ki 2013 amendment e statutory definition e pore?"
        }
    },
    {
        "scenario_id": "SCENARIO_LABOUR_06",
        "domain": "employment_labour",
        "split": "dev",
        "expected_provisions": ["BLA2006_S২৬", "BLAA2013_S৭"],
        "single_or_multi": "multi",
        "sufficient_evidence": True,
        "criteria": "Distinction between termination simpliciter (Sec 26) and punitive dismissal for misconduct (Sec 23/Sec 7).",
        "queries": {
            "bn_unicode": "সাধারণ চাকরি অবসান ও অসদাচরণের কারণে বরখাস্তের মধ্যে আর্থিক সুবিধার কী পার্থক্য আছে?",
            "banglish": "Simple termination ar misconduct dismissal er moddhe compensation difference ki?",
            "en": "What is the difference in terminal benefits between simple termination and dismissal for misconduct?",
            "code_mixed": "Termination simpliciter vs misconduct dismissal er moddhe settlement benefits difference ki?"
        }
    },
    {
        "scenario_id": "SCENARIO_LABOUR_07",
        "domain": "employment_labour",
        "split": "dev",
        "expected_provisions": ["BLA2006_S২৭"],
        "single_or_multi": "single",
        "sufficient_evidence": True,
        "criteria": "Worker resigning voluntarily after 5 years service entitled to 14 days wages per completed year.",
        "queries": {
            "bn_unicode": "পাঁচ বছর চাকরির পর শ্রমিক স্বেচ্ছায় পদত্যাগ করিলে কি কোনো ক্ষতিপূরণ পাইবেন?",
            "banglish": "5 bochor chakri korar por voluntary resign dile ki compensation pawa jay?",
            "en": "Is a worker entitled to severance compensation upon voluntary resignation after five years of service?",
            "code_mixed": "5 years continuous service er por employee resign korle separation compensation pabe?"
        }
    },
    {
        "scenario_id": "SCENARIO_LABOUR_08",
        "domain": "employment_labour",
        "split": "dev",
        "expected_provisions": ["BLA2006_S২৬"],
        "single_or_multi": "single",
        "sufficient_evidence": True,
        "criteria": "Temporary worker termination requires 30 days notice for monthly rated or 14 days for others.",
        "queries": {
            "bn_unicode": "অস্থায়ী মাসিক মজুরিপ্রাপ্ত শ্রমিককে চাকরি হইতে অব্যাহতি দিতে কত দিনের নোটিশ প্রয়োজন?",
            "banglish": "Temporary worker ke chakri theke badhite koto diner notice dite hobe?",
            "en": "How many days notice is required to terminate the employment of a temporary monthly-rated worker?",
            "code_mixed": "Temporary monthly-rated worker ke terminate korar jonno notice requirement koto din?"
        }
    },
    {
        "scenario_id": "SCENARIO_LABOUR_09",
        "domain": "employment_labour",
        "split": "dev",
        "expected_provisions": [],
        "single_or_multi": "none",
        "sufficient_evidence": False,
        "criteria": "Out of scope: Domestic worker protection guidelines under Cabinet policy 2015 not in Labour Act.",
        "queries": {
            "bn_unicode": "গৃহশ্রমিককে নির্যাতন করিলে শ্রম ট্রাইব্যুনালে সরাসরি ক্ষতিপূরণ মামলা করা যাইবে কি?",
            "banglish": "Griho shromik er grievance niye Labour Court e direct case kora jabe ki?",
            "en": "Can a domestic worker directly file a claim before the Labour Court for workplace abuse?",
            "code_mixed": "Domestic helper abuse hole Labour Court jurisdiction e case file kora possible?"
        }
    },
    # Labour Test Scenarios (Held-out 4 Scenarios -> 16 queries)
    {
        "scenario_id": "SCENARIO_LABOUR_10",
        "domain": "employment_labour",
        "split": "test",
        "expected_provisions": ["BLAA2013_S৭"],
        "single_or_multi": "single",
        "sufficient_evidence": True,
        "criteria": "Misconduct inquiry must provide 7 days notice to worker to explain charges.",
        "queries": {
            "bn_unicode": "অসদাচরণের দায়ে অভিযুক্ত শ্রমিককে আত্মপক্ষ সমর্থনের জন্য কত দিনের সময় দিতে হইবে?",
            "banglish": "Misconduct accusation e worker ke defense er jonno koto diner time dite hoy?",
            "en": "How many days must an employer give a worker to show cause against misconduct allegations?",
            "code_mixed": "Misconduct show-cause notice a worker ke reply deyar jonno statutory time koto din?"
        }
    },
    {
        "scenario_id": "SCENARIO_LABOUR_11",
        "domain": "employment_labour",
        "split": "test",
        "expected_provisions": ["BLA2006_S২৬"],
        "single_or_multi": "single",
        "sufficient_evidence": True,
        "criteria": "Compensation for termination under Section 26 is 30 days wages for every completed year of service.",
        "queries": {
            "bn_unicode": "২৬ ধারায় চাকরি অবসানের ক্ষেত্রে প্রতি সমাপ্ত কর্মবছরের জন্য কত দিনের মজুরি ক্ষতিপূরণ দিতে হইবে?",
            "banglish": "Dhara 26 e termination hole proti completed bochorer jonno koto diner salary pabe?",
            "en": "Under Section 26, how many days wages per completed year of service must be paid as compensation?",
            "code_mixed": "Section 26 termination e per year of service koto diner wage compensation calculate hoy?"
        }
    },
    {
        "scenario_id": "SCENARIO_LABOUR_12",
        "domain": "employment_labour",
        "split": "test",
        "expected_provisions": ["BLA2006_S২৩"],
        "single_or_multi": "single",
        "sufficient_evidence": True,
        "criteria": "Acts constituting misconduct include theft, fraud, bribery, riotous behavior, strike.",
        "queries": {
            "bn_unicode": "শ্রম আইনে কোন কোন আচরণকে অসদাচরণ বা শৃঙ্খলাভঙ্গ বলিয়া গণ্য করা হইয়াছে?",
            "banglish": "Labour Act onujayi kon kon kaj misconduct hishebe consider kora hoy?",
            "en": "Which acts and omissions are legally defined as misconduct under the Bangladesh Labour Act?",
            "code_mixed": "Statutory legal grounds ki ki ache ja Labour Law te misconduct hishebe classify hoy?"
        }
    },
    {
        "scenario_id": "SCENARIO_LABOUR_13",
        "domain": "employment_labour",
        "split": "test",
        "expected_provisions": [],
        "single_or_multi": "none",
        "sufficient_evidence": False,
        "criteria": "Out of scope: Merchant shipping master maritime wages under Merchant Shipping Ordinance.",
        "queries": {
            "bn_unicode": "সমুদ্রগামী জাহাজের নাবিকের বকেয়া বেতনের জন্য আন্তর্জাতিক মেরিটাইম ট্রাইব্যুনালে কীভাবে নালিশ করিবেন?",
            "banglish": "Jahajer sailor er bakya salary niye Maritime Tribunal e kivabe case korte hoy?",
            "en": "How can an ocean-going vessel seaman recover unpaid maritime wages under Bangladesh law?",
            "code_mixed": "Merchant seaman salary dispute hole maritime law te recovery suit kivabe kore?"
        }
    },

    # =========================================================================
    # DOMAIN 3: CONSUMER PROTECTION (11 Scenarios -> 44 queries)
    # =========================================================================
    {
        "scenario_id": "SCENARIO_CONSUMER_01",
        "domain": "consumer_protection",
        "split": "dev",
        "expected_provisions": ["CRPA2009_S৩৭"],
        "single_or_multi": "single",
        "sufficient_evidence": True,
        "criteria": "Not mentioning retail price, weight, or expiration date punishable by up to 1 yr imprisonment or 50k fine.",
        "queries": {
            "bn_unicode": "দোকানদার পণ্যের গায়ে মেয়াদোত্তীর্ণের তারিখ না লিখে বিক্রি করলে কি শাস্তি হবে?",
            "banglish": "Dokandar expiry date na likhe ponno sell korle ki shasti hobe consumer rights law te?",
            "en": "What is the penalty if a seller sells goods without mentioning expiration date on packaging?",
            "code_mixed": "Shopkeeper expired product ba date chara ponno sell korle consumer rights e ki penalty pabe?"
        }
    },
    {
        "scenario_id": "SCENARIO_CONSUMER_02",
        "domain": "consumer_protection",
        "split": "dev",
        "expected_provisions": ["CRPA2009_S৩৮"],
        "single_or_multi": "single",
        "sufficient_evidence": True,
        "criteria": "Failure to display price list of goods punishable by up to 1 year imprisonment or 50,000 taka fine.",
        "queries": {
            "bn_unicode": "দোকানে পণ্যের মূল্য তালিকা প্রদর্শন না করিলে দোকানদারের কী শাস্তি হইতে পারে?",
            "banglish": "Dokane price list na jhulale dokandarer ki shasti hote pare consumer act a?",
            "en": "What is the legal punishment for a shopkeeper who fails to display the price list of goods?",
            "code_mixed": "Shop e product price list display na korle Directorate of Consumer Rights ki fine korte pare?"
        }
    },
    {
        "scenario_id": "SCENARIO_CONSUMER_03",
        "domain": "consumer_protection",
        "split": "dev",
        "expected_provisions": ["CRPA2009_S৩৯"],
        "single_or_multi": "single",
        "sufficient_evidence": True,
        "criteria": "Selling at price higher than scheduled price punishable by up to 1 year prison or 50,000 taka fine.",
        "queries": {
            "bn_unicode": "নির্ধারিত মূল্যের চেয়ে বেশি দামে পণ্য বিক্রি করিলে বিক্রেতার কী শাস্তি হইবে?",
            "banglish": "MRP theke beshi dame jinish bikri korle dokandarer ki shasti hobe?",
            "en": "What is the penalty for selling products at a price higher than the fixed retail price?",
            "code_mixed": "Maximum retail price er cheye over-price charge korle consumer protection law te ki punishment?"
        }
    },
    {
        "scenario_id": "SCENARIO_CONSUMER_04",
        "domain": "consumer_protection",
        "split": "dev",
        "expected_provisions": ["CRPA2009_S৪১"],
        "single_or_multi": "single",
        "sufficient_evidence": True,
        "criteria": "Selling adulterated products punishable by up to 3 years imprisonment or 2 lakh taka fine.",
        "queries": {
            "bn_unicode": "পণ্যে ভেজাল মিশ্রণ করিলে বা ভেজাল খাদ্যদ্রব্য বিক্রি করিলে কত বছরের জেল হইতে পারে?",
            "banglish": "Khabare vejal mishale ba adulterated food sell korle koto bochorer jail hoy?",
            "en": "How many years imprisonment can be awarded for mixing adulterants or selling adulterated food?",
            "code_mixed": "Food product e adulteration korle ba expired items sell korle jail time koto years?"
        }
    },
    {
        "scenario_id": "SCENARIO_CONSUMER_05",
        "domain": "consumer_protection",
        "split": "dev",
        "expected_provisions": ["CRPA2009_S৪৫"],
        "single_or_multi": "single",
        "sufficient_evidence": True,
        "criteria": "False or misleading advertisement punishable by up to 1 year imprisonment or 2 lakh taka fine.",
        "queries": {
            "bn_unicode": "পণ্যের আকর্ষণীয় কিন্তু মিথ্যা বিজ্ঞাপন দিলে আইনের দৃষ্টিতে উহা কী ধরনের অপরাধ?",
            "banglish": "Mithya ba misleading ad diye customer ke thokaile ki crime hoy?",
            "en": "Is publishing false or misleading advertisements to deceive consumers a punishable offense?",
            "code_mixed": "Product er deceptive advertising ba false promotion korle legal offense ki hobe?"
        }
    },
    {
        "scenario_id": "SCENARIO_CONSUMER_06",
        "domain": "consumer_protection",
        "split": "dev",
        "expected_provisions": ["CRPA2009_S৩৭", "CRPA2009_S৩৯"],
        "single_or_multi": "multi",
        "sufficient_evidence": True,
        "criteria": "Dual violations regarding packaging omission and selling above fixed price.",
        "queries": {
            "bn_unicode": "মোড়কে মূল্য না লিখিয়া নির্ধারিত মূল্যের অতিরিক্ত দামে পণ্য বিক্রি করিলে সম্মিলিত শাস্তি কী হইবে?",
            "banglish": "Packet e price na likhe overprice e sell korle double offense e ki shasti hoy?",
            "en": "What is the combined penalty for not marking retail price on packaging and charging above fixed rate?",
            "code_mixed": "Packaging date omit kore overpricing korle simultaneous sections a ki fine pabe?"
        }
    },
    {
        "scenario_id": "SCENARIO_CONSUMER_07",
        "domain": "consumer_protection",
        "split": "dev",
        "expected_provisions": ["CRPA2009_S৪৬"],
        "single_or_multi": "single",
        "sufficient_evidence": True,
        "criteria": "Deceptive weight or measure using faulty scale punishable by up to 1 year prison or 50k fine.",
        "queries": {
            "bn_unicode": "দোকানে বাটখারা বা ওজনে কারচুপি করিয়া পণ্য কম দিলে ক্রেতা কীভাবে প্রতিকার পাইবেন?",
            "banglish": "Ojon e kom dile ba faulty scale use korle dokandarer ki shasti hobe?",
            "en": "What is the legal punishment for using inaccurate weights or measures to short-change customers?",
            "code_mixed": "Weight scale tampering kore product kom dile consumer protection act e ki case hobe?"
        }
    },
    {
        "scenario_id": "SCENARIO_CONSUMER_08",
        "domain": "consumer_protection",
        "split": "dev",
        "expected_provisions": [],
        "single_or_multi": "none",
        "sufficient_evidence": False,
        "criteria": "Out of scope: Drug price regulation under Drug Control Ordinance 1982 not in Consumer Act.",
        "queries": {
            "bn_unicode": "ফার্মেসি কর্তৃক বিদেশি ঔষধের সর্বোচ্চ খুচরা মূল্য কীভাবে ওষুধ প্রশাসন অধিদপ্তর দ্বারা নির্ধারিত হয়?",
            "banglish": "Pharmacy te imported medicine er MRP kivabe DGDA control kore?",
            "en": "Under what statutory rules does the Drug Administration fix prices of imported medicines?",
            "code_mixed": "Foreign pharmaceutical medicine er price control dispute DGDA te kivabe regulate hoy?"
        }
    },
    # Consumer Protection Test Scenarios (Held-out 3 Scenarios -> 12 queries)
    {
        "scenario_id": "SCENARIO_CONSUMER_09",
        "domain": "consumer_protection",
        "split": "test",
        "expected_provisions": ["CRPA2009_S৩৭"],
        "single_or_multi": "single",
        "sufficient_evidence": True,
        "criteria": "Requirement of mentioning manufacture date and ingredients on packaged goods.",
        "queries": {
            "bn_unicode": "মোড়কজাত পণ্যে উৎপাদনের তারিখ ও উপাদান না থাকিলে বিক্রেতা কি দায় এড়াইতে পারিবে?",
            "banglish": "Packaging e manufacturing date ar ingredients na thakle seller ki bachite parbe?",
            "en": "Can a seller escape liability if packaged commodities omit manufacturing date and ingredients?",
            "code_mixed": "Packaged food product e production date and ingredients na thakle statutory liability ki?"
        }
    },
    {
        "scenario_id": "SCENARIO_CONSUMER_10",
        "domain": "consumer_protection",
        "split": "test",
        "expected_provisions": ["CRPA2009_S৩৮"],
        "single_or_multi": "single",
        "sufficient_evidence": True,
        "criteria": "Service providers must display price list of services at prominent place.",
        "queries": {
            "bn_unicode": "হোটেল বা রেস্তোরাঁয় খাবারের মূল্য তালিকা প্রকাশ্য স্থানে টাঙানো কি আইনত আবশ্যক?",
            "banglish": "Hotel ba restaurant e food price list public place e jhulano ki mandatory?",
            "en": "Is a restaurant or hotel legally required to visibly display the price list of food items?",
            "code_mixed": "Restaurant menu card ba service charge price list openly display kora statutory requirement ki?"
        }
    },
    {
        "scenario_id": "SCENARIO_CONSUMER_11",
        "domain": "consumer_protection",
        "split": "test",
        "expected_provisions": [],
        "single_or_multi": "none",
        "sufficient_evidence": False,
        "criteria": "Out of scope: E-commerce escrow refund timeline governed under Ministry of Commerce SOP 2021.",
        "queries": {
            "bn_unicode": "ই-কমার্স প্ল্যাটফর্ম ১০ দিনের মধ্যে অর্থ ফেরত না দিলে কোন ব্যাংকিং আইনে জরিমানা করা হইবে?",
            "banglish": "E-commerce platform 10 diner moddhe refund na dile kon banking law te fine hoy?",
            "en": "Under which banking regulation is an e-commerce platform fined for delaying customer refunds?",
            "code_mixed": "E-commerce escrow refund delay hole Bangladesh Bank circular er limitation ki?"
        }
    },

    # =========================================================================
    # DOMAIN 4: CONTRACTUAL OBLIGATIONS (11 Scenarios -> 44 queries)
    # =========================================================================
    {
        "scenario_id": "SCENARIO_CONTRACT_01",
        "domain": "contractual_obligations",
        "split": "dev",
        "expected_provisions": ["CA1872_S10"],
        "single_or_multi": "single",
        "sufficient_evidence": True,
        "criteria": "All agreements are contracts if made by free consent of competent parties for lawful consideration.",
        "queries": {
            "bn_unicode": "কোন কোন শর্ত পূরণ করিলে একটি সাধারণ সম্মতি বা চুক্তিপত্র আদালতে কার্যকর চুক্তি বলিয়া গণ্য হইবে?",
            "banglish": "Ki ki condition fulfill korle ekta agreement legally valid contract hishebe gonno hoy?",
            "en": "What legal conditions are required for an agreement to be enforceable as a valid contract?",
            "code_mixed": "Agreement legal contract hishebe valid hote free consent and lawful object er requirement ki?"
        }
    },
    {
        "scenario_id": "SCENARIO_CONTRACT_02",
        "domain": "contractual_obligations",
        "split": "dev",
        "expected_provisions": ["CA1872_S11"],
        "single_or_multi": "single",
        "sufficient_evidence": True,
        "criteria": "Person must be of age of majority, sound mind, and not disqualified by law to contract.",
        "queries": {
            "bn_unicode": "নাবালক বা অপ্রাপ্তবয়স্ক ব্যক্তি কি কোনো আইনগত বাধ্যবাধকতাপূর্ণ বাণিজ্যিক চুক্তি সম্পাদন করিতে পারিবে?",
            "banglish": "Minor ba 18 bochorer kom boyosher keu business contract sign korle oita ki valid?",
            "en": "Can a minor or person under majority age enter into a legally binding business agreement?",
            "code_mixed": "Minor person business agreement sign korle contract competence er under e void hobe ki?"
        }
    },
    {
        "scenario_id": "SCENARIO_CONTRACT_03",
        "domain": "contractual_obligations",
        "split": "dev",
        "expected_provisions": ["CA1872_S25"],
        "single_or_multi": "single",
        "sufficient_evidence": True,
        "criteria": "Agreement made without consideration is void unless in writing, registered, and made on natural affection.",
        "queries": {
            "bn_unicode": "বিনিময় বা প্রতিদান ছাড়া সম্পাদিত চুক্তি কি আইনের দৃষ্টিতে বাতিল বলিয়া গণ্য হইবে?",
            "banglish": "Kono consideration chara agreement sign korle oita ki void contract hobe?",
            "en": "Is an agreement made without legal consideration considered void under the Contract Act?",
            "code_mixed": "Consideration chara verbal promise ba agreement korle legally enforceable ki na?"
        }
    },
    {
        "scenario_id": "SCENARIO_CONTRACT_04",
        "domain": "contractual_obligations",
        "split": "dev",
        "expected_provisions": ["CA1872_S10", "CA1872_S11"],
        "single_or_multi": "multi",
        "sufficient_evidence": True,
        "criteria": "Dual requirement: Section 10 establishes contract essentials; Section 11 establishes age of majority.",
        "queries": {
            "bn_unicode": "১৮ বছরের কম বয়সী ব্যক্তির সহিত কোনো লিখিত চুক্তিপত্র সম্পাদিত হইলে উহা কেন বাতিল বলিয়া গণ্য হয়?",
            "banglish": "18 years er kom boyosher karo sathe written contract keno void declare hoy?",
            "en": "Why is an agreement executed with a person below 18 years of age declared void ab initio?",
            "code_mixed": "Underage person er sathe commercial contract sign korle statutory grounds e keno void hoy?"
        }
    },
    {
        "scenario_id": "SCENARIO_CONTRACT_05",
        "domain": "contractual_obligations",
        "split": "dev",
        "expected_provisions": ["CA1872_S2"],
        "single_or_multi": "single",
        "sufficient_evidence": True,
        "criteria": "Interpretation clause defining proposal, acceptance, promise, promisor, promisee, consideration.",
        "queries": {
            "bn_unicode": "চুক্তি আইনে প্রস্তাব গ্রহণ এবং প্রতিদানের সংজ্ঞা কীভাবে দেওয়া হইয়াছে?",
            "banglish": "Contract Act e proposal acceptance ebong consideration er definition ki?",
            "en": "How are proposal, acceptance, and consideration legally defined under the Contract Act?",
            "code_mixed": "Contract Act interpretation clause e offer acceptance and consideration er legal meaning ki?"
        }
    },
    {
        "scenario_id": "SCENARIO_CONTRACT_06",
        "domain": "contractual_obligations",
        "split": "dev",
        "expected_provisions": ["CA1872_S73"],
        "single_or_multi": "single",
        "sufficient_evidence": True,
        "criteria": "Compensation for loss or damage caused by breach of contract naturally arising from breach.",
        "queries": {
            "bn_unicode": "এক পক্ষ চুক্তি ভঙ্গ করিলে ক্ষতিগ্রস্ত পক্ষ কীভাবে ক্ষতিপূরণ দাবি করিতে পারিবে?",
            "banglish": "Kew chukti bhongo korle opor pokkho kivabe damages claim korte pare?",
            "en": "How can an aggrieved party claim damages for loss suffered due to breach of contract?",
            "code_mixed": "Breach of contract hole compensation and direct financial loss recovery kivabe claim kora jay?"
        }
    },
    {
        "scenario_id": "SCENARIO_CONTRACT_07",
        "domain": "contractual_obligations",
        "split": "dev",
        "expected_provisions": ["CA1872_S56"],
        "single_or_multi": "single",
        "sufficient_evidence": True,
        "criteria": "Agreement to do impossible act is void; contract becoming impossible becomes void (frustration).",
        "queries": {
            "bn_unicode": "চুক্তি সম্পাদনের পর পরিস্থিতিগত কারণে কাজ অসম্ভব হইয়া পড়িলে চুক্তি কি বাতিল হইয়া যায়?",
            "banglish": "Chukti korar por unexpected event er karone kaj impossible hole contract ki void hoy?",
            "en": "Does a contract become void if performance becomes impossible after execution due to frustration?",
            "code_mixed": "Subsequent impossibility ba frustration of contract hole legal liabilities ki thake?"
        }
    },
    {
        "scenario_id": "SCENARIO_CONTRACT_08",
        "domain": "contractual_obligations",
        "split": "dev",
        "expected_provisions": [],
        "single_or_multi": "none",
        "sufficient_evidence": False,
        "criteria": "Out of scope: Cheque dishonor under Section 138 of Negotiable Instruments Act 1881.",
        "queries": {
            "bn_unicode": "ব্যবসায়িক লেনদেনে ব্যাংকের চেক ডিজঅনার হইলে কত দিনের মধ্যে আইনি নোটিশ পাঠাইতে হইবে?",
            "banglish": "Bank cheque dishonor hole koto diner moddhe legal notice pathate hoy?",
            "en": "Within how many days must a statutory legal notice be served following bank cheque dishonour?",
            "code_mixed": "Cheque bounce hole 138 notice deyar limitation period koto din?"
        }
    },
    # Contractual Obligations Test Scenarios (Held-out 3 Scenarios -> 12 queries)
    {
        "scenario_id": "SCENARIO_CONTRACT_09",
        "domain": "contractual_obligations",
        "split": "test",
        "expected_provisions": ["CA1872_S10"],
        "single_or_multi": "single",
        "sufficient_evidence": True,
        "criteria": "Lawful object and consideration required; agreements expressly declared void excluded.",
        "queries": {
            "bn_unicode": "চুক্তির উদ্দেশ্য যদি বেআইনি বা অনৈতিক হয় তাহা হইলে কি চুক্তিটি কার্যকর থাকিবে?",
            "banglish": "Chuktir uddesho jodi illegal ba immoral hoy tahole oita ki valid contract hobe?",
            "en": "Is a contract enforceable if its underlying object or consideration is unlawful or immoral?",
            "code_mixed": "Contract er consideration ba object unlawful hole agreement enforce kora jay ki?"
        }
    },
    {
        "scenario_id": "SCENARIO_CONTRACT_10",
        "domain": "contractual_obligations",
        "split": "test",
        "expected_provisions": ["CA1872_S25"],
        "single_or_multi": "single",
        "sufficient_evidence": True,
        "criteria": "Promise to compensate for something done voluntarily or promise to pay time-barred debt.",
        "queries": {
            "bn_unicode": "তামাদি হইয়া যাওয়া ঋণ পরিশোধের লিখিত প্রতিশ্রুতি কি আইনত বলবৎযোগ্য?",
            "banglish": "Time-barred debt pay korar written promise dile ki legal contract hoy?",
            "en": "Is a written and signed promise to pay a time-barred debt enforceable without fresh consideration?",
            "code_mixed": "Time-barred loan pay korar written commitment dile Contract Act e validity ki?"
        }
    },
    {
        "scenario_id": "SCENARIO_CONTRACT_11",
        "domain": "contractual_obligations",
        "split": "test",
        "expected_provisions": [],
        "single_or_multi": "none",
        "sufficient_evidence": False,
        "criteria": "Out of scope: Specific relief injunction balance of convenience under CPC Order 39.",
        "queries": {
            "bn_unicode": "দেওয়ানি মামলায় অস্থায়ী নিষেধাজ্ঞার আবেদন মঞ্জুর করিতে আদালতের কী কী মূল নীতি অনুসরণ করিতে হয়?",
            "banglish": "Temporary injunction er order pete court er balance of convenience kivabe prove kore?",
            "en": "What judicial principles determine balance of convenience in granting temporary injunctions?",
            "code_mixed": "Civil suit e temporary injunction pray korle court kon principles check kore?"
        }
    }
]


def build_benchmark_records() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Generates 200 benchmark query records partitioned into dev and test sets."""
    dev_records = []
    test_records = []

    dev_scenarios = set()
    test_scenarios = set()

    query_counter = 1

    for sc in SCENARIOS:
        sc_id = sc["scenario_id"]
        split = sc["split"]
        domain = sc["domain"]
        expected = sc["expected_provisions"]
        single_multi = sc["single_or_multi"]
        sufficient = sc["sufficient_evidence"]
        criteria = sc["criteria"]

        if split == "dev":
            dev_scenarios.add(sc_id)
        else:
            test_scenarios.add(sc_id)

        for lang_script, q_text in sc["queries"].items():
            qid = f"BNCH_{domain.upper()[:4]}_{query_counter:03d}_{lang_script.upper()}"
            record = {
                "query_id": qid,
                "scenario_id": sc_id,
                "split": split,
                "original_user_query": q_text,
                "language_and_script": lang_script,
                "legal_domain": domain,
                "expected_supporting_provisions": expected,
                "single_or_multi_provision": single_multi,
                "corpus_has_sufficient_evidence": sufficient,
                "expected_answer_criteria": criteria,
                "annotation_confidence": "High",
                "annotation_status": "researcher_annotated_provisional",
                "reviewer_notes": f"Scenario {sc_id} {split} evaluation case. Parallel cross-script query."
            }
            if split == "dev":
                dev_records.append(record)
            else:
                test_records.append(record)

            query_counter += 1

    # Assert strict scenario anti-leakage
    overlap = dev_scenarios.intersection(test_scenarios)
    assert len(overlap) == 0, f"Critical Leakage! Overlapping scenarios: {overlap}"

    return dev_records, test_records


def main():
    benchmarks_dir = Path("data/benchmarks")
    benchmarks_dir.mkdir(parents=True, exist_ok=True)

    dev_records, test_records = build_benchmark_records()

    dev_path = benchmarks_dir / "benchmark_dev.jsonl"
    test_path = benchmarks_dir / "benchmark_test.jsonl"

    with open(dev_path, "w", encoding="utf-8") as f:
        for r in dev_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    with open(test_path, "w", encoding="utf-8") as f:
        for r in test_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"[+] Benchmark Generation Successful:")
    print(f"    - Dev queries:   {len(dev_records)} (Written to {dev_path})")
    print(f"    - Test queries:  {len(test_records)} (Written to {test_path})")
    print(f"    - Total queries: {len(dev_records) + len(test_records)}")
    print(f"    - Unique Scenarios: {len(SCENARIOS)} (Anti-leakage disjoint sets verified)")


if __name__ == "__main__":
    main()
