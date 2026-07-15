# Детализация фаз: API / Worker / Agent Runtime split

> Дочерний документ к [`MICROSERVICES_SPLIT_PLAN.md`](MICROSERVICES_SPLIT_PLAN.md) §7.
> Здесь фазы 1–7 из §7 разбиты на под-фазы с маленьким diff'ом каждая: что меняется,
> в каких файлах, как проверить, что ничего не сломалось. §8/§9 (domain-agnostic ядро,
> память) сюда не входят — там не "фазы" в этом смысле, а рефактор-цели и целевая
> модель; если нужно разбить и их на маленькие диффы так же, это отдельный запрос.
>
> В процессе этой детализации нашлись три конкретных архитектурных факта, которых не
> было в исходном плане и которые меняют порядок/содержание некоторых под-фаз. Они
> вынесены в начало, т.к. влияют не на одну фазу, а на несколько.

## Открытие A: process-local in-memory state ломается при переходе на отдельный процесс/контейнер

`cys_core/application/workers/tool_execution_tracker.py:15-24` — это модульные
Python-словари (`_counts`, `_manifests`, `_outputs`, `_persona_manifests`, ...) под
`threading.Lock`, не Redis/Postgres. Комментарий в самом коде уже это признаёт
(`run_worker_job.py:183-189`): *"both are process-local in-memory state; the worker
and critic run as separate processes in every real deployment topology here"*.

Сегодня это работает, потому что и запись (`record_tool_execution`, `record_evidence_manifest`
и т.д., вызываются изнутри `RunWorkerJob.execute()`), и чтение после таймаута
(`get_tool_execution_count(job.job_id)` в `orchestrator.py` после `TimeoutError`,
`try_salvage_partial()` → `get_tool_outputs(job.job_id)` в `run_worker_job.py:250`)
происходят **в одном и том же процессе Worker'а**.

Как только `execute()` начинает исполняться в отдельном subprocess/контейнере
(Phase 2/3), а Dispatcher (`WorkerOrchestrator.run_job()`) остаётся в родительском
процессе — эти вызовы читают **пустые** словари родителя, а не то, что накопил
дочерний процесс. Последствия:

- soft-timeout salvage (`try_salvage_partial`) перестаёт находить какие-либо
  `tool_outputs` → всегда возвращает `None` → job просто фейлится вместо того, чтобы
  салважиться частичным findings;
- `tool_count` в логе таймаута (`orchestrator.py`, `logger.error("worker job timed out",
  tool_count=tool_count, ...)`) всегда будет `0`, теряя диагностическую ценность;
- `clear_tool_execution_count(job.job_id)` в `finally`-блоке `orchestrator.py` станет
  no-op на родителе (безвредно само по себе, но признак той же проблемы).

**Вывод**: это блокер именно для Phase 2 (subprocess backend), не только для Phase 3
(контейнеры/K8s) — иначе для subprocess-бэкенда пропадёт soft-timeout-salvage, который
сегодня реально работает. Решение встроено в под-фазы Phase 2 ниже (2.2a/2.2b).

## Открытие B: HITL resume уже сегодня исполняется мимо Dispatcher'а — не sandboxed вообще

`interfaces/api/app.py:467-490`, `POST /jobs/{job_id}/resume` вызывает
`resume_worker_job(job_id, body)` (`interfaces/worker/hitl_resume.py:16-24`)
**синхронно, внутри обработчика HTTP-запроса в процессе API**, который дергает
`get_runtime()` и продолжает LangGraph-граф прямо там же, блокируя HTTP-ответ до
завершения (или до возврата `ResumeHitlJob.execute`).

Это не гипотетический риск будущего сплита — это уже сегодня существующий разрыв:
resume **никогда не проходит** через `WorkerOrchestrator`/`SandboxConnector`/бюджет/
tool gateway policy, которые применяются к обычным job'ам через очередь. Approved
HITL-действие (то есть ровно то самое high-impact действие, которое требовало
человеческого одобрения) продолжает исполняться **без** тех же изоляционных гарантий,
что обычные worker-job'ы. Это релевантно и для §10 плана (validation & hardening) —
это дыра уже сегодня, не только после Dispatcher/Runtime split.

