# Care Plan 自动生成系统 — Design Doc

**Version:** 0.1 (Draft)
**Customer:** CVS Specialty Pharmacy
**Last Updated:** 2026-04-30

---

## 1. Background & Problem

CVS specialty pharmacy 的药剂师目前需要**手动**为每位患者撰写 care plan，单份耗时 20–40 分钟。care plan 是 Medicare 与 pharma 报销的合规要求文件。由于人力短缺，目前已有大量积压。

**目标：** 构建一个内部 Web 工具，让医疗工作者通过表单录入患者信息，由 LLM 自动生成 care plan，可下载、可打印、可上报 pharma。

**预期收益：** 单份 care plan 生成时间从 20–40 分钟下降到录入 + 审核时间（目标 < 10 分钟），消除 backlog。

---

## 2. Users & Workflow

### 2.1 Users

| 角色 | 职责 | 与系统的交互 |
| --- | --- | --- |
| Medical Assistant (MA) | 录入患者数据、触发生成 | 主要使用者 |
| Pharmacist | 审核生成结果（待确认是否需要） | 审核 / 签字（如有） |
| 患者 | 不接触系统 | 仅接收打印版 care plan |

### 2.2 Workflow

```
MA 收到开药请求
   ↓
登录系统 → 录入患者 + 订单 + 病历信息
   ↓
系统执行 validation + 重复检测
   ↓
触发 LLM 生成 care plan
   ↓
（可选：Pharmacist 审核）
   ↓
下载 care plan 文件 → 打印交给患者
   ↓
上传到 CVS 内部系统 / 导出 pharma 报告
```

---

## 3. Scope

### 3.1 In Scope (MVP)

- 患者 / 订单 / Provider 信息录入表单
- 输入数据 validation
- 患者重复检测（warning）
- 订单重复检测（warning）
- Provider 全局唯一性约束
- 调用 LLM 生成 care plan 文本
- Care plan 下载
- Pharma 报告导出

### 3.2 Out of Scope (MVP)

- 与 EHR / pharmacy management system 的集成（手动录入）
- 患者直接访问系统
- Care plan 多版本管理
- 移动端适配
- 多语言支持

---

## 4. Functional Requirements

| 编号 | 功能 | 优先级 | 说明 |
| --- | --- | --- | --- |
| FR-1 | 表单录入 | P0 | MA 输入患者、订单、Provider、病历 |
| FR-2 | 输入 validation | P0 | 字段格式 + 业务规则双层校验 |
| FR-3 | 患者重复检测 | P0 | 提交前 warning，不阻塞 |
| FR-4 | 订单重复检测 | P0 | 同患者 + 同药，warning |
| FR-5 | Provider 全局唯一 | P0 | NPI 作为唯一 key |
| FR-6 | LLM 生成 care plan | P0 | 输出固定结构 |
| FR-7 | Care plan 下载 | P0 | 文本文件，可打印 |
| FR-8 | Pharma 报告导出 | P0 | 批量导出 |

---

## 5. Data Model

### 5.1 Entities

**Patient**

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| mrn | string | 主键，唯一，格式待确认（原文 6 位 vs 示例 8 位） |
| first_name | string | 必填 |
| last_name | string | 必填 |
| dob | date | 待确认是否需要 |
| sex | enum | 待确认是否需要 |
| weight_kg | number | 待确认是否需要（影响剂量） |
| allergies | string | 待确认 |

**Provider**

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| npi | string(10) | 主键，全局唯一 |
| name | string | 必填 |

**Order**

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| order_id | UUID | 主键 |
| patient_mrn | FK → Patient | 必填 |
| provider_npi | FK → Provider | 必填 |
| medication_name | string | 必填 |
| primary_diagnosis | ICD-10 code | 必填 |
| additional_diagnoses | list[ICD-10] | 可选 |
| medication_history | list[string] | 可选 |
| patient_records | text / pdf | 可选 |
| created_at | timestamp | 自动 |

