# Детализация фаз: API / Worker / Agent Runtime split

> Дочерний документ к [`MSP_BACKLOG.md`](MSP_BACKLOG.md) §7.
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

## Открытие E: `JobStorePort` не хранит сериализованный job — вариант (б) из 3.1 требует миграции схемы, которой ещё нет

Найдено при реализации Phase 3. `cys_core/application/ports/job_store.py` — `JobRecord`
хранит только лёгкие метаданные (`job_id`, `session_id`, `persona`, `status`,
`pending_hitl`, `correlation_id`, `tenant_id`, `event_id`, ошибки) — **не** сам `WorkerJob`/
`budgeted`/`session_id`-контекст, нужный, чтобы реально вызвать `execute()`. То есть
вариант (б) из 3.1 ("под читает job по `RUN_ID` из `job_store`") сегодня физически
нечем читать — потребовал бы отдельную миграцию схемы + новый метод порта
(`get_payload(job_id)`/аналог), что само по себе отдельная под-фаза, а не деталь Job-спеки.

**Решение для этой фазы**: вариант (а) — передать envelope как значение env var
(`JOB_PAYLOAD_JSON`) в теле K8s Job. Один job — один под, envelope одного job'а
(job+budgeted+session_id, без сжатия) на практике далеко умещается в лимит K8s на
суммарный размер env (обычно единицы КБ на такой payload против лимита в районе
1 МБ на под). Если это когда-то перестанет умещаться (очень большие payload'ы) —
тогда действительно нужна отдельная под-фаза на job_store-схему; не блокирует эту.

## Открытие F: `K8sSandboxConnector.create()`, вызванный изнутри пода, который сам же породил `K8sExecutionBackend`, создаст **второй**, паразитный Job

Прямое продолжение Открытия C, но конкретнее, чем "решить один раз" — вот что происходит
буквально: `K8sExecutionBackend` (новый, Phase 3.2) создаёт под через Batch API напрямую
(decision (б) из Открытия C). Внутри этого пода запускается `run-sandboxed-job` →
`RunWorkerJob.execute()` → `_create_sandbox()` → `self.sandbox.acreate(run_id, ...)`, где
`self.sandbox` — это **новый экземпляр** `K8sSandboxConnector` (свежий процесс, пустой
`_job_names`). Guard `"sandbox already active for run_id"` в `create()` проверяет только
`_job_names` **этого** экземпляра — он **не сработает**, потому что это другой процесс.
Вместо явной ошибки `create()` молча создаст **второй**, паразитный K8s Job — хуже, чем
падение: тихая утечка ресурсов, а не громкий фейл.

**Решение**: `K8sSandboxConnector` получает флаг `credentials_only: bool` (из
`settings.k8s_sandbox_credentials_only`, читаемого через env `K8S_SANDBOX_CREDENTIALS_ONLY`).
Когда `True` — `create()`/`acreate()` **не** вызывают `_create_job`/`_wait_job_ready`
вообще, а сразу минтят и возвращают `SandboxCredentials` (под уже существует — это и есть
текущий контекст исполнения). `K8sExecutionBackend` кладёт
`K8S_SANDBOX_CREDENTIALS_ONLY=true` в env спеки пода, которую сам создаёт — так что
`get_sandbox_connector()` внутри `execute()`, запущенного в этом поде, увидит флаг через
обычный `Settings` (env-driven) и не попытается породить ещё один Job. Снаружи пода
(текущее прямое использование `K8sSandboxConnector` где угодно ещё) флаг остаётся `False`
по умолчанию — поведение не меняется.

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

**3.3. (Реализовано иначе, чем в изначальной формулировке.)** `DockerExecutionBackend`
(`cys_core/infrastructure/execution/docker_backend.py`) написан как тонкая обёртка
**вокруг `SubprocessExecutionBackend`** (композиция), а не независимая копия его логики.
Причина: в отличие от K8s-пода, `docker run -i ...` (без `-d`) форвардит stdin/stdout
контейнера в процесс `docker` CLI буквально так же, как обычный subprocess — то есть
Docker-путь может и должен переиспользовать stdin-envelope-in/stdout-RunResult-out
контракт из Phase 2 **напрямую**, без envelope-через-env-var трюка, нужного только для
K8s (там пода стандартный stdout-пайплинг с Batch API недоступен). Никакого
`K8S_SANDBOX_CREDENTIALS_ONLY`-аналога Docker-пути тоже не нужно — этот флаг существует
только потому, что `K8sSandboxConnector.create()` иначе породил бы второй Kubernetes Job
(Открытие F); у Docker-sandbox-коннектора нет такого побочного эффекта размещения, с
которым нужно бороться.

**3.4. (Реализовано только для K8s; для Docker — сознательное отклонение.)**
`K8sExecutionBackend` читает результат через `job_store` поллингом (метод `.get(job_id)`,
терминальные статусы `COMPLETED`/`FAILED`/`AWAITING_APPROVAL`) — как и планировалось,
т.к. Batch API не даёт простого способа получить stdout пода синхронно. Но по пути
нашлось ещё одно: `JobStorePort`/`JobRecord` не хранит сам `RunResult.finding` — только
статус/ошибку (тот же класс проблемы, что Открытие E). Реконструированный `RunResult`
для K8s поэтому даёт `finding={}` — не "finding потерялся", а именно "это поле не
проезжает через это конкретное значение порта для этого backend'а": сам finding уже
проходит через agent bus/engagement store независимо от `ExecutionBackend`, как и для
всех остальных backend'ов. Docker, поскольку читает результат через stdout (3.3), **не**
имеет этого ограничения — `RunResult.finding` доезжает так же полно, как у
`SubprocessExecutionBackend`.

**3.5.** Тесты: `tests/infrastructure/test_k8s_execution_backend.py` — тот же паттерн
инъекции мока (`batch_api`), что уже был у `K8sSandboxConnector`-тестов, плюс fake
`job_store`; проверяет, что Job-спека теперь содержит `uv run egregore
run-sandboxed-job --job-json env:JOB_PAYLOAD_JSON`, а не `worker.daemon`, плюс
успех/фейл/таймаут поллинга и отсутствие batch API → RuntimeError.
`tests/infrastructure/test_docker_execution_backend.py` — **настоящий** интеграционный
тест (не мок): собирает лёгкий stand-in Docker-образ (`python:3.13-slim` + фейковый `uv`
shim поверх уже существующей subprocess-фикстуры `fake_sandboxed_job_child.py`) и реально
гоняет `docker run` через `DockerExecutionBackend`; `pytest.mark.skipif`, если Docker
недоступен.

Acceptance: реальный job реально исполняется в отдельном поде/контейнере (K8s — через
job_store, подтверждено моками; Docker — подтверждено реальным `docker run` в тесте),
Открытия A, C, F закрыты явно (не "получилось случайно").

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

## Открытие G: `JobRecord` не хранит исходный `payload` — нечем восстановить контекст для resume-job'а

Найдено при проектировании Phase 6.1/6.3 (не было в исходном плане). Confirmed вручную:
`web_ui/components/approval-actions.tsx` вызывает `resumeJob(...)` и **не читает** тело
ответа (`await resumeJob(...)`, дальше просто `setMessage("Approved")` независимо от
содержимого) — так что смена контракта на "202, poll отдельно" (6.4) **безопасна для
фронта уже сегодня**, без дополнительных изменений в `web_ui/lib/api-client.ts`. Это
подтверждает предположение плана, а не опровергает — хорошая новость.

Плохая новость — та же болезнь, что Открытие E, но теперь мешает конкретно 6.1/6.3:
`JobStorePort`/`JobRecord` (`cys_core/application/ports/job_store.py`) хранит
`persona`/`correlation_id`/`tenant_id`/`event_id`/`pending_hitl` (`tool_name`/`tool_args`/
`risk_level`/`approval_id`) — но **не** исходный `WorkerJob.payload` (`goal`, `phase`,
`alert`, `findings_summary` и т.д. — всё, от чего зависит ветвление в
`RunWorkerJob._publish_and_finalize()`: synthesis vs follow-up vs обычная finding-публикация).
Чтобы resume-job, дойдя до `RunWorkerJob.execute()`, мог корректно опубликовать результат
через **тот же** `_publish_and_finalize()`, что и обычные job'ы — нужен весь исходный
`payload`, а не только то, что уже лежит в `JobRecord`.

**Решение**: `resume_job.payload` строится из **`pending.tool_args`/`pending_hitl`
контекста плюс минимально необходимых полей из `JobRecord`** (`persona`, `correlation_id`,
`tenant_id`), **не** пытаясь заново реконструировать `phase`/`goal`/`findings_summary` —
вместо этого `RunWorkerJob`'s resume-ветка (6.3) **не** проходит через полный
`_publish_and_finalize()` с его synthesis/follow-up-специфичными разветвлениями (это
незачем — LangGraph-граф сам знает, на каком этапе он был прерван, и его собственный
чекпойнт уже кодирует это состояние); вместо этого — упрощённая финализация: создать
sandbox под **новый** `run_id` этого resume-job'а (даёт реальные MCP Tool Gateway
credentials на случай, если после `Command(resume=...)` граф продолжит вызывать
инструменты — то, чего сегодня, до этой фазы, вообще не происходит), вызвать
`runtime.aresume(persona, resume_checkpoint_ref, resume_payload)`, опубликовать finding
через `_finding_publisher.publish(...)` напрямую (не через полный `_publish_and_finalize`)
и `mark_success`/`mark_runtime_failure` на **новом** `job_id` — а не пытаться слепо
скопировать весь `_publish_and_finalize`, чьи synthesis/follow-up ветки рассчитаны на
контекст, которого resume-job структурно не имеет и не должен имитировать.