**Вывод**: Phase 6 должен не просто "чинить risk из §5", а закрывать реально
существующую сегодня несогласованность — resume обязан идти через ту же очередь и того
же Dispatcher'а, что и обычные job'ы, а не исполняться инлайн в API-процессе.

## Открытие C: двойной вызов `SandboxConnector.create()` для одного `run_id`

`RunWorkerJob.execute()` сам вызывает `self._create_sandbox(...)` →
`self.sandbox.acreate(run_id, persona, policy)` (`run_worker_job.py:817`, реализация
`_create_sandbox` в строках 384+) — то есть минт `SandboxCredentials` для MCP Tool
Gateway происходит **изнутри** `execute()`, независимо от того, кто и как решил, где
физически исполняется этот код.

Если в Phase 3 Dispatcher **тоже** использует `SandboxConnector.create()` (тот же порт)
для того, чтобы породить под/контейнер, в котором затем запустится `execute()` — то
`execute()`, запустившись внутри уже созданного пода, снова вызовет `sandbox.acreate()`
**для того же `run_id`**. Для `K8sSandboxConnector` это буквально упадёт: в коде есть
явный guard (`k8s_sandbox.py`, `create()`) — *"if run_id in self._job_names: raise
RuntimeError(f"sandbox already active for run_id={run_id!r}; refusing to reuse state")"*.

**Вывод**: нужно явно разделить две роли, которые сегодня совмещены в одном порту
`SandboxConnector`:

1. **Placement** — "породить процесс/под/VM, в котором будет исполняться `execute()`"
   (это то, что делает новый `ExecutionBackend` из Phase 1–3).
2. **Credentials** — "выдать `SandboxCredentials` для MCP Tool Gateway на этот job"
   (это то, что уже делает `_create_sandbox()` внутри `execute()`).

Для in-process и subprocess бэкендов (Phase 1–2) это не проблема — `execute()` там
единственный, кто вызывает `sandbox.acreate()`. Для K8s/Docker бэкенда (Phase 3) —
нужно решить один раз: либо (а) `execute()`, запущенный через `run-sandboxed-job`
entrypoint, получает уже сминченные credentials через job payload/env и **пропускает**
собственный вызов `_create_sandbox()`, либо (б) `ExecutionBackend` для K8s/Docker не
использует `SandboxConnector.create()` для самого создания пода (это делает
Kubernetes Job API напрямую), оставляя `SandboxConnector.create()` только за
`execute()` как единственным вызывающим. Вариант (б) проще и меньше меняет
существующий код — рекомендуется по умолчанию, см. Phase 3.3.

## Открытие D: `JobBudgetTracker`/`configure_job_cost` — та же process-locality болезнь, что Открытие A, но это уже enforcement, а не диагностика

Найдено при проектировании Phase 2 (не было в исходном плане). `cys_core/domain/workers/job_budget.py`
— `JobBudgetTracker._states`/`_profile_costs` и модульная `_cost_per_1k_tokens_usd` — это
**точно такие же** process-local словари/globals под classmethod-интерфейсом, что и
`tool_execution_tracker` из Открытия A. Сегодня `WorkerOrchestrator.run_job()`
(`orchestrator.py:154-166`) делает `configure_job_cost(cost_rate, profile_id=profile_id)`
и `JobBudgetTracker.configure(session_id, max_tokens=..., max_cost_usd=..., max_tool_calls=...,
profile_id=profile_id)` **до** вызова `execute()` — и именно это единожды-конфигурированное
состояние читают:

- `cys_core/middleware/security_middleware.py:105,159` — `JobBudgetTracker.check_tool_call(session_id)`
  **перед каждым вызовом инструмента**, то есть это не диагностика, а реальный enforcement
  budget/DoW-лимита (часть §10 hardening baseline);
