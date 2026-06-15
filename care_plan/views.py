"""
全部业务逻辑都堆在 views.py 里 —— 这是故意的。
当你后面开始加 validation / duplicate detection / pharma export 时，
这个文件会迅速膨胀到几百行，你会自然产生"该拆出来"的冲动。
那时再去做分层重构，体感会比一上来就分层要深刻得多。

v0.3：数据库从单表 patient_data(JSON) 拆成规范化的 4 张表
（Patient / Provider / Order / CarePlan）。这里相应改成先落库
Patient + Provider + Order，再生成 CarePlan，用 status 跟踪生成状态。
"""

import logging
import os
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from anthropic import Anthropic

from .models import Patient, Provider, Order, CarePlan

logger = logging.getLogger(__name__)

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
- Date of Birth: {dob}
- Primary Diagnosis (ICD-10): {diagnosis}
- Medication: {medication}
- Referring Provider: {provider_first_name} {provider_last_name} (NPI: {provider_npi})
- Patient Records / History:
{records}

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
    """POST /generate/ -> 收表单 -> 落库 Patient/Provider/Order -> 调 LLM -> 存 CarePlan -> 渲染结果

    依旧没有 validation / 重复检测 / auth；错了就直接 500 给你看堆栈。
    唯一的新东西是 CarePlan.status：建单时 processing，成功 completed，异常 failed。
    """
    logger.info("收到请求  method=%s  path=%s", request.method, request.path)

    # 1. 从表单拿数据（POST 里啥都没有时也不报错，给空字符串）
    data = {
        "first_name": request.POST.get("first_name", ""),
        "last_name": request.POST.get("last_name", ""),
        "mrn": request.POST.get("mrn", ""),
        "dob": request.POST.get("dob", "") or None,
        "diagnosis": request.POST.get("diagnosis", ""),
        "medication": request.POST.get("medication", ""),
        "records": request.POST.get("records", ""),
        "provider_first_name": request.POST.get("provider_first_name", ""),
        "provider_last_name": request.POST.get("provider_last_name", ""),
        "provider_npi": request.POST.get("provider_npi", ""),
    }

    # 2. 落库：按 MRN / NPI 复用已有的 Patient / Provider，没有就建。
    patient, _ = Patient.objects.get_or_create(
        mrn=data["mrn"],
        defaults={
            "first_name": data["first_name"],
            "last_name": data["last_name"],
            "dob": data["dob"],
        },
    )
    provider, _ = Provider.objects.get_or_create(
        npi=data["provider_npi"],
        defaults={
            "first_name": data["provider_first_name"],
            "last_name": data["provider_last_name"],
        },
    )
    order = Order.objects.create(
        patient=patient,
        provider=provider,
        medication=data["medication"],
        diagnosis=data["diagnosis"],
        records=data["records"],
    )

    # 3. 先建 CarePlan 占位，status=processing
    plan = CarePlan.objects.create(order=order, status=CarePlan.Status.PROCESSING)

    # 4. 拼 prompt 并同步调 LLM —— 用户在这里干等
    prompt = PROMPT_TEMPLATE.format(**data)
    logger.info("开始调用 LLM  model=%s  prompt_len=%d", MODEL, len(prompt))
    try:
        response = _client.messages.create(
            model=MODEL,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception:
        # 失败也落库一个状态，方便后面排查 / 重试；DEBUG 下照样把堆栈抛出来给你看
        plan.status = CarePlan.Status.FAILED
        plan.save(update_fields=["status"])
        logger.exception("LLM 调用失败  care_plan_id=%s", plan.id)
        raise

    care_plan_text = response.content[0].text
    logger.info("LLM 返回  text_len=%d  usage=%s", len(care_plan_text), response.usage)

    # 5. 写回结果，status=completed
    plan.content = care_plan_text
    plan.status = CarePlan.Status.COMPLETED
    plan.save(update_fields=["content", "status"])

    # 6. 渲染结果
    return render(
        request,
        "care_plan/result.html",
        {
            "care_plan_id": str(plan.id),
            "care_plan": care_plan_text,
            "patient": patient,
            "order": order,
        },
    )


def detail(request, care_plan_id):
    """GET /care_plans/<id>/ -> 按 id 从数据库取一条 care plan

    get_object_or_404 找不到时自动抛 Http404（内部会处理 id 格式不合法的情况），
    所以不用自己写 .get() + if None 那一套。
    select_related 一次 join 把 order/patient 取出来，省得后面 N 次查询。
    """
    logger.info("care_plan_id = %s", care_plan_id)
    plan = get_object_or_404(
        CarePlan.objects.select_related("order__patient"), pk=care_plan_id
    )
    patient = plan.order.patient
    logger.info("care plan found, id=%s  status=%s", care_plan_id, plan.status)
    return HttpResponse(
        f"got {patient.first_name} {patient.last_name} "
        f"care plan [{plan.status}]:\n{plan.content}"
    )
