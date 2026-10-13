# Update2Report 第 2 轮交付报告

交付日期：2026-10-13。七项要求已实现并验证；未部署 Spaces。26 个测试通过，最终三份样例已真实调用，九个项目完成数逐项一致。后台启动后 curl 首页返回 200，应用进程已关闭。

## 约束、假设与边界

- 使用 UTF-8 读取了指定 plan.md，未读取禁止目录，未复制其他项目代码。样例、缓存和调试输入均为虚构 Northwind Studio 数据。
- 沿用进程环境的 `LLM_BASE_URL / LLM_API_KEY / LLM_MODEL`，模型 ID 为 `workbuddy-deepseek-v4.1-flash`。未输出或提交密钥。实际底层模型权重不在本次验证范围内。
- 样例报告日期固定为 2026-10-13。应用实时报告默认服务器本地日期，云端时区不保证为 Asia/Shanghai。`by Fri / tomorrow` 等相对日期保留原文，不猜日期。
- 每会话限五次解释为五次实时尝试，模型失败也计数；空输入和超长输入在模型调用前拦截，不扣额度。新 Gradio 会话会重置次数。
- 8000 字符按 Python 字符数计算，包含文字与解码后的 CSV；上传文件另限 32 KB。

## 修复与加固结果

1. **统计与正文统一。** 根因是旧统计只累加 CSV 完成状态，漏掉抽取出的 done。现在合并两类完成项，按项目/任务名去重，记录每项来源。HTML 脚注与 Counted completions、Excel Summary 均展示口径及证据。增加文字已完成而 CSV 缺失/未完成、重复提及、CSV 重复、跨项目同名的回归测试。
2. **三份杂乱样例。** 每份六人均发言，包含中英混写、实际错字（标千、pagnation）、一人多消息、跨人重复事项、等待客户的隐含阻塞及相对日期。最终 No update 均为 0；internal 和 client-facing 两种摘要都由真实调用生成并缓存。
3. **UTF-8。** 旧 HTML 和缓存没有 U+FFFD，不能确认旧截图乱码来自文件内容，查看端解码是可能原因。输出统一 UTF-8，HTML 明确 meta charset，分隔符使用 `&middot; / &mdash;`。中文往返测试通过，最终三份 HTML 无替换字符。
4. **报告补全。** 本文件已覆盖旧稿，全部字段写完；末尾八条验收清单另有任务指定位置的中文版 acceptance.md。
5. **LLM 恢复。** SDK timeout = 45 秒，传输重试一次；模拟超时验证了两次请求后安全退出。坏 JSON/schema 修正一次仍失败时返回友好消息。完整 Markdown 代码块中的合法 JSON 可解析，内容仍严格校验。界面错误不会终止应用，也不展示提供方异常详情。
6. **限额与缓存。** 服务端验证输入长度，生成回调串行执行，会话 State 限五次。缓存匹配文字、CSV 内容及版本；编辑任一输入即实时生成。未编辑样例两个语气都不调用模型；实时生成不写缓存。导出采用独立目录，避免并发覆盖。
7. **Spaces 准备。** README 顶部 YAML 指定 Gradio SDK、5.50.0、Python 3.11 和 app.py。SPACE_ID 环境下监听 0.0.0.0:7860，本机仍为 127.0.0.1:7860。本地 .env 不覆盖进程变量。README 明确 LLM_API_KEY 为 Secret，LLM_BASE_URL 与 LLM_MODEL 为 Variable 或 Secret，并说明云端不能访问本机代理。未部署。

## 完成数与去重口径

完成数 = 抽取的 done 项 + CSV 状态属于 `done / complete / completed / closed / 已完成 / 完成` 的任务，在项目内按规范化任务名取并集。

任务名规范化使用 Unicode NFKC、大小写折叠、去空白和标点、去可选项目名前缀。不同负责人可以指同一项，不同项目同名分开计数。提示要求抽取时采用 CSV 原任务名，并将重复中英表达归为同一名称；未匹配的不同措辞不会模糊合并，可能需要人工归并。mostly done 不计完成。