**Вывод для конкретной сессии, писавшей этот план**: это самая рискованная фаза из
всех — единственная, которая меняет `RunWorkerJob.execute()` (главный, самый сложный
файл в кодовой базе, ~900 строк) и путь для HITL-approval'ов (то есть именно те
действия, которые требовали одобрения человека **потому что они высокорисковые** — цена
тонкой ошибки здесь выше, чем где либо ещё в этом плане). Ни LangGraph-checkpointer, ни
реальный interrupted graph state нельзя проверить без живого Postgres + реального
графа с interrupt — то есть эта фаза **не может** быть протестирована так же полно, как
Phase 1–3 (golden/parity-тесты там сравнивали реальные вызовы; здесь можно протестировать
только оркестрацию вокруг `aresume`, не сам LangGraph resume). Рекомендация: реализовать
6.1/6.2 (enqueue вместо inline-исполнения, новое поле модели) — это чисто механическая,
безопасная, полностью тестируемая часть, которая **уже сама по себе** закрывает самую
острую часть Открытия B (resume больше не исполняется синхронно в API-процессе без
sandbox/бюджета вообще). 6.3 (сама resume-ветка в `RunWorkerJob.execute()`) — реализовать
отдельно, с явным ручным/интеграционным прогоном на реальном стенде с Postgres
checkpointer'ом перед тем, как считать её production-ready; не сливать в один коммит с
6.1/6.2, чтобы откат (если резюм-ветка окажется неверной) не откатывал уже рабочую и
проверенную часть исправления.

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

---

## Открытие H: живая инфраструктура нашла два реальных бага, которых моки в тестах не видели

Всё Phase 1–4/6 было протестировано только unit-тестами с фейковыми child-процессами
(`fake_sandboxed_job_child.py` и т.п.), которые всегда пишут в stdout ровно один чистый
JSON. Как только подняли реальный стек (docker-compose postgres/redis, реальный worker
daemon через `uv run egregore worker`, реальный DeepSeek через LiteLLM) и прогнали
настоящий SOC-триаж через `in_process`, `subprocess` и `docker` backend'ы — нашлись два
факта, которые ни один мок не мог поймать:

**H.1. `configure_logging()` пишет structlog JSON в stdout** (`cys_core/observability/
logging_setup.py`, докстринг: *"for stdout (Loki/Promtail ingestion)"*) — верно и нужно
для `serve`/`worker --daemon`/`coordinator`/`critic` (контейнерный log scraping), но
`cmd_run_sandboxed_job` (`interfaces/cli/main.py`) использует stdout как IPC-канал:
`SubprocessExecutionBackend.execute()` делает `json.loads(stdout.decode())` ожидая ровно
один документ. Любой реальный job (tool call, skill load, security event — всё, что
пишет `agent_security_event`/`skill_loaded`/т.п.) льёт в stdout НЕСКОЛЬКО строк JSON
до финального `{"result": ...}` → `json.loads` падает с `Extra data: line N column 1`.
`DockerExecutionBackend` наследует баг (он оборачивает `SubprocessExecutionBackend`).
Фейковый child в тестах никогда не пишет собственные логи в stdout — поэтому баг был
невидим до реального прогона с настоящим агентом.