**CarePlan**

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| care_plan_id | UUID | 主键 |
| order_id | FK → Order | 1:1 关系（一个订单一份 care plan） |
| problem_list | text | LLM 输出 |
| goals | text | LLM 输出 |
| pharmacist_interventions | text | LLM 输出 |
| monitoring_plan | text | LLM 输出 |
| generated_at | timestamp | 自动 |
| llm_model_version | string | 审计用 |

### 5.2 关系图

```
Patient (1) ────< Order (N) >──── (1) Provider
                    │
                    │ 1:1
                    ↓
                CarePlan
```

---

## 6. Validation Rules

### 6.1 Field-Level (Syntactic)

| 字段 | 规则 |
| --- | --- |
| First/Last Name | 非空，最大 100 字符，允许 Unicode + 空格 + `-` + `'` |
| NPI | 10 位数字，建议加 Luhn checksum 校验 |
| MRN | **待澄清**（6 位 vs 8 位带前导零） |
| ICD-10 | 正则 + 字典匹配（active codes） |
| Medication Name | 非空，**待澄清**是否要求映射 RxNorm |
| PDF | MIME 类型 + 文件大小上限（建议 ≤ 10 MB） |

### 6.2 Cross-Field (Semantic)

- Primary diagnosis 必须在 active ICD-10 字典中
- Additional diagnoses 不能与 primary 重复
- NPI 在 Provider 表中已存在但 name 不同 → warning（可能数据录入错误）

### 6.3 错误处理

- **阻塞性错误**（格式错误、缺必填）：禁用提交按钮，字段下方红字
- **Warning**（疑似重复、NPI 不一致）：可勾选确认后提交
- 错误信息**不能泄露 PHI**到日志或 stack trace

---

## 7. 重复检测规则

### 7.1 Patient Duplicate

| 触发条件 | 处理方式 |
| --- | --- |
| MRN 完全匹配现有患者 | 直接复用现有 patient record，不算 duplicate |
| First + Last + DOB 相同但 MRN 不同 | Warning：可能重复，展示并排比较 |
| Fuzzy match（Levenshtein 距离 ≤ 2 的 name） | Warning（可配置阈值） |

### 7.2 Order Duplicate

**定义：** 同一 patient + 同一 medication，且在 N 天内（默认 N=30，可配置）。

| 处理 | 说明 |
| --- | --- |
| Warning 展示 | 列出已有 order 的日期、provider |
| MA 可覆盖 | 勾选 "Confirmed not duplicate" 后允许提交 |

### 7.3 Provider Uniqueness

- NPI 是 Provider 的全局唯一 key
- 录入时若 NPI 已存在 → 自动复用现有记录
- 若 NPI 已存在但 name 不同 → warning，要求 MA 二次确认

---

## 8. Care Plan 生成

### 8.1 输出结构（强制）

每份 care plan 必须包含 4 个 section：

1. **Problem List / Drug Therapy Problems (DTPs)**
2. **Goals (SMART)**
3. **Pharmacist Interventions / Plan**
4. **Monitoring Plan & Lab Schedule**

### 8.2 LLM 调用

| 项目 | 决策 |
| --- | --- |
| 模型选择 | **待定**（须满足 HIPAA BAA） |
| Prompt 模板 | 由 pharmacist 与工程师共同设计，存版本号 |
| 输入数据 | 表单结构化字段 + patient_records 文本（PDF 须先抽取文本） |
| 输出格式 | 固定 4 段结构的纯文本（后续可考虑 JSON → render） |
| 超时 | 60s，超时显示重试按钮 |
| 失败处理 | 保留已填表单数据，允许重试或手动撰写 |

### 8.3 安全护栏

- **剂量字段后校验：** LLM 输出中的数字剂量与药品标准剂量范围比对，超出 → 高亮 warning
- **审计日志：** 记录 prompt + response + model version + timestamp + user
- **签字流程**（待定）：是否需要 pharmacist review/approve 后才能下载

---

## 9. 导出 (Pharma Report)