文字完成而 CSV 滞后时计入完成，从逾期项排除，并在 Risks 中保留 `CSV status needs reconciliation`，不修改原 CSV。成文和缓存摘要禁止数字及英文数词，防止另一个项目的数字误通过旧全局校验。数字只由 Python 给出。

## 最终真实样例运行

命令为 `python scripts/refresh_samples.py`，显式绕过缓存，逐份抽取、生成两种语气、更新缓存并导出 HTML/Excel。耗时涵盖整条链路；tokens 为 API usage 的 total_tokens，不是估算或费用。

| 样例 | 耗时（秒） | API tokens | 六人覆盖 | Atlas / Beacon / Cedar |
|---|---:|---:|---|---|
| sample-1 | 11.710 | 5310 | 全部有更新 | 3 / 2 / 3 |
| sample-2 | 8.208 | 3455 | 全部有更新 | 2 / 2 / 2 |
| sample-3 | 8.220 | 3755 | 全部有更新 | 2 / 2 / 3 |
| 最终合计 | 28.138 | 12520 | No update 均为 0 | 21 个项目完成项 |

可提交原始记录为 `samples/cache/round2-live-metrics.json`，含模型、日期、摘要、统计、预期/实际完成数、耗时和 tokens。产物为 `out/sample-1_weekly_report.html/.xlsx` 至 `out/sample-3_weekly_report.html/.xlsx`。out 被 Git 忽略；样例、缓存及指标记录已提交。

最终表不含调试复跑消耗。中间记录保存在 out 的 round2-initial、second、failed、fourth、fifth-live-metrics 和两份 diagnosis-metrics 中。曾有 Markdown 外壳造成解析失败（3065 tokens），以及一次统计/发言覆盖门禁未通过（1104 tokens，诊断复跑未复现）。失败结果没有替换对应缓存。最终仅采用后续真实复跑及人工核对通过的结果。

## HTML 正文与快照逐项对照

以下名称同时出现在最终摘要及完成证据中，数字对应 Project snapshot。正文未把待办当完成，CSV-only 的 archived migration 也在正文中；已完成项没有再写为逾期。

| 样例 | 项目 | 正文完成事项 | 证据条数 | Completed | 结论 |
|---|---|---|---:|---:|---|
| 1 | Atlas | capacity review；landing page；QA checklist | 3 | 3 | 一致 |
| 1 | Beacon | release notes review；email copy | 2 | 2 | 一致 |
| 1 | Cedar | dashboard draft；export button；documentation review | 3 | 3 | 一致 |
| 2 | Atlas | prototype；accessibility pass | 2 | 2 | 一致 |
| 2 | Beacon | API guide；webhook tests | 2 | 2 | 一致 |
| 2 | Cedar | dashboard filters；data dictionary | 2 | 2 | 一致 |
| 3 | Atlas | release checklist；deployment notes | 2 | 2 | 一致 |
| 3 | Beacon | smoke tests；support FAQ | 2 | 2 | 一致 |
| 3 | Cedar | chart labels；archived migration（CSV）；billing export | 3 | 3 | 一致 |

## 验证证据

- `python -m pytest -q` → **26 passed, 2 warnings in 9.89s**，由原 7 个增至 26 个。覆盖统计与冲突、UTF-8、坏 JSON、代码块、实际 SDK 超时重试、跨项目数字、限额、输入大小、CSV 缓存失配、样例回调、Spaces host、三份双语气离线样例。
- `python scripts/check_reports.py` → **PASS: 9 project counts, UTF-8, six speakers, both tones offline.** 打印摘要及完成清单供逐句人工核对。离线测试禁止构造模型，缓存前后字节不变。
- `python scripts/smoke_app.py` → **http_status = 200, process_stopped = true**。后台启动 python app.py，实际 curl 首页并核对标题；finally 只关闭脚本创建的进程。原始记录为 `out/round2-startup.json`。
- `git diff --check` 与 staged diff 检查无空白错误。检查了配置密钥不在受 Git 跟踪文件中，.env 未跟踪；未打印密钥。