Фикс: `configure_logging(service_name, *, stream=None)` — необязательный параметр,
по умолчанию `sys.stdout` (ноль изменений для всех остальных вызывающих). Единственный
вызов, который передаёт `stream=sys.stderr` — `cmd_run_sandboxed_job`, единственный
случай, где stdout — это не лог, а протокол.

**H.2. `DockerExecutionBackend` подключается с нулём `extra_run_args`**
(`engagement_container.py`) — в отличие от `K8sExecutionBackend` (там базовый env пода
приходит из ConfigMap/Secret на уровне кластера, а не от кода бэкенда), у Docker-пути
не было никакого способа передать сети/env в спавненный контейнер. `docker run` не
наследует env родителя и не подключается ни к какой сети по умолчанию — контейнер не
мог достучаться ни до Postgres, ни до Redis, ни до DeepSeek. Подтверждено: с ручным
`docker run --network deploy_default --env-file ...` всё работает; без этого — нет.

Фикс: `docker_network`/`docker_env_file` в `Settings`, прокинуты в `extra_run_args`
DockerExecutionBackend'а в `engagement_container.py`. Пусто по умолчанию — ноль
изменений в поведении, пока не настроено явно.

Отдельно: третий баг оказался не багом, а загрязнением окружения этой конкретной
тест-сессии (`POSTGRES_DB=cys_agi` вместо `egregore`, попавшее в реальный `os.environ`
child-процесса через `litellm/__init__.py`'s implicit `load_dotenv()`, который ищет
`.env` вверх по дереву от собственного расположения пакета внутри `.venv/`, находит
`backend/shared/.env` раньше repo-root `.env` — но только когда оба файла реально существуют и
расходятся в значении). Настоящий баг репозитория тут не в дуальном `_settings_env_files()`
(она работает как задумано), а в том, что *любой* процесс, импортирующий litellm, может
словить эту гонку, если когда-нибудь `backend/shared/.env` и repo-root `.env` разойдутся — стоит
иметь в виду, не обязательно чинить сейчас.

Все три ExecutionBackend'а (`in_process`, `subprocess`, `docker`) прогнаны сквозь
реальный стек: engagement → DeepSeek-планирование → SOC-джоба с реальными tool call'ами
→ synthesis → закрытие engagement'а, без единой ошибки парсинга после фикса H.1.
[Открытие I ниже — критик не видит evidence manifest'ы worker'а, тот же класс бага на
другой паре процессов — найдено и закрыто отдельно, при работе над первопричинами.]

**H.3.** Полный batched suite после этого нашёл ещё один эффект того же загрязнения:
`tests/infrastructure/test_config.py::test_config_computed_fields` не изолировал
`DEEPSEEK_API_KEY` (первый в приоритете `llm_api_key`), поэтому на любой машине с
реальным `deploy/.secrets/egregore-local.env` тест молча проверял бы не то значение —
раньше просто никто не запускал полный suite с настоящим локальным ключом. Починено:
тест явно очищает `DEEPSEEK_API_KEY=""` в трёх местах, где раньше полагался на то, что
переменная в принципе не задана.

---

## Открытие I: критик не видит evidence manifest'ы воркера — process-locality, но другой пример, чем A/D

Найдено при реализации фикса первопричины #1 (см. ниже) — не было в исходном списке
A–H, но это тот же класс бага, только на другой паре процессов (worker/critic, а не
Dispatcher/child). `cys_core/application/workers/tool_execution_tracker.py:144-199`
уже содержал развёрнутую inline-заметку (`NOTE(evidence-grounding-consolidation,
2026-07-14)`), написанную и оставленную как **сознательно не починенная**:
`ProcessFindingCritic._resolve_trust_score`/`_structural_issues`
(`process_finding_critic.py`) и `CriticService._enqueue_revision`
(`critic_service.py`) читают `get_persona_manifests(investigation_id)` —
process-local module-level dict, который пишет **worker** (`egregore worker --daemon`,
свой контейнер) и который поэтому почти всегда пуст в процессе критика (`egregore
critic --daemon`, отдельный контейнер) в любой реальной multi-container-топологии
этого репозитория. Практическое следствие: SOC evidence-grounding gate, который
критик должен применять к findings (`soc_evidence_gaps`, cap на `max_confidence` по
telemetry sparse/rich), **молча не срабатывает** в проде — критик пропускает
findings, которые должен был бы поймать как недостаточно обоснованные, потому что он
физически не видит manifest, который worker для этого же investigation уже собрал.

Заметка в коде уже указывала на правильный фикс (*"give `ProcessFindingCritic` access
to `EngagementStateStore` and read `engagement.evidence_manifests[persona]`"*), но не
была реализована — она специально документировала находку и откладывала фикс "pending
a deliberate fix", чтобы не консолидировать два разных lookup'а вслепую и не
замаскировать баг ложным ощущением "теперь они согласованы".

**Вывод**: это конкретный, живой сегодня экземпляр первопричины #1 (см. синтез ниже) —
не гипотетический будущий риск, как большинство Открытий A–H, а баг, действующий в
production multi-container деплое прямо сейчас, до этой сессии. Реализован в этой же
сессии как часть фикса первопричины #1.

**5 почему:**

1. Почему критик не видит manifest, который worker уже собрал для того же
   investigation? Потому что оба читают/пишут один и тот же
   `tool_execution_tracker`-module-level dict, а worker и критик — разные процессы/
   контейнеры в любой реальной топологии.
2. Почему критик вообще полагался на process-local dict, а не на что-то
   cross-process-safe? Потому что `get_persona_manifests()` — уже существующая,
   удобная, готовая функция именно с той сигнатурой, которая нужна
   (`investigation_id -> {persona: manifest}`) — путь наименьшего сопротивления при
   написании `_resolve_trust_score`/`_structural_issues`.
3. Почему не заметили, что worker и критик — разные процессы, когда это писалось?
   Потому что pytest всегда гоняет producer (worker-код) и consumer (critic-код) в
   одном интерпретаторе — тесты этого файла проходят зелёными именно потому, что
   module-level dict в тестовом процессе один и тот же, а в проде — нет.
4. Почему это не поймали раньше, если заметка в коде существует с 2026-07-14? Потому
   что заметка **сознательно** документировала находку и откладывала фикс, ожидая
   доступа к `EngagementStateStore` в конструкторе критика — правильное инженерное
   решение "не чинить вслепую", но без явного тикета/дедлайна это могло откладываться
   неопределённо долго.
5. *(первопричина)* Тот же архитектурный пробел, что и в A/D (см. синтез ниже) — нет
   контракта "cross-process-видимое состояние живёт в shared store, не в
   module-level dict" — просто на **другой** паре процессов (worker↔critic, не
   Dispatcher↔child), поэтому не был закрыт тем же фиксом, что закрыл A/D
   (Phase 2.2a/2.2b — тот фикс специфичен для Dispatcher/child, никак не касается
   worker/critic).