- `cys_core/runtime/agent.py:490,587,611` — `record_tokens()` на каждый LLM-вызов;
- `run_worker_job.py:298,578,692,776` — `JobBudgetTracker.get(session_id)` для контроля
  бюджета в разных точках пайплайна;
- `job_finalizer.py:142` — финальное чтение `tokens_used`/`cost_usd` для метрик и биллинга.

Как только `execute()` переезжает в дочерний процесс (Phase 2 subprocess, Phase 3
контейнеры), а `configure()` остаётся в родителе (`WorkerOrchestrator.run_job()`) —
`JobBudgetTracker.get(session_id)` в дочернем процессе всегда возвращает `None`.
Последствия хуже, чем в Открытии A, потому что это не только "теряем диагностику при
таймауте", а: **`check_tool_call()` при отсутствующем state в текущей реализации не
падает и не блокирует** (нет state → нечего проверять) — то есть tool-call budget cap
и cost cap **молча перестают действовать** для любого job'а, исполняемого вне
родительского процесса. Отдельно, `configure_job_cost(cost_rate, profile_id=...)` — тоже
модульный global; `Container.__init__` уже вызывает `configure_job_cost(settings.job_cost_per_1k_tokens_usd)`
при старте (это восстанавливает диапазон **default**-ставки в любом свежем процессе,
включая дочерний), но per-profile override (когда у профиля своя, отличная от default,
`cost_per_1k_tokens`) не переживает границу процесса — дочерний процесс использует
default-ставку вместо профильной.

