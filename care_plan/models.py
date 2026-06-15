import uuid

from django.db import models


# ---------------------------------------------------------------------------
# 从 v0.2 的「单表 + patient_data JSONField」升级到规范化的 4 张表：
#   Patient ──< Order >── Provider
#                 │ 1:1
#                 └── CarePlan
# 每张表用 UUID 做主键（编号），MRN / NPI 作为业务唯一键。
# ---------------------------------------------------------------------------


class Patient(models.Model):
    """病人。MRN 是业务唯一键，可用来做重复检测 / 复用现有记录。"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    mrn = models.CharField(max_length=20, unique=True)
    dob = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} (MRN: {self.mrn})"


class Provider(models.Model):
    """开方医生。NPI 全局唯一。"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    npi = models.CharField(max_length=10, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} (NPI: {self.npi})"


class Order(models.Model):
    """开药订单。一个病人 / 一个医生可以有多个订单。"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(
        Patient, on_delete=models.CASCADE, related_name="orders"
    )
    provider = models.ForeignKey(
        Provider, on_delete=models.CASCADE, related_name="orders"
    )
    medication = models.CharField(max_length=255)  # 药物
    diagnosis = models.CharField(max_length=255)  # 诊断（主诊断 ICD-10）
    records = models.TextField(blank=True)  # 病历 / 自由文本
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order {self.id} — {self.medication}"


class CarePlan(models.Model):
    """一个订单对应一份 care plan（1:1）。status 跟踪生成状态。"""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.OneToOneField(
        Order, on_delete=models.CASCADE, related_name="care_plan"
    )
    content = models.TextField(blank=True)  # LLM 生成的正文
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"CarePlan {self.id} [{self.status}]"
