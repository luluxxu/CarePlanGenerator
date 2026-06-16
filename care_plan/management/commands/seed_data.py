"""
生成 mock 数据并落库，方便用 TablePlus 等工具直接查看 4 张表的关系。

用法：
    python manage.py seed_data            # 追加（按 MRN/NPI 复用已有 Patient/Provider）
    python manage.py seed_data --flush    # 先清空 4 张表再灌入
    python manage.py seed_data --orders 30 # 控制订单数量（默认用内置清单全部）

不调用 LLM：CarePlan.content 用合理的占位正文填充，status 在
pending/processing/completed/failed 之间分布，方便测试各种状态的展示。
"""

import datetime
import random

from django.core.management.base import BaseCommand
from django.db import transaction

from care_plan.models import Patient, Provider, Order, CarePlan

# --- 固定种子，保证每次生成的数据可复现 -------------------------------------
SEED = 42

PATIENTS = [
    # (first, last, mrn, dob)
    ("James", "Carter", "MRN0001", "1958-03-12"),
    ("Maria", "Gonzalez", "MRN0002", "1971-07-29"),
    ("Robert", "Nguyen", "MRN0003", "1949-11-04"),
    ("Linda", "Patel", "MRN0004", "1985-01-22"),
    ("David", "Johnson", "MRN0005", "1963-09-17"),
    ("Susan", "Kim", "MRN0006", "1990-05-08"),
    ("Michael", "O'Brien", "MRN0007", "1955-12-30"),
    ("Aisha", "Mohammed", "MRN0008", "1978-04-15"),
]

PROVIDERS = [
    # (first, last, npi)
    ("Emily", "Stone", "1003001",),
    ("Daniel", "Reyes", "1003002",),
    ("Hannah", "Wright", "1003003",),
    ("Marcus", "Lee", "1003004",),
    ("Priya", "Shah", "1003005",),
]

# (medication, diagnosis ICD-10, records 自由文本)
ORDER_TEMPLATES = [
    ("Metformin 500mg BID", "E11.9 Type 2 diabetes mellitus",
     "A1c 8.4%. Newly diagnosed. No prior oral hypoglycemics. Mild CKD (eGFR 62)."),
    ("Lisinopril 10mg daily", "I10 Essential hypertension",
     "BP 152/94 on two readings. No history of angioedema. K+ 4.1."),
    ("Atorvastatin 40mg daily", "E78.5 Hyperlipidemia",
     "LDL 168. ASCVD 10-yr risk 14%. No statin intolerance reported."),
    ("Apixaban 5mg BID", "I48.91 Atrial fibrillation",
     "CHA2DS2-VASc 4. CrCl 70. No prior major bleed. Currently on no anticoagulant."),
    ("Albuterol HFA PRN", "J45.40 Moderate persistent asthma",
     "Two exacerbations in past year. Uses rescue inhaler >2x/week. No ICS yet."),
    ("Levothyroxine 75mcg daily", "E03.9 Hypothyroidism",
     "TSH 9.8, free T4 low-normal. Symptoms of fatigue and weight gain."),
    ("Sertraline 50mg daily", "F33.1 Major depressive disorder, recurrent",
     "PHQ-9 score 16. No prior SSRI trial. No suicidal ideation."),
    ("Furosemide 40mg daily", "I50.9 Heart failure",
     "EF 35%. NYHA class II. Recent 3kg weight gain and ankle edema."),
    ("Insulin glargine 20u qHS", "E11.65 Type 2 diabetes with hyperglycemia",
     "A1c 10.2% despite metformin + sulfonylurea. Fasting glucose 230-280."),
    ("Omeprazole 20mg daily", "K21.9 GERD",
     "Heartburn 4x/week for 3 months. No alarm features. Trial of PPI planned."),
    ("Warfarin 5mg daily", "I26.99 Pulmonary embolism",
     "Provoked PE post-surgery. Target INR 2-3. Baseline INR 1.0."),
    ("Gabapentin 300mg TID", "G62.9 Peripheral neuropathy",
     "Diabetic neuropathy, burning pain 6/10. No prior neuropathic agent."),
]