### 9.1 触发方式

- 手动按钮：选时间范围 + pharma 厂商 → 生成报告
- 后续可加定时任务（out of MVP）

### 9.2 格式（待澄清）

| 候选 | 说明 |
| --- | --- |
| CSV | 默认，结构化字段 |
| PDF | 如 pharma 要求 |
| 厂商专属格式 | **需收集各 pharma 的 spec** |

### 9.3 字段（初稿）

`patient_mrn`, `medication`, `primary_diagnosis`, `provider_npi`, `care_plan_generated_at`

> **合规问题：** PHI 是否需要 de-identification？取决于与 pharma 的 BAA 条款。

---

## 10. Non-Functional Requirements

| 维度 | 要求 |
| --- | --- |
| 安全 | HIPAA 合规；TLS in transit；AES-256 at rest |
| 认证 | SSO（待定 IdP）；RBAC（MA / Pharmacist / Admin） |
| 审计 | 所有读、写、生成、导出操作记录 user + timestamp |
| 可用性 | 99.5%（MVP），后续提升 |
| 性能 | 表单加载 < 1s；LLM 生成 < 60s |
| 测试 | Critical 路径单元测试 + 关键 e2e；coverage ≥ 70% |
| 部署 | Docker Compose 一键启动；secret 通过 env 注入 |

---

## 11. Architecture (High-Level)

```
┌─────────────┐
│   Browser   │ (MA / Pharmacist)
└──────┬──────┘
       │ HTTPS
┌──────▼──────────────────────────┐
│   Web App (React + API server)  │
│   ├─ Form / Validation          │
│   ├─ Duplicate Detection        │
│   └─ Auth & RBAC                │
└──────┬─────────────┬────────────┘
       │             │
┌──────▼──────┐ ┌────▼─────────┐
│  Database   │ │  LLM Service │
│ (Postgres)  │ │ (HIPAA-safe) │
└─────────────┘ └──────────────┘
       │
┌──────▼──────┐
│ Object Store│ (PDF, care plan files)
└─────────────┘
```

**Modularity:**

- `validators/` — 字段 + 业务规则
- `duplicates/` — 患者 / 订单 / provider 检测
- `llm/` — prompt 构建、调用、retry、审计
- `export/` — pharma 报告生成
- `api/` — REST endpoints
- `db/` — schema + repository
- `ui/` — React 组件

---

## 12. Open Questions（需向客户澄清）

1. **MRN 格式** — 6 位还是带前导零的更长格式？
2. **必填字段范围** — DOB / Sex / Weight / Allergies 是否纳入表单（剂量计算依赖 weight）
3. **LLM 选型** — 客户能否接受 Anthropic / OpenAI 等外部 API（须 BAA）；还是必须自托管
4. **Pharmacist sign-off** — care plan 是否必须经药剂师审核才能下载
5. **Pharma 报告格式** — 各 pharma 厂商的具体 spec
6. **重复检测阈值** — order duplicate 的时间窗口；patient fuzzy match 的相似度阈值
7. **PDF 处理** — patient records PDF 是否需要 OCR；多文件支持
8. **现有数据迁移** — backlog 中已有的患者 / provider 信息如何导入
9. **Medication 标准化** — 是否要求映射到 RxNorm / NDC

---

## 13. Milestones (建议)

| Phase | 内容 | 预计周期 |
| --- | --- | --- |
| M1 | 数据模型 + 表单 + validation | 2 周 |
| M2 | 重复检测 + Provider 唯一性 | 1 周 |
| M3 | LLM 集成 + care plan 生成 | 2 周 |
| M4 | 导出 + 审计日志 | 1 周 |
| M5 | 安全加固 + e2e 测试 + 部署 | 2 周 |

---

## 14. Appendix

### A. 输入示例
见 `1.1 原始需求文档`（A.B. / IVIG / Myasthenia gravis 案例）

### B. 输出示例
care plan 包含 Problem list、SMART Goals、Pharmacist interventions、Monitoring plan 四部分。