## 本轮提交

| 提交 | 英文 commit message |
|---|---|
| ce1c084 | fix: reconcile text and CSV completions with auditable deduplication |
| e141057 | test: verify UTF-8 reports preserve multilingual text and separators |
| 36c8bc0 | fix: bound model retries and return safe extraction errors |
| 30be0cd | feat: enforce session quotas and input-bound offline sample caching |
| 684d101 | chore: prepare pinned Gradio Spaces configuration and secret setup |
| a5c1b47 | fix: prevent cross-project numeric claims in generated summaries |
| 81906cd | fix: accept fenced JSON and keep summary evidence within each project |
| b8164ee | fix: separate stale CSV statuses from unfinished overdue work |
| 1cba57a | feat: refresh messy fictional samples with measured live caches and verification tools |

本报告与验收清单在最后的文档提交中收尾，其 ID 见 `git log -1 --oneline`。

## 尚未验证与限制

- Spaces 未实际云端构建、部署或测试 DeepSeek 官方 API。当前验证环境是 Windows / PowerShell 5.1 / Python 3.12，Spaces 的 Python 3.11 未云端实测。
- 新会话可绕过限额，这不是按账号或 IP 的全面防刷。45 秒是请求超时设置，修正与重试会增加完整链路等待时间。
- 数字与来源可审计，但抽取语义仍依赖模型。任意真实输入仍需使用者审核；不同措辞的未匹配任务可能被保守地分别计数。
- 首页用 curl 验证，未自动执行浏览器逐按钮验收。回调与限额经过 pytest，真实浏览器交互由下面清单确认。
- 两条警告是 Gradio 5.50.0 对 api_name=False 的未来弃用提示，不是失败，依赖已固定。未实现上传/导出文件定期清理，公共 demo 只应使用虚构数据。

## 验收清单

[ ] PowerShell 执行 `Set-Location C:\soft\work_collab\hackathon\update2report`、`python -m pip install -r requirements.txt`、`python app.py` → 显示服务启动并保持窗口运行；实时生成沿用已配置的三个 LLM 环境变量。

[ ] 浏览器打开 `http://127.0.0.1:7860` → 看到 Update2Report、Sample、Load sample、Tone、Generate report，页面正常显示。

[ ] 依次选择 sample-1/2/3，点击 Load sample，再分别用 internal 和 client-facing 点击 Generate report → 六人都有更新，出现 HTML/Excel 下载；两个语气均走缓存，不占实时额度。

[ ] 下载并打开三份 HTML，检查正文、Project snapshot、Counted completions 与脚注 → Atlas/Beacon/Cedar 分别为 3/2/3、2/2/2、2/2/3；逐项名称与上表相同，无乱码或完成/逾期矛盾。

[ ] 下载并用 Excel 打开任一样例工作簿 → 有 Summary、Details、Risks 三个 sheet，完成数与 HTML 相同，Risks 单列 CSV status needs reconciliation。

[ ] 新浏览器会话清空 CSV，粘贴虚构文字 `Mira [Atlas]: QA checklist done; next mobile polish by Fri.`，连续生成五次后点第六次，再加载样例生成 → 第六次提示 Session limit，未编辑样例仍可生成。

[ ] 新 PowerShell 执行 `Set-Clipboard ('x' * 8001)`，清空页面 CSV 后粘贴到 Team updates 并点 Generate report → 显示 8000 characters 输入限制，不调用模型。

[ ] 启动窗口先按 Ctrl+C，再执行 `python -m pytest -q`、`python scripts/check_reports.py`、`python scripts/smoke_app.py` → 26 passed、九项目核对 PASS，最后输出 http_status 200 和 process_stopped true。
