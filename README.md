# 保研监督系统

这是一个仅供个人使用的保研监督系统初始化工具。数据、移动端录入、提醒和仪表盘均依赖飞书多维表格与飞书移动端；本仓库只负责 OpenAPI 结构管理、Seed 数据、进度算法和幂等同步，不包含账号系统、数据库或独立 Web 后端。

## 当前架构

```text
飞书移动端 / 多维表格
          │
          ├─ 6 张核心数据表、命名视图、自动化、仪表盘
          │
Python CLI ├─ OpenAPI 初始化与幂等补齐
          ├─ 配置化生成今天与未来2天任务
          └─ 进度、速度、预计完成日、风险计算与回写
GitHub Actions ── 每小时执行一次 Daily Job
```

## 目录结构

```text
src/baoyan_tracker/
  config.py            安全 env 读取与兼容别名
  feishu_client.py      tenant token 内存缓存与统一请求
  bitable_service.py    表、字段、视图、记录操作
  schema.py             6 张表及 Seed 声明
  bootstrap.py          幂等初始化
  progress_engine.py    透明可解释的进度算法
  sync.py               打卡→任务→目标→里程碑→周复盘全量重算
  business_time.py      Asia/Shanghai 业务时间
  task_generator.py     配置化、幂等任务生成
scripts/
  test_feishu_connection.py
  test_bitable_connection.py
  bootstrap_feishu.py
  inspect_feishu.py
  sync_progress.py
  generate_daily_tasks.py
  daily_job.py
config/task_rules.json  固定学习规则
.github/workflows/      GitHub Actions 无人值守调度
tests/                  默认不访问网络的单元测试
docs/                   飞书端配置与算法说明
```

## 安装

需要 Python 3.11 或更高版本：

```powershell
python -m pip install -e ".[dev]"
python -m pytest
```

## 环境变量

复制 `ID.env.example` 为同目录下的 `ID.env`，至少配置：

```dotenv
FEISHU_APP_ID=cli_your_app_id
FEISHU_APP_SECRET=your_app_secret
```

也兼容 `APP_ID` / `APP_SECRET` 和 `LARK_APP_ID` / `LARK_APP_SECRET`。已有多维表格可配置 `FEISHU_BITABLE_URL`、`FEISHU_APP_TOKEN`、`FEISHU_BASE_TOKEN` 或 `BITABLE_APP_TOKEN`。如果未配置目标表格，写权限测试或 `--apply` 会创建“保研监督系统”，并把 app token 写入本地已忽略的真实 env 文件。

业务时间统一由 `BUSINESS_TIMEZONE` 控制，默认值为 `Asia/Shanghai`。GitHub runner 即使使用 UTC，也会按上海日期生成任务和归属打卡。

## 使用

先验证身份，不会输出 token：

```powershell
python scripts/test_feishu_connection.py
```

已有 Bitable 时验证读写；没有时允许创建：

```powershell
python scripts/test_bitable_connection.py
python scripts/test_bitable_connection.py --create-if-missing
```

先预览、再初始化：

```powershell
python scripts/bootstrap_feishu.py --dry-run
python scripts/bootstrap_feishu.py --apply
python scripts/bootstrap_feishu.py --dry-run
```

重新同步进度计算字段：

```powershell
python scripts/sync_progress.py --dry-run
python scripts/sync_progress.py --apply
```

预览或生成固定任务：

```powershell
python scripts/generate_daily_tasks.py --today --dry-run
python scripts/generate_daily_tasks.py --days 7 --apply
python scripts/generate_daily_tasks.py --date 2026-09-01 --apply
```

默认不指定日期参数时生成今天和未来 2 天。已有任务不覆盖；只有显式增加 `--force` 才按当前规则重写计划量、预计时间、备注等系统计划字段。规则位于 `config/task_rules.json`。

统一日常入口：

```powershell
python scripts/daily_job.py --dry-run
python scripts/daily_job.py --apply
```

执行顺序为固定任务生成、全量进度同步、周复盘更新。整个过程幂等。

查看非敏感结构摘要：

```powershell
python scripts/inspect_feishu.py
```

重复执行 bootstrap 或 sync 都会先读取现状，只补缺失结构或更新发生变化的值。

同步以 `04_打卡记录` 为唯一行为事实源，不执行 `当前值 += 新值`。修改或删除打卡后再次同步，会从全部剩余打卡重新计算每日任务、长期目标、速度、预计完成日期、风险和周复盘，因此不会重复计数。

手机快速打卡只需填写类别和数量或投入分钟，内容可选。创建时间、日期、单位、所属目标，以及“日期+类别”唯一时的所属任务由同步自动推断。

## 每天怎么用

早上：看今日任务

学习后：手机快速打卡

晚上：看未完成与进度

日常不需要运行 Python 命令。

## GitHub Actions 配置

工作流 `.github/workflows/feishu-sync.yml` 支持手动执行和每小时一次的定时执行。GitHub 定时工作流使用 cron，调度可能有少量平台延迟；业务日期始终由代码转换到 `Asia/Shanghai`。参考 [GitHub Actions workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)。

进入 **GitHub Repository → Settings → Secrets and variables → Actions**，新增以下 Repository secrets：

- `FEISHU_APP_ID`
- `FEISHU_APP_SECRET`
- `FEISHU_APP_TOKEN`

`FEISHU_BASE_TOKEN` 只是本地兼容别名，当前 Actions 工作流不需要配置。保存后进入 **Actions → Feishu Sync → Run workflow** 做第一次线上验收。工作流、README 和日志都不保存或打印实际 secret/token。

## 安全

- `tenant_access_token` 只在进程内缓存，过期前自动刷新，不写文件、不打印。
- App ID、App Secret 和真实 env 文件不会写进日志或 Git。
- `.gitignore` 忽略 `.env`、`.env.*`、`ID.env`、`*.env`，但放行 `*.env.example`。
- 不要把实际凭据复制到 README、issue、终端命令或提交历史。

## 飞书端仍需手工配置

命名视图已由 API 创建，但视图筛选、自动化和仪表盘需要在飞书界面完成：

- [数据结构与视图](docs/FEISHU_SCHEMA.md)
- [自动化步骤](docs/FEISHU_AUTOMATIONS.md)
- [手机快速打卡](docs/FEISHU_MOBILE.md)
- [仪表盘设计](docs/FEISHU_DASHBOARD.md)
- [进度算法](docs/PROGRESS_ENGINE.md)