**Вывод**: это блокер для Phase 2, не только для Phase 3 — так же, как Открытие A.
Решение по той же схеме: **`run-sandboxed-job` entrypoint** (Phase 2.2b) должен сам
вызывать `JobBudgetTracker.configure(...)` (и, если профильная cost-ставка отличается от
default, `configure_job_cost(cost_rate, profile_id=profile_id)`) **внутри дочернего
процесса**, до вызова `execute()`, используя `budgeted`/`profile_id`/`cost_rate`,
переданные через job payload — а не полагаться на то, что родитель уже это сделал
(родительская конфигурация в этом случае действует только на несуществующий, "свой"
`JobBudgetTracker`-namespace родительского процесса и никак не видна дочернему). После
завершения — `JobBudgetTracker.clear(session_id)` в `finally` дочернего процесса
(симметрично тому, что уже делает `WorkerOrchestrator.run_job()` сегодня в родителе для
in-process backend'а).

---

## Phase 1 — extract `ExecutionBackend` port, без изменения поведения

**1.1.** Добавить новый файл `cys_core/application/ports/execution_backend.py` —
протокол `ExecutionBackend` с одним методом, сигнатура 1-в-1 как у
`RunWorkerJob.execute`:

```
async def execute(job: WorkerJob, budgeted: WorkerJob, session_id: str, job_state: dict) -> RunResult
```

Diff: один новый файл, ничего не подключено. Тесты не нужны (просто протокол).

**1.2.** Добавить `cys_core/infrastructure/execution/in_process.py` —
`InProcessExecutionBackend(run_worker_job: RunWorkerJob)`, чей `execute()` — это
буквально `return await self._run_worker_job.execute(job, budgeted, session_id, job_state)`.
Diff: один новый файл, простая обёртка, ноль новой логики.

**1.3.** В `WorkerOrchestrator.__init__` (`orchestrator.py`) добавить параметр
`execution_backend: ExecutionBackend | None = None`, по умолчанию —
`InProcessExecutionBackend(self._run_worker_job)`. В `run_job()` заменить единственный
вызов `self._run_worker_job.execute(job, budgeted, session_id, job_state)` внутри
`asyncio.wait_for(...)` на `self.execution_backend.execute(job, budgeted, session_id, job_state)`.
Всё остальное (budget/timeout/salvage/finally) остаётся в `WorkerOrchestrator` —
переносится **только** сам вызов исполнения, не окружающая его Dispatcher-логика.
Diff: несколько строк в существующем файле.

**1.4.** `bootstrap/container.py`, `get_worker_orchestrator(...)` — читает новую
настройку `settings.execution_backend` (`in_process` по умолчанию) и передаёт
соответствующий backend; для значений кроме `in_process` пока — `NotImplementedError`
с понятным сообщением ("будет в Phase 2/3").

**1.5.** Проверка: существующий тестовый набор `tests/workers/` и `tests/domain/workers/`
проходит без единого изменения (это критерий "no behavior change"). Добавить один новый
тест `tests/workers/test_execution_backend_port.py`, который явно проверяет, что
`InProcessExecutionBackend.execute(...)` даёт тот же `RunResult`, что и прямой вызов
`RunWorkerJob.execute(...)` на одном и том же job-фикстуре (golden/parity-тест —
пригодится и в Phase 2 для сравнения с subprocess-бэкендом).

Acceptance: `git diff` — один новый порт, одна новая обёртка, ~5 строк изменений в
`orchestrator.py`, один новый flag в settings. Поведение в проде не меняется, т.к.
default остаётся `in_process`.

---

## Phase 2 — `SubprocessExecutionBackend` (проверить контракт без контейнеров)

**2.0. Родитель не должен гонять свой soft-timeout параллельно с child'овым.**
`WorkerOrchestrator.run_job()` (Phase 1, не менялось) оборачивает
`self.execution_backend.execute(...)` в `asyncio.wait_for(..., timeout=soft_timeout)` и
при `TimeoutError` сам вызывает `try_salvage_partial`. Если это оставить как есть для
subprocess-бэкенда, у нас будет **гонка**: и родитель, и child (2.2a) независимо
считают от одного и того же `soft_timeout`, и если родительский таймер сработает
первым (планировщик/IPC jitter), родитель отменит await, попытается
`try_salvage_partial` на **своём** (пустом) `tool_execution_tracker`/`JobBudgetTracker`
— получит `None` — и залогирует `tool_count=0`, ровно тот баг, который 2.2a должен
был закрыть, просто с другой стороны провода.

Решение: у `ExecutionBackend`-реализаций, которые сами управляют таймаутом и salvage
(subprocess, K8s, Docker), — атрибут `owns_timeout: bool = True` (у
`InProcessExecutionBackend` — `False`, поведение Phase 1 не меняется). В
`WorkerOrchestrator.run_job()`: если `getattr(self.execution_backend, "owns_timeout", False)`
— оборачивать `execute(...)` в `asyncio.wait_for(..., timeout=job_timeout)` (**hard**,
не soft) и **не** вызывать `try_salvage_partial` при `TimeoutError` этого внешнего
таймера (нечего салважить — весь livedata в child'е; если сработал именно hard-таймер,
это значит child завис **сверх** своего собственного soft-timeout+salvage бюджета —
последний рубеж, не обычный путь). Обычный путь — child сам укладывается в
soft_timeout, сам салважит при необходимости и возвращает финальный `RunResult` — тогда
родительский `wait_for(job_timeout)` просто получает результат раньше hard-границы.

**2.1.** `cys_core/infrastructure/execution/subprocess_backend.py` —
`SubprocessExecutionBackend.execute(...)`, `owns_timeout = True`. Сериализует **envelope**,
не голый `job`: `{"job": ..., "budgeted": ..., "session_id": ..., "profile_id": ...,
"cost_rate": ..., "soft_timeout": ..., "job_timeout": ...}` (см. Открытие D — child
должен сам сконфигурировать `JobBudgetTracker`/`configure_job_cost`, для этого ему нужны
`profile_id`/`cost_rate`, которые сегодня резолвятся в родителе перед `execute()`).
Запускает `egregore run-sandboxed-job --job-json -` через `asyncio.create_subprocess_exec`
(не `shell=True` — важно, см. §10.2/OS Command Injection controls), пишет envelope в
stdin, читает stdout, парсит `RunResult` из `{"result": {...}}`, который
`cmd_run_sandboxed_job` уже печатает (`cli/main.py:105`).

**2.2a. Закрыть Открытие A — soft-timeout/salvage должны переехать внутрь child-процесса.**
Новый контракт: **`run-sandboxed-job` entrypoint сам знает `soft_timeout`** (из envelope),
сам оборачивает `RunWorkerJob.execute(...)` в `asyncio.wait_for` **внутри дочернего
процесса**, и при таймауте **сам** вызывает `try_salvage_partial` (у него есть живые
`tool_execution_tracker`-данные) — и в любом случае (успех, salvage, жёсткий фейл)
печатает **один** финальный `RunResult` в stdout.

**2.2b. Закрыть Открытие D — child должен сам сконфигурировать `JobBudgetTracker`/`configure_job_cost`.**
Правка `cmd_run_sandboxed_job` (`cli/main.py:82-106`): распаковать envelope из 2.1,
до вызова `execute()` вызвать `configure_job_cost(cost_rate, profile_id=profile_id)` и
`JobBudgetTracker.configure(session_id, max_tokens=budgeted.max_tokens,
max_cost_usd=budgeted.max_cost_usd, max_tool_calls=budgeted.max_tool_calls,
profile_id=profile_id)` — без этого `security_middleware.py`'s
`JobBudgetTracker.check_tool_call()` молча перестаёт ограничивать tool-calls внутри
child'а. Реализовать ту же soft/hard timeout+salvage-логику, что раньше была в
`WorkerOrchestrator.run_job()` (2.2a), но локально. В `finally`: `JobBudgetTracker.clear(session_id)`
и `clear_tool_execution_count(job.job_id)` — симметрично родительскому `finally` сегодня.

**2.3.** Отмена/kill: `SubprocessExecutionBackend.execute()` должен убивать дочерний
процесс (`proc.kill()`) в `finally`, если родительский `asyncio.CancelledError`/hard
timeout сработал раньше, чем child успел допечатать результат.

**2.4.** `settings.execution_backend = "subprocess"` включает этот backend через
container-wiring из 1.4.

**2.5.** Тесты: `tests/workers/test_subprocess_execution_backend.py` — parity-тест
относительно golden-теста из 1.5 (тот же job-фикстур, тот же `RunResult`, за
исключением полей, которые обязаны отличаться — например, отсутствие
process-local-специфичных счётчиков в родителе); отдельный тест на soft-timeout +
salvage именно из дочернего процесса; тест на kill при отмене.

**2.6.** Ручная проверка: поднять один worker с `EXECUTION_BACKEND=subprocess`
локально, прогнать один реальный job, убедиться, что результат приходит через
`job_store` (не просто "функция вернула значение") — это первая живая проверка
допущения из §4 основного плана.

Acceptance: контейнеров/K8s ещё нет, переключается env-переменной, `in_process`
остаётся default и не меняется.

---

## Phase 3 — container backend, закрытие задокументированного разрыва

**3.0. Сначала — зафиксировать факт, а не чинить вслепую.** Текущий K8s Job template
внутри `K8sSandboxConnector._create_job` (`k8s_sandbox.py`, `"args"`) запускает
**`python -m interfaces.worker.daemon --persona <p> --max-jobs 1`**, а не
`run-sandboxed-job`. `RUN_ID` передаётся как env var, но `daemon.py` его нигде не
читает (только `--persona`/`--max-jobs`/`--idle-timeout` через argparse). То есть
сегодня созданный K8s Job поднимает **ещё один обычный worker-демон**, который
дёргает **любой** следующий job из общей очереди для этой persona — не обязательно
тот самый job, ради которого сандбокс создавался (race condition по построению, не
"один job — один под"). Это нужно исправить в первую очередь, иначе Phase 3
достраивается поверх уже сломанного контракта.

**3.1.** Исправить Job-спеку (`k8s_sandbox.py:_create_job`, и синхронизировать с
`deploy/k8s/worker-job-template.yaml`, который сегодня, судя по всему, независимая
копия того же намерения): `args` → `["egregore", "run-sandboxed-job", "--job-json", "-"]`
(или эквивалент), а сериализованный `WorkerJob` передавать одним из двух способов —
(а) как значение доп. env var (`JOB_PAYLOAD_JSON`, если размер укладывается в лимиты
K8s env, обычно да для одного job'а) или (б) короче: под читает job по `RUN_ID` из
`job_store`/queue вместо stdin (T.к. stdin в K8s-под передать после `create` нельзя —
это не subprocess). Вариант (б) естественнее для K8s и переиспользует уже
существующий `job_store`. Это меняет `cmd_run_sandboxed_job`: добавить режим
`--job-id <id>` (читает job из job_store/queue по id) как альтернативу
`--job-json -` (stdin, используется в Phase 2 для subprocess).

**3.2. Закрыть Открытие C.** Принять решение (б) из "Открытие C" — `ExecutionBackend`
для K8s **не** использует `SandboxConnector.create()` для порождения пода (Job создаётся
напрямую через Batch API, как уже делает `K8sSandboxConnector`, но теперь это код
внутри нового `K8sExecutionBackend`, а не совмещено с методом `create()` порта
`SandboxConnector`). `_create_sandbox()` внутри `execute()`, запущенного в поде,
продолжает как раньше вызывать `sandbox.acreate()` **один раз**, изнутри — никакого
двойного вызова, т.к. под больше не порождается через тот же порт.

**3.3.** Написать `DockerAgentSandboxConnector`/`DockerExecutionBackend`
(`cys_core/infrastructure/execution/docker_backend.py`) — локальный аналог 3.2 через
`docker run` вместо Batch API, для dev/CI без реального K8s. Переиспользует тот же
`--job-id` режим `cmd_run_sandboxed_job`, что и K8s-путь.

**3.4.** `K8sExecutionBackend`/`DockerExecutionBackend` — результат читается через
`job_store` (уже написанный write-path для timeout/salvage-сценариев,
`orchestrator.py:180-221`) поллингом со стороны Dispatcher, а не через stdout (в
контейнерах stdout не читается родителем так же просто, как в subprocess).

**3.5.** Тесты: расширить существующие тесты `K8sSandboxConnector` (конструктор уже
принимает `batch_api: Any = None` для инъекции мока — переиспользовать этот паттерн)
проверкой, что теперь Job-спека содержит `run-sandboxed-job`/`--job-id`, а не
`worker.daemon`. Docker-путь — интеграционный тест, skip если Docker недоступен в CI.

Acceptance: реальный job реально исполняется в отдельном поде/контейнере, Dispatcher
узнаёт о завершении через `job_store`, Открытия A и C закрыты явно (не "получилось
случайно").

---

## Phase 4 — gVisor RuntimeClass

**4.1.** (Инфраструктура, не код) — установить containerd+gVisor shim на нодах и
`RuntimeClass` CR в кластере (или включить GKE Sandbox, если облако это даёт из
коробки).

**4.2.** `bootstrap/settings.py` — добавить `k8s_runtime_class: str | None = None`.

**4.3.** `K8sExecutionBackend`/`k8s_sandbox.py` (после 3.x) — если
`settings.k8s_runtime_class` задан, добавить `spec.template.spec.runtimeClassName`
в тело Job. Если не задан — ключ просто отсутствует (текущее поведение, runc).

**4.4.** `deploy/k8s/worker-job-template.yaml` — добавить то же поле как
Helm/kustomize-переменную (не хардкод), чтобы dev/staging/prod могли отличаться.

**4.5.** Тест: unit-тест на то, что `_create_job`/эквивалент кладёт
`runtimeClassName` в Job body dict при заданной настройке и не кладёт при пустой —
не требует реального кластера, тот же стиль, что уже есть у существующих тестов
`K8sSandboxConnector`.

**4.6.** Замер: latency/overhead cold-start на реальной persona (runc vs gVisor) —
результат определяет, нужна ли вообще Phase 5.

Acceptance: чисто инфраструктурное изменение + один optional settings-флаг, нулевое
изменение поведения при пустой настройке.

---

## Phase 5 — tiered isolation по trust level (опционально, зависит от Phase 4)

**5.1.** Сначала — решение, а не код: нужна ли вообще эта фаза, по данным замера 4.6.

**5.2.** Если да: добавить в catalog/persona-конфиг (`AgentCatalogEntry` или
policy payload) необязательное поле `runtime_class_override`, либо таблицу
`AgentTrustLevel → runtime_class` (переиспользовать `AgentTrustLevel` из
`agent_bus.py:32-36`, не изобретать новую классификацию).

**5.3.** `K8sExecutionBackend` резолвит `runtime_class` по persona/trust level вместо
единой глобальной настройки из Phase 4.

**5.4.** Инфраструктура: node pool с nested virtualization/bare-metal для Kata —
отдельная ops-задача, не в этом репозитории.

Acceptance: тот же механизм, что Phase 4, но per-persona, а не глобально; ничего не
делается, если 5.1 говорит "не нужно".

---

## Phase 6 — HITL resume rework (закрывает Открытие B, не просто "риск из §5")

**6.1.** `ResumeHitlJob.execute()` (`application/use_cases/resume_hitl_job.py`) —
вместо синхронного продолжения через `runtime.resume(...)` внутри HTTP-хендлера,
публикует **новый job на очередь** (`job_queue.aenqueue(resume_job)`) и возвращает
"resume submitted"/202-подобный ответ немедленно. `resume_job` — тот же `WorkerJob`,
но с доп. полем `resume_of_job_id`/`resume_checkpoint_ref`, указывающим, что нужно
продолжить существующий LangGraph-thread (тот же `session_id`/`thread_id`, что был у
исходного запуска — **не** новый), а не начать новый.

**6.2.** `WorkerJob`/`RunResult` модели (`cys_core/domain/workers/models.py`) —
добавить опциональное поле `resume_checkpoint_ref: str | None`.

**6.3.** `RunWorkerJob.execute()` (и его sandboxed-эквивалент из Phase 2/3) — если
`job.resume_checkpoint_ref` задан, использовать тот же `session_id`, что и оригинальный
run (не `f"worker:{persona}:{new_job.job_id}"`, а тот, что был у прерванного run), чтобы
LangGraph checkpointer (`cys_core/persistence.py`) корректно продолжил с того же места
— это уже поддерживается на уровне Postgres-checkpointer, нужно только правильно
прокинуть исходный `session_id` в новый job.

**6.4.** `interfaces/api/app.py:467-490` — эндпоинт `POST /jobs/{job_id}/resume` меняет
контракт с "синхронный результат" на "202, poll через job_store" — это ломающее
изменение для потребителей (`web_ui/lib/api-client.ts`, `use-api-query.ts`), нужно
явно скоординировать с фронтендом (polling-цикл для resumed job уже есть для обычных
job'ов, скорее всего переиспользуется без нового кода на фронте — но нужно проверить,
не предполагать).

**6.5.** Тесты: `tests/worker/test_hitl_resume_dispatch.py` — resume кладёт job на
очередь с правильным `resume_checkpoint_ref`/`session_id`; существующие тесты
`resume_hitl_job` адаптировать под новый (асинхронный) контракт.

Acceptance: HITL resume теперь всегда идёт через тот же Dispatcher → ExecutionBackend
путь, что обычные job'ы — то есть с тем же бюджетом, sandbox/tool-gateway policy,
что и всё остальное. Это закрывает реально существующую сегодня дыру (Открытие B),
не гипотетический будущий риск.

---

## Phase 7 — warm pool (опционально, только если cold start после Phase 4 мешает SLA)

**7.1.** Единственное, что делается сразу — решение по данным 4.6: нужен ли warm pool
вообще. Если Phase 4 показывает, что gVisor cold-start укладывается в текущий
`job_timeout`/`worker_soft_timeout_fraction` бюджет — эта фаза не нужна.

**7.2.** Если да — это отдельный, более крупный design (claim/release API на
`ExecutionBackend`, отдельный pool-координатор, Deployment из N дежурных подов вместо
Job per job) — заслуживает отдельного планового документа, а не сжатия в маленькие
диффы здесь.

Acceptance: явное решение "делаем/не делаем" зафиксировано; если делаем — заводится
отдельный план.
