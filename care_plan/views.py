"""
全部业务逻辑都堆在 views.py 里 —— 这是故意的。
当你后面开始加 validation / duplicate detection / pharma export 时，
这个文件会迅速膨胀到几百行，你会自然产生"该拆出来"的冲动。
那时再去做分层重构，体感会比一上来就分层要深刻得多。
"""

import os
import uuid
from django.shortcuts import render
from anthropic import Anthropic

# ---------------------------------------------------------------------------
# In-memory "数据库"。进程一重启就全没了。
# 后面切换到 Postgres / SQLite 时，这个字典是替换目标。
# ---------------------------------------------------------------------------
CARE_PLANS: dict[str, dict] = {}

# ---------------------------------------------------------------------------
# LLM client。同步调用，请求会阻塞 worker 几十秒。
# 后面体验完阻塞痛点，再加 async / queue / streaming。
# ---------------------------------------------------------------------------
_client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
MODEL = "claude-sonnet-4-5"  # 想换模型在这里改

PROMPT_TEMPLATE = """You are a clinical pharmacist. Generate a care plan for the following patient.

Patient Info:
- Name: {first_name} {last_name}
- MRN: {mrn}
- Primary Diagnosis (ICD-10): {primary_diagnosis}
- Medication: {medication}
- Additional Diagnoses: {additional_diagnoses}
- Medication History: {medication_history}
- Referring Provider: {provider_name} (NPI: {provider_npi})
- Patient Records:
{patient_records}

Output the care plan with EXACTLY these 4 sections, in this order:
1. Problem List / Drug Therapy Problems
2. Goals (SMART)
3. Pharmacist Interventions / Plan
4. Monitoring Plan & Lab Schedule

Use plain text. Do not use markdown formatting like ** or #.
"""


def form(request):
    """GET / -> 显示录入表单"""
    return render(request, "care_plan/form.html")


def generate(request):
    """POST /generate/ -> 收表单 -> 调 LLM -> 渲染结果

    注意这里没有任何 validation、没有 try/except、没有重复检测、
    没有 warning、没有 auth。错了就直接 500 给你看堆栈。
    """
    # 1. 从表单拿数据（POST 里啥都没有时也不报错，给空字符串）
    data = {
        "first_name": request.POST.get("first_name", ""),
        "last_name": request.POST.get("last_name", ""),
        "mrn": request.POST.get("mrn", ""),
        "primary_diagnosis": request.POST.get("primary_diagnosis", ""),
        "medication": request.POST.get("medication", ""),
        "additional_diagnoses": request.POST.get("additional_diagnoses", ""),
        "medication_history": request.POST.get("medication_history", ""),
        "provider_name": request.POST.get("provider_name", ""),
        "provider_npi": request.POST.get("provider_npi", ""),
        "patient_records": request.POST.get("patient_records", ""),
    }

    # 2. 拼 prompt
    prompt = PROMPT_TEMPLATE.format(**data)

    # 3. 同步调 LLM —— 用户在这里干等
    response = _client.messages.create(
        model=MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    care_plan_text = response.content[0].text

    # 4. 存内存
    care_plan_id = str(uuid.uuid4())
    CARE_PLANS[care_plan_id] = {
        "patient_data": data,
        "care_plan": care_plan_text,
    }

    # 5. 渲染结果
    return render(
        request,
        "care_plan/result.html",
        {
            "care_plan_id": care_plan_id,
            "care_plan": care_plan_text,
            "data": data,
        },
    )