# 每条 CarePlan 的占位正文（4 段，和 PROMPT_TEMPLATE 要求的结构一致）
CARE_PLAN_BODY = """1. Problem List / Drug Therapy Problems
- Primary condition requires initiation of {med}.
- Confirm no contraindications or significant drug-drug interactions.
- Assess adherence barriers and patient understanding.

2. Goals (SMART)
- Achieve target therapeutic response within 12 weeks.
- Maintain relevant labs/vitals within guideline range.
- Zero medication-related adverse events requiring intervention.

3. Pharmacist Interventions / Plan
- Counsel patient on dosing, administration, and expected effects.
- Verify renal/hepatic dosing appropriateness.
- Coordinate follow-up with referring provider.

4. Monitoring Plan & Lab Schedule
- Baseline labs reviewed; repeat at 4 and 12 weeks.
- Monitor for class-specific adverse effects at each visit.
- Reassess therapy at next scheduled appointment.
"""

# status 分布：大部分 completed，少量其它状态用于测试展示
STATUS_WEIGHTS = [
    (CarePlan.Status.COMPLETED, 7),
    (CarePlan.Status.PENDING, 1),
    (CarePlan.Status.PROCESSING, 1),
    (CarePlan.Status.FAILED, 1),
]


def _weighted_status(rng):
    population = [s for s, w in STATUS_WEIGHTS for _ in range(w)]
    return rng.choice(population)


class Command(BaseCommand):
    help = "生成 mock 病人/医生/订单/care plan 数据并落库"

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="灌入前先清空 4 张表（CarePlan/Order/Patient/Provider）",
        )
        parser.add_argument(
            "--orders",
            type=int,
            default=len(ORDER_TEMPLATES),
            help=f"要生成的订单数量（默认 {len(ORDER_TEMPLATES)}）",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        rng = random.Random(SEED)

        if options["flush"]:
            # 顺序：先删依赖方。CarePlan -> Order -> Patient/Provider
            CarePlan.objects.all().delete()
            Order.objects.all().delete()
            Patient.objects.all().delete()
            Provider.objects.all().delete()
            self.stdout.write(self.style.WARNING("已清空 4 张表"))

        # 1. Patients（按 MRN 复用）
        patients = []
        for first, last, mrn, dob in PATIENTS:
            p, _ = Patient.objects.get_or_create(
                mrn=mrn,
                defaults={
                    "first_name": first,
                    "last_name": last,
                    "dob": datetime.date.fromisoformat(dob),
                },
            )
            patients.append(p)

        # 2. Providers（按 NPI 复用）
        providers = []
        for first, last, npi in PROVIDERS:
            pr, _ = Provider.objects.get_or_create(
                npi=npi,
                defaults={"first_name": first, "last_name": last},
            )
            providers.append(pr)

        # 3. Orders + CarePlan（1:1）
        n_orders = max(0, options["orders"])
        created_orders = 0
        for i in range(n_orders):
            med, dx, rec = ORDER_TEMPLATES[i % len(ORDER_TEMPLATES)]
            patient = rng.choice(patients)
            provider = rng.choice(providers)
            order = Order.objects.create(
                patient=patient,
                provider=provider,
                medication=med,
                diagnosis=dx,
                records=rec,
            )
            status = _weighted_status(rng)
            # 只有 completed 才有正文，其它状态正文留空，贴近真实生成流程
            content = CARE_PLAN_BODY.format(med=med) if status == CarePlan.Status.COMPLETED else ""
            CarePlan.objects.create(order=order, status=status, content=content)
            created_orders += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"完成：Patient={Patient.objects.count()} "
                f"Provider={Provider.objects.count()} "
                f"Order={Order.objects.count()} "
                f"CarePlan={CarePlan.objects.count()}（本次新增 {created_orders} 单）"
            )
        )
