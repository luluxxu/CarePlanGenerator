# Care Plan Generator — MVP

最小可跑通骨架：Django + 一个表单页 + 一个调 LLM 的 view + 内存字典存储。

## 它**有意**没做的事

| 没做 | 你后面加它的时候会感受到什么 |
| --- | --- |
| Validation / 错误处理 | 输错 NPI、漏填字段、PDF 上传——任何一处都会 500 给你看 |
| 重复检测 (patient / order / provider) | 同一个患者可以无限提交，数据"看起来"在涨但其实是脏的 |
| 异步 / 队列 / worker | LLM 调用同步阻塞，并发 5 个请求 worker 就吃满了 |
| 数据库 | 重启进程 = 数据全没；多个 worker 之间不共享 |
| Auth / 权限 | 任何人访问 8000 端口都能生成 care plan |
| CSRF / 安全头 | 现在表单是裸的，没法上生产 |
| 测试 | 改任何代码都得手动点一遍 |
| 分层 (service / repository) | `views.py` 一直加东西会肿成几百行，自然产生拆分冲动 |
| 日志 / 审计 | 出了问题不知道是谁、什么时候、生成了什么 |

每加一项之前，先在当前版本"撞一次南墙"，再去加，记忆点会更牢。

## 跑起来

### 1. 准备 API key

```bash
cp .env.example .env
# 编辑 .env，把 ANTHROPIC_API_KEY 换成你自己的
```

或者直接 export：

```bash
export ANTHROPIC_API_KEY=sk-ant-xxxx
```

### 2. 启动

```bash
docker compose up --build
```

第一次会拉镜像 + 装依赖，大概 1-2 分钟。

### 3. 用

打开 `http://localhost:8000`，表单已经预填了示例数据，直接点 **Generate Care Plan**。

等 15-60 秒（同步阻塞，浏览器会一直转圈，这就是同步的痛），care plan 显示出来。

### 4. 停掉

`Ctrl+C`，或者另开终端 `docker compose down`。

## 目录结构

```
CarePlanGenerator/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── manage.py
├── .env.example
├── config/               # Django project config
│   ├── __init__.py
│   ├── settings.py       # 极简，没装 auth/admin/db apps
│   ├── urls.py
│   └── wsgi.py
└── care_plan/            # 业务 app
    ├── __init__.py
    ├── apps.py
    ├── urls.py
    ├── views.py          # 👈 所有逻辑都在这里
    └── templates/care_plan/
        ├── form.html
        └── result.html
```

## 数据流（一次请求的全过程）

```
Browser
   │ GET /
   ▼
views.form()  ──► 渲染 form.html
   │
   │ 用户填写 + 点 Submit
   │ POST /generate/  (表单字段)
   ▼
views.generate()
   ├─ 1. 从 request.POST 抓字段 → dict
   ├─ 2. 拼 PROMPT_TEMPLATE.format(**data)
   ├─ 3. anthropic SDK 同步调用 (阻塞 15-60s)
   ├─ 4. 拿到 care_plan_text
   ├─ 5. 塞进 CARE_PLANS[uuid] 内存字典
   └─ 6. render result.html
   ▼
Browser 显示结果
```

## 下一步推荐顺序（建议你按这个顺序加，每一步先"撞墙"再修）

1. **加 validation**——故意输个非法 NPI，看 500 → 学 Django form / pydantic
2. **加 try/except 和友好错误页**——故意拔网线让 LLM 失败 → 学异常边界
3. **加重复检测**——重复提交同一个 patient → 学如何在内存字典里查重
4. **加 SQLite (Django models)**——重启容器数据没了 → 学 ORM + migration
5. **加异步 (Celery + Redis 或 Django 4.1+ async views)**——同时开 5 个标签页提交 → 学 worker 模型
6. **拆分层**——`views.py` 涨到 300 行 → 学 service / repository pattern
7. **加 auth**——任何人都能访问 → 学 Django session / OIDC
8. **加测试**——某次重构挂了一个隐藏分支 → 学 pytest-django