**Решение на каждом уровне:**

1. *(критик не видит manifest)* — сделано в этой сессии: новая функция
   `resolve_persona_manifest()` в `tool_execution_tracker.py` — сначала читает
   `EngagementStateStore.get(tenant_id, investigation_id).evidence_manifests[persona]`
   (durable, cross-process — worker уже пишет туда через
   `finding_publisher.append_engagement_finding`), падает обратно на
   `get_persona_manifests()` только если store не сконфигурирован или ничего не
   нашёл. `ProcessFindingCritic` и `CriticService._enqueue_revision` теперь оба
   используют эту функцию. Regression-тесты:
   `tests/application/test_critic_judge.py::test_critic_reads_evidence_manifest_cross_process_via_engagement_store`
   (доказывает чтение через store при пустом in-process tracker'е) и
   `::test_critic_falls_back_to_in_process_tracker_when_no_store_wired` (не ломает
   старое поведение).
2. *(путь наименьшего сопротивления — готовая process-local функция)* —
   зафиксировать в докстринге `get_persona_manifests()`, что эта функция — **не**
   cross-process-safe и не должна использоваться напрямую новым кодом, который может
   исполняться в другом процессе, чем producer — использовать
   `resolve_persona_manifest()` вместо неё.
3. *(тесты не могли поймать — один интерпретатор для producer/consumer)* — тот же
   фикс, что и корень #4 (нет live-infra test lane): этот конкретный баг был найден
   именно живым multi-container прогоном, не unit-тестом — что подтверждает, почему
   чек-лист живого прогона (см. ниже) — не разовая мера, а системная защита от целого
   класса подобных багов.
4. *(заметка существовала, но без дедлайна фикс откладывался)* — на будущее: любая
   `NOTE(...)`-заметка в коде, которая сознательно откладывает фикс, должна
   сопровождаться трекаемым тикетом/задачей (не просто текстом в коде) — иначе
   "pending a deliberate fix" может значить "навсегда".
5. *(первопричина — тот же архитектурный пробел, что и A/D, на другой паре
   процессов)* — раз этот паттерн уже проявился дважды (Dispatcher/child и
   worker/critic) на независимых участках кода, это сигнал, что фикс первопричины #1
   (Redis-backed или, как здесь, Postgres-backed — через уже существующий
   `EngagementStateStore` — shared state) должен применяться системно к **любому**
   module-level dict в `cys_core/application/workers/`, который читается не только
   тем процессом, что пишет — не только к `tool_execution_tracker`/`job_budget`
   целиком, а к паттерну в принципе. См. обновлённый синтез ниже.

---

## 5 Почему: анализ первопричин Открытий A–I

Ниже — по каждому Открытию 5 вопросов "почему?", доведённых до настоящей
первопричины, а не до того слоя, на котором применён (уже реализованный, см.
фазы выше) тактический фикс. Цель — не переписать историю уже сделанного, а
проверить: закрывает ли реализованный фикс именно первопричину, или это патч
поверх симптома, который аукнется снова в другом месте. Короткий вывод сразу:
**9 Открытий (A–I) — это не 9 независимых первопричин, а проявления 4 системных
причин**, и это меняет, откуда начинать исправление.

### Открытия A и D — process-local state (`tool_execution_tracker`, `JobBudgetTracker`)

1. Почему soft-timeout salvage и tool-call budget cap молча ломаются при
   переходе на subprocess/контейнер? Потому что `tool_execution_tracker` и
   `JobBudgetTracker` хранят данные в module-level Python-словарях, видимых
   только внутри одного процесса.
2. Почему tool-tracking и budget-tracking реализованы как in-process globals,
   а не через общее хранилище? Потому что были написаны в момент, когда
   `execute()` и Dispatcher были частями **одного и того же** процесса — не
   существовало границы процесса, которую нужно было бы пересекать.
3. Почему не использовали Redis (который уже есть в стеке) с самого начала?
   Потому что для однопроцессной топологии in-memory dict — самое простое и
   быстрое решение, и cross-process-сценарий тогда не был требованием.
4. Почему это не предугадали до начала ExecutionBackend-сплита (Phase 1–3)?
   Потому что исходный план трактовал "разделение на процессы" как вопрос
   **размещения** (subprocess/контейнер/под), а не как вопрос **модели
   данных** — влияние границы процесса на то, что можно безопасно читать
   после неё, не было явно промоделировано заранее.
5. Почему это влияние не промоделировали? Потому что в кодовой базе нет
   архитектурного контракта/правила, запрещающего заводить мутабельный
   process-local global для чего-либо, что Dispatcher может захотеть прочитать
   **снаружи** исполняющего процесса — `tool_execution_tracker` и
   `JobBudgetTracker` писались как удобный global без этой проверки, потому
   что проверки не существовало.

**Решение на каждом уровне (не только в первопричине):**

1. *(soft-timeout/budget молча ломаются)* — уже сделано, Phase 2.2a/2.2b: child
   сам владеет soft-timeout+salvage и сам вызывает
   `configure_job_cost`/`JobBudgetTracker.configure` перед `execute()`,
   симметрично чистит оба в `finally`. Это устраняет непосредственный
   наблюдаемый симптом сегодня.
2. *(это in-process globals, потому что раньше был один процесс)* —
   зафиксировать явно в докстринге `tool_execution_tracker.py`/`job_budget.py`:
   "process-local by design, валидно только пока ровно один процесс и читает,
   и пишет — не переиспользовать этот паттерн для нового backend'а без
   ревью", чтобы следующий разработчик не скопировал паттерн бездумно.
3. *(не завели shared store с самого начала, т.к. не было нужно)* — раз нужда
   уже наступила (3 backend'а из 3 её имеют), перенести backing store в
   Redis (уже в стеке): ключ `job_id`/`session_id`, TTL = `job_timeout` + запас,
   через уже существующий redis-клиент проекта — не откладывать до Phase 7.
4. *(не предугадали до начала ExecutionBackend-сплита)* — добавить в сам план
   чеклист-пункт "Как проверять новую под-фазу": любая под-фаза, вводящая
   новую границу процесса, обязана явно перечислить, какое process-local
   состояние она пересекает — чтобы Открытия такого рода (A, D и,
   структурно, E/G) не находились заново задним числом в каждой следующей
   фазе.
5. *(первопричина — нет архитектурного контракта)* — перенести данные
   `tool_execution_tracker`/`JobBudgetTracker` в Redis-backed реализацию,
   доступную через ту же абстракцию (port), так, чтобы **любой** процесс
   (родитель, child, будущий Rust/Go-сервис) читал одно и то же состояние
   напрямую, без per-backend трюков вида "сконфигурируй локально + протащи
   результат наружу вручную". Это самый фундаментальный из 4 системных
   корней — см. задачу в task-листе, начинать отсюда.

### Открытие B — HITL resume мимо Dispatcher'а

1. Почему resume исполняется синхронно внутри HTTP-хендлера API? Потому что
   `resume_worker_job` написан как прямой вызов `get_runtime().resume(...)` —
   самый короткий путь, без похода через очередь.
2. Почему resume не завели через очередь/Dispatcher сразу, ведь паттерн для
   **обычных** job'ов уже существовал? Потому что HITL resume добавлялся как
   отдельная фича поверх уже стабильного "старт job'а через очередь", и автор
   выбрал самый прямой путь, не переиспользуя существующую абстракцию.
3. Почему "самый прямой путь" победил переиспользование абстракции? Потому
   что не было теста/линта, требующего "любой код, вызывающий agent runtime,
   обязан идти через WorkerOrchestrator/ExecutionBackend" — ничего не
   заставляло новый код соответствовать существующему паттерну.
4. Почему такой границы нет? Потому что `tests/architecture` (import-linter
   контракты) проверяет **layering** (domain не импортирует infra и т.п.), но
   не этот конкретный инвариант ("исполнение агента только через Dispatcher").
5. Почему этот инвариант не в архитектурных тестах? Потому что он не был
   идентифицирован как риск до этой планирующей сессии — HITL resume
   появился раньше, чем ExecutionBackend-абстракция и явное разделение на
   "планы" (API/Worker/Runtime), которое вводит этот план.

**Решение на каждом уровне:**

1. *(resume исполняется синхронно в HTTP-хендлере)* — уже сделано, Phase 6.1:
   `ResumeHitlJob.execute()` кладёт `resume_job` на очередь и возвращает 202
   немедленно, не дожидаясь `runtime.resume(...)`.
2. *(resume не завели через очередь сразу)* — Phase 6.2/6.3 добавляют
   `resume_checkpoint_ref`/переиспользование исходного `session_id`, то есть
   resume теперь буквально реализован как частный случай обычного job'а, а не
   как отдельный, второй способ достучаться до runtime — закрывает соблазн
   писать для "особых" операций (будущих, не только resume) свой короткий
   путь мимо очереди.
3. *("самый прямой путь" победил переиспользование абстракции)* —
   зафиксировать в CONTRIBUTING.md/архитектурном разделе явное правило:
   "новая операция, вызывающая agent runtime, обязана заходить через
   `WorkerOrchestrator`/`ExecutionBackend`, без исключений для 'быстрых'
   синхронных путей" — чтобы это было явным стандартом, а не тем, что
   выводится из чтения существующего кода.
4. *(нет линтера/теста именно на этот инвариант, хотя layering-тесты есть)* —
   расширить `tests/architecture` новым контрактом специально под этот
   инвариант (не общий layering, а конкретно "runtime вызывается только
   отсюда").
5. *(первопричина — нет guard rail'а)* — добавить import-linter контракт (или
   runtime-assert внутри `get_runtime()`/рядом), запрещающий вызывать
   `runtime.resume`/`aresume`/`.ainvoke` откуда-либо, кроме
   `RunWorkerJob.execute()`/её sandboxed-эквивалента — тест, который упадёт в
   CI, если завтра появится ещё один такой обходной путь, а не полагаться на
   то, что ревью его заметит.

### Открытия C и F — двойной `SandboxConnector.create()` / паразитный K8s Job

1. Почему `SandboxConnector.create()` может быть вызван дважды для одного
   `run_id`? Потому что порт `SandboxConnector` совмещал две ответственности —
   "разместить исполнение" (породить под/процесс) и "выдать credentials" — и
   обе роли исторически вызывались из одного и того же места.
2. Почему одна ответственность не была отделена от другой раньше? Потому что
   когда `SandboxConnector` только появился, `execute()` был единственным
   местом, где вообще что-либо создавалось — "создать sandbox" естественно
   означало "и породить, и выдать credentials" одновременно, разделять было
   незачем.
3. Почему это не разделили до того, как Phase 3 завела **второго** вызывающего
   "создать под" из другого слоя? Потому что дизайн `SandboxConnector`
   предшествует самой идее ExecutionBackend — до Phase 3 не было сценария, где
   размещение и credentials запрашиваются из разных мест.
4. Почему это не поймали тесты/ревью до того, как это вызвало реальный
   guard-exception/тихий паразитный Job? Потому что unit-тесты мокают
   `SandboxConnector`/`K8sSandboxConnector` как **один** объект в **одном**
   тестовом процессе — взаимодействие "второй `create()` из другого
   экземпляра в другом процессе" физически не может произойти в таком тесте.
5. Почему тестовый harness не моделирует "два независимых экземпляра одного
   класса-порта в двух процессах"? Потому что смоделировать настоящую
   multi-process семантику в pytest (реальный под/подпроцесс с собственным
   состоянием) — это отдельная, более тяжёлая инфраструктура тестирования,
   которую изначально не строили под этот класс багов.

**Решение на каждом уровне:**

1. *(двойной `create()` для одного `run_id`)* — уже сделано, Открытие F:
   `credentials_only`-флаг — под, уже созданный `K8sExecutionBackend`, не
   пытается создать второй Job, только минтит credentials.
2. *(одна ответственность не отделена от другой раньше)* — уже сделано,
   Открытие C, вариант (б): `ExecutionBackend` (Placement) и
   `_create_sandbox()`-internal-вызов (Credentials) теперь два явно разных
   вызывающих одного порта, а не один смешанный путь.
3. *(разделение не сделали до появления второго вызывающего)* — этот пункт сам
   по себе не требует отдельного фикса задним числом (второй вызывающий и
   есть Phase 3, который уже спроектирован с разделением) — но стоит явно
   задокументировать в самом `SandboxConnector`'е (докстринг порта), что это
   двухролевой порт по историческим причинам, и любой третий будущий
   вызывающий обязан явно решить, к какой из двух ролей он относится, прежде
   чем звать `create()`.
4. *(баг не поймали тесты/ревью до реального прогона)* — то же исправление,
   что и для Открытия H ниже (см. корень #4): тестовый harness должен уметь
   создавать **два независимых** экземпляра мокнутого
   `SandboxConnector`/`K8sSandboxConnector` в одном тесте и явно проверять,
   что второй вызов `create()` для того же `run_id` либо не происходит
   вообще (текущее решение), либо детектится явной ошибкой — а не полагаться
   только на живой K8s-guard, видимый лишь в реальном кластере.
5. *(первопричина — конфликт ролей в порту + harness не может проверить
   multi-process)* — обе части первопричины закрыты по существу: роли
   разделены (Открытия C/F), а harness — отдельно чинится через корень #4
   ниже. Дополнительных действий сверх уже сделанного не требуется.

### Открытия E и G — `JobStorePort`/`JobRecord` не хранит полный payload

1. Почему K8s-под/resume-job не может восстановить полный контекст `execute()`?
   Потому что `JobRecord` хранит только лёгкие метаданные статуса
   (`persona`/`tenant_id`/`correlation_id`/...), а не сам `WorkerJob.payload`/
   `budgeted`/`session_id`.
2. Почему `JobRecord` спроектирован только под метаданные? Потому что
   изначальное назначение `JobStorePort` — отслеживание статуса для
   polling/observability; единственный путь, которому был нужен полный
   payload — in-process backend, где payload и так лежит на стеке вызовов
   того же процесса, персистить его было незачем.
3. Почему схему не расширили, когда Phase 3 завела потребителя (под),
   которому нужно восстановить payload **без** общего стека вызовов с
   родителем? Потому что Phase 3.0 нашла однодневный обход (передать envelope
   через `JOB_PAYLOAD_JSON` env var / тело K8s Job) — сознательное, явно
   задокументированное сужение скоупа, а не недосмотр.
4. Почему выбрали env var, а не миграцию схемы в той же фазе? Потому что
   миграция — больший, отдельно ревьюable кусок работы, а payload сегодня
   спокойно помещается в лимиты K8s env — откладывать было прагматичным
   решением, пока лимит реально не мешает.
5. Почему тот же пробел всплыл повторно в Открытии G (resume), вместо того
   чтобы закрыться один раз для всех потребителей? Потому что Phase 3 и
   Phase 6 — разные вызывающие с разными узкими обходами одной и той же
   проблемы (env var passthrough для K8s vs. реконструкция минимального
   resume-payload из `pending_hitl`+`JobRecord`) — нет единого разделяемого
   примитива "восстанови полный контекст job'а по `job_id`", который оба
   потребителя могли бы переиспользовать.

**Решение на каждом уровне:**

1. *(под/resume-job не может восстановить контекст)* — уже сделано для своих
   фаз: Phase 3.0/3.1 передаёт envelope через `JOB_PAYLOAD_JSON` env var;
   Phase 6.1 строит `resume_job.payload` из `pending.tool_args`+минимальных
   полей `JobRecord`, минуя `_publish_and_finalize()`.
2. *(`JobRecord` спроектирован только под метаданные)* — задокументировать
   явно в докстринге `JobStorePort`/`JobRecord`, что это **известное**
   ограничение, а не недосмотр — со ссылкой на это Открытие, чтобы следующий
   разработчик не тратил время на повторное расследование "почему тут нет
   payload".
3. *(схему не расширили, когда появился второй потребитель)* — здесь и нужен
   настоящий фикс первопричины, а не документация: `JobRecord.payload: dict |
   None` + миграция — см. пункт 5.
4. *(env var выбрали вместо миграции в той же фазе)* — это было верным
   прагматичным решением **для той фазы** (payload помещается в лимиты K8s
   env) — фиксировать явно, что решение не пересматривается ради самого
   пересмотра; но завести отдельную, самостоятельную под-фазу на миграцию
   (не смешивать с Phase 3/6), чтобы не блокировать их же принятые сроки.
5. *(тот же пробел всплыл повторно в E и в G независимо)* — первопричина:
   `JobStorePort` спроектирован под "статус", не под "полный контекст".
   Настоящий фикс — `JobRecord.payload: dict | None` + метод порта
   `get_payload(job_id)`/аналог, с настоящей миграцией схемы, чтобы
   "восстанови контекст job'а по id" стало одним каноническим методом,
   переиспользуемым K8s-spawn, HITL-resume и любым будущим потребителем
   (включая future Rust/Go API), вместо того чтобы каждая новая фаза
   изобретала свой узкий обход заново.

### Открытие H (H.1/H.2) — оба бага пойманы только живой инфраструктурой

1. Почему реальные job'ы ломали JSON IPC-парсинг (H.1), а Docker-контейнер не
   мог достучаться до сети (H.2)? Прямые причины уже описаны в самом
   Открытии H (stdout как двойной канал; `docker run` без network/env).
2. Почему оба бага не поймал Phase 2/3 code review? Потому что фейковый child
   в тестах (`fake_sandboxed_job_child.py`) по конструкции печатает **ровно
   один** чистый JSON и никогда не резолвит реальные hostname'ы — тестовая
   фикстура сама по себе не может воспроизвести ни один из двух багов.
3. Почему фикстура не эмулирует реалистичное поведение (свои логи, реальную
   сеть)? Потому что она создавалась для узкой цели — "проверить контракт
   envelope-in/RunResult-out", а не "проверить, что child ведёт себя как
   настоящий процесс во всём остальном" — разумное сужение скоупа для
   unit-теста, но оно же и оставляет слепую зону.
4. Почему не было более широкого теста (integration/live-infra), который
   закрыл бы эту слепую зону? Потому что, по статусу этой же сессии, прогон
   против настоящей инфраструктуры был explicitly отложен до сегодняшнего дня
   — acceptance criteria Phase 1–4/6 были "unit-тесты зелёные", не "реальный
   job проходит end-to-end".
5. Почему acceptance criteria не включали живой прогон раньше? Потому что
   поднять docker-compose стек + реальный LLM-провайдер — дополнительная
   инфраструктура и время, которых не было в рамках "маленький diff на
   каждую под-фазу" (см. заявленный подход в начале документа) — размер diff'а
   намеренно приоритизировался над глубиной проверки на каждом шаге.

**Решение на каждом уровне:**

1. *(реальные job'ы ломали IPC/сеть)* — уже сделано: H.1 —
   `configure_logging(stream=sys.stderr)` в `cmd_run_sandboxed_job`; H.2 —
   `docker_network`/`docker_env_file` settings, прокинутые в
   `extra_run_args`.
2. *(оба бага не поймал code review)* — добавлено в этой сессии:
   `tests/observability/test_logging_setup.py` — прямой unit-тест на
   инвариант "`stream=` уводит вывод со stdout", без живой инфраструктуры,
   так что для H.1 конкретно ревью/CI теперь ловит регресс мгновенно.
3. *(фикстура не эмулирует реалистичное поведение)* — сделано: добавлен
   `mode == "noisy"` в `fake_sandboxed_job_child.py` (обе копии —
   `tests/workers/fixtures/` и
   `tests/infrastructure/fixtures/docker_backend_test_image/`), который сперва
   пишет пару правдоподобных JSON-лог-строк в stdout, затем финальный
   результат — плюс тест, документирующий, что `SubprocessExecutionBackend`
   **корректно классифицирует** такой вывод как
   `run_sandboxed_job_unparseable_output` (не крашится, не тихо теряет job) —
   это не "чинит" noisy-child (backend и не обязан парсить зашумлённый
   stdout — контракт "ровно один JSON" такой и остаётся), а превращает саму
   деградацию из невидимого руками-найденного бага в явно
   протестированный, named-и-locked-in контракт: если завтра что-то снова
   польётся в stdout настоящего child'а, результат будет предсказуемым
   "job failed with run_sandboxed_job_unparseable_output" — той же категорией
   ошибки, что и раньше, а не молчаливой порчей данных — без Docker и
   Postgres, за миллисекунды.
4. *(нет integration-теста, закрывающего слепую зону unit-тестов)* —
   формализовать это не как one-off сессию, а как повторяемую процедуру:
   `deploy/docker-compose.yml` (infra-only) уже поднимается одной командой;
   зафиксировать в этом документе минимальный ручной чек-лист "живой прогон
   перед merge крупной под-фазы Phase 2/3/6" (что поднять, какой job
   прогнать, что проверить в логах) — не полноценный CI-lane (это отдельная
   ops-задача), но воспроизводимый рецепт, а не разовое расследование.
5. *(первопричина — нет постоянного live-infra test lane)* — единственная
   причина, объясняющая **оба** бага H.1 и H.2 сразу (это не два независимых
   объяснения, а одно и то же на двух файлах). Полное закрытие первопричины —
   пункты 2–4 выше вместе: unit-тест на конкретный уже найденный инвариант,
   "шумная" фикстура на класс багов "child сам загрязняет stdout", и
   задокументированный воспроизводимый живой чек-лист на то, что фикстуры в
   принципе не могут покрыть (реальная сеть, реальный DNS, реальный LLM).

### Синтез: 4 системные первопричины вместо 9 отдельных

| # | Первопричина | Затронутые Открытия | Статус |
|---|---|---|---|
| 1 | Нет контракта "cross-process-видимое состояние живёт в shared store, не в module-level dict" | A, D (Dispatcher↔child, обойдено), **I (worker↔critic, закрыто в этой сессии)** | **Частично закрыто** — Открытие I доказывает паттерн (читать через существующий durable store — здесь `EngagementStateStore` — первым, process-local tracker как fallback); A/D для Dispatcher↔child остаются обойдены (см. выше), т.к. Phase 2.2a/2.2b уже устранили единственный практический failure mode для сегодняшних 3 backend'ов |
| 2 | Нет enforced-границы "исполнение агента только через Dispatcher/ExecutionBackend" | B (частично C) | **Закрыто в этой сессии** — `check_interfaces_api_no_runtime()` в `scripts/verify_import_boundaries.py` + `ALLOWLIST_INTERFACES_API_RUNTIME` (shrink-only, пусто) + тесты в `test_import_boundaries.py`/`test_layer_contracts.py` |
| 3 | Порт совмещает две ответственности (placement/credentials, status/full-context) | C, F (закрыто по-настоящему), E, G (обойдено) | **Частично закрыто** — C/F исправлены в первопричине, E/G ждут схемы `JobRecord.payload` |
| 4 | Нет постоянного live-infra test lane | H.1, H.2 | **Закрыто в этой сессии** — `test_logging_setup.py` (unit-тест на сам инвариант) + `noisy`-режим фикстуры и regression-тест на `SubprocessExecutionBackend` (см. ниже) |

Порядок исправления по первопричинам (не по алфавиту Открытий): начинать с
**#4** (дешевле всего, и без него любой следующий фикс по #1–#3 рискует снова
быть "проверен" только моками) → затем **#1** (Redis-backed tracker/budget —
самый фундаментальный архитектурный долг, влияет и на будущий Phase 7 warm
pool) → **#2** (architecture-тест, дёшево) → **#3** остаётся частично
задокументированным будущим шагом (миграция `JobRecord.payload`), не блокером
сегодня.

### Живой чек-лист перед merge крупной под-фазы (закрывает пункт 4 корня #4)

Не полноценный CI-lane (это отдельная ops-задача — поднять эфемерный
docker-compose стек в CI дороже, чем эта сессия успевает обосновать), а
воспроизводимый ручной рецепт, чтобы следующий раз "живой прогон" не был
разовым расследованием на всю ночь:

1. `docker compose -f deploy/docker-compose.yml up -d postgres redis` (infra
   only — не поднимать `docker-compose.dev.yml`, если не нужен UI).
2. `source deploy/.secrets/egregore-local.env` (реальный `DEEPSEEK_API_KEY`,
   или любой другой провайдер первым в приоритете `llm_api_key`).
3. Поднять API + один worker нативно (`uv run egregore serve` /
   `uv run egregore worker --daemon`) с `EXECUTION_BACKEND` по очереди
   `in_process` → `subprocess` → `docker` (для `docker` — предварительно
   `docker build` актуальный `egregore-worker:latest`).
4. Прогнать один настоящий SOC-триаж job через реальный event ingress (не
   через тестовый фейк) и убедиться: (а) job доходит до `COMPLETED`/finding
   опубликован, (б) в логах worker'а нет `run_sandboxed_job_unparseable_output`
   ни разу, (в) для `docker` backend'а — контейнер реально резолвит
   `postgres`/`redis` по имени (не падает на connection refused/DNS).
5. Только после этого — полный `USE_MEMORY_FALLBACK=true STAGE=test
   ./scripts/pytest_batches.sh` для финального подтверждения, что живой
   прогон не тянет за собой side effects, ломающие unit-тесты (см. Открытие
   H.3 — реальный секрет на диске однажды уже это делал).

---

## Статус на конец этой сессии

Реализовано и протестировано (полный batched suite, 29 batch'ей, зелёный на каждом
коммите): **Phase 1** (`ExecutionBackend` порт), **Phase 2** (`SubprocessExecutionBackend`,
Открытия A/D), **Phase 3** (`K8sExecutionBackend`/`DockerExecutionBackend`, Открытия C/E/F —
Docker verified реальным `docker run`, не только моком), **Phase 4** (опциональный
`runtimeClassName`/gVisor — settings-флаг, ноль изменения поведения при пустой
настройке), **Phase 6** (HITL resume теперь идёт через Dispatcher, Открытие B закрыто;
Открытие G задокументировано — 6.3 нужен живой прогон с Postgres-checkpointer'ом перед
production).

**Phase 5 и Phase 7 сознательно не реализованы** — не потому что пропущены, а потому
что сам план явно ставит обе в зависимость от 4.6 (замер cold-start latency runc vs
gVisor на реальном кластере), которого в этой среде нет и не может быть. Писать
код для Phase 5 (`runtime_class_override` per-persona) или Phase 7 (warm pool) без
этого замера означало бы гадать, а не решать по плану — сам план прямо требует
"решение, а не код" (5.1) и "явное решение зафиксировано" (7.1, acceptance). Когда
появится реальный кластер — сначала прогнать 4.6, потом по результату решить 5.1/7.1.

**Дополнительно (живая инфраструктура)**: поднят реальный локальный стек
(docker-compose postgres/redis + native `uv run egregore serve`/`worker` + собранный
`egregore-worker:latest` образ + реальный DeepSeek API) и через него прогнаны все три
уже реализованных backend'а (`in_process`, `subprocess`, `docker`) на настоящих
SOC-триаж джобах — не unit-тестами с фейковыми child'ами, а настоящим `docker run`/
`python -m interfaces.cli.main` с реальными LLM-вызовами. Нашлось и починено Открытие H
(stdout как IPC-канал ломался собственными логами child'а; Docker backend не мог
достучаться до сети/env). Все три backend'а подтверждены рабочими end-to-end
(engagement → planning → job → synthesis → закрытие) после фиксов.

**Ещё дополнительно (5 почему по всем Открытиям + фикс первопричин)**: каждое из
Открытий A–H прогнано через 5 вопросов "почему?" с решением на **каждом** уровне (не
только на самом глубоком) — 9 Открытий (после добавления I) свелись к 4 системным
первопричинам (см. "Синтез" выше). Из них реально исправлено в этой сессии:

- **Первопричина #4** (нет постоянного live-infra test lane) — закрыта: unit-тест на
  сам инвариант stdout/stderr-разделения (`tests/observability/test_logging_setup.py`),
  "шумный" режим фикстуры + regression-тест на `SubprocessExecutionBackend`, плюс
  задокументированный воспроизводимый живой чек-лист перед merge крупных под-фаз.
- **Первопричина #2** (нет enforced-границы "исполнение агента только через
  Dispatcher") — закрыта: `check_interfaces_api_no_runtime()` в
  `scripts/verify_import_boundaries.py` + shrink-only allowlist + тесты в
  `test_import_boundaries.py`/`test_layer_contracts.py` — падает в CI, если
  `interfaces/api` когда-либо снова попробует вызвать `cys_core.runtime` напрямую.
- **Первопричина #1** (process-local state вместо shared store) — найден и закрыт
  **конкретный, живой в проде экземпляр** (Открытие I: критик не видел evidence
  manifest'ы worker'а из-за process-locality) через `resolve_persona_manifest()`
  (читает `EngagementStateStore` первым, process-local tracker как fallback) — SOC
  grounding gate критика больше не тихий no-op в multi-container деплое. Сама
  process-locality `tool_execution_tracker`/`JobBudgetTracker` для пары Dispatcher↔child
  осталась как есть (Phase 2.2a/2.2b уже устранили единственный практический failure
  mode для сегодняшних 3 backend'ов) — полная Redis-миграция остаётся будущей работой,
  не блокером сейчас.
- **Первопричина #3** (порт совмещает две ответственности) — без изменений в этой
  сессии: C/F уже были закрыты по-настоящему в прошлой сессии, E/G ждут миграции схемы
  `JobRecord.payload` как самостоятельной под-фазы.

Тот же анализ применён к самым конкретным находкам родительского документа
[`MSP_BACKLOG.md`](MSP_BACKLOG.md) (§12 там): Reflexion
lessons без durability (§9.2.4 — тот же системный корень #1, что и A/D/I), и пять
находок из §11 (AuthN/AuthZ) — все три authz-переключателя выключены по умолчанию
(§11.2), пустой `organization_id` обходит tenant-проверку (§11.3), ReBAC не защищает
агента-исполнителя на Tool Gateway (§11.4), sandbox-токен минтится, но не проверяется
на Gateway (§11.5), нет санитизации на входной границе API (§11.7) — и риск "кто
уничтожает sandbox при краше Dispatcher'а" (§5). Эти шесть — задокументированы с
решением на каждом уровне 5 почему, но **не реализованы в этой сессии**: это
security-critical пути (authz-дефолты, ReBAC на Tool Gateway, credential-verification),
которые заслуживают отдельного, целенаправленного прохода с живой проверкой, а не
попутного патча внутри сессии, сфокусированной на ExecutionBackend-сплите.
