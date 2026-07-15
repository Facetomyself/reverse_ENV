# NAS 数据库服务清单

本文是 reverse_ENV 对 NAS `re-db` 栈的脱敏 canonical inventory。只记录服务、端口、状态与管理边界，不保存账号、密码或连接密钥。

## 事实来源

| 层 | Source of truth | 说明 |
|---|---|---|
| 部署拓扑 | `\\NAS\docker\re-db\docker-compose.yml` / `/volume1/docker/re-db/docker-compose.yml` | 服务、镜像、profile、端口与数据卷 |
| 数据库凭据 | NAS `/volume1/docker/re-db/.env` | 服务账号与密码；不得复制到仓库、skill、提示词或日志 |
| NAS 运维凭据 | `%USERPROFILE%\.nas\credentials.json` | DSM / SSH 登录；本机私密文件，仅当前用户可读 |
| 本地部署凭据副本 | `%USERPROFILE%\.nas\re-db.env` | 可选部署副本；本机私密文件，仅当前用户可读 |
| DBX 连接登记 | `%APPDATA%\com.dbx.app\dbx.db` | DBX / DBX MCP 实际可见的连接，不等同于 NAS 服务全集 |
| 操作入口 | `%USERPROFILE%\.claude\skills\nas\`、`%USERPROFILE%\.codex\skills\nas\` | Claude / Codex 同步 NAS skill |

## 服务清单

| 服务 | 镜像 | Profile | NAS 端口 | 2026-07-15 状态 | DBX 登记 |
|---|---|---|---:|---|---|
| PostgreSQL | `postgres:16-alpine` | `core` / `full` | 5433 | `re-postgres` running | `nas-re-db-postgres` / `re_db` |
| Redis | `redis:7-alpine` | `core` / `full` | 6379 | `re-redis` running；DBX `PING` 通过 | `nas-re-db-redis` / DB `0` |
| MinIO | `minio/minio:latest` | `core` / `full` | 9000 / 9001 | `re-minio` running | 对象存储，不走 DBX 数据库连接 |
| Elasticsearch | `elasticsearch:8.17.4` | `search` / `full` | 9200 | 当前未运行 | `nas-re-db-elasticsearch` |
| MongoDB | `mongo:4.4` | `doc` / `full` | 27017 | `re-mongodb` running；容器原生 `ping` 通过；DBX bridge 待桌面端完整重启 | `nas-re-db-mongodb` / auth DB `admin` |
| MariaDB | `mariadb:11` | `sql` / `full` | 3306 | 当前未运行 | `nas-re-db-mariadb` / `re_db` |

> DS920+ 的 Intel J4125 不支持 MongoDB 5.0+ 所需 AVX，部署固定使用 MongoDB 4.4。

## Profile 语义

- `core`：PostgreSQL + Redis + MinIO，日常常驻。
- `search`：Elasticsearch，按需启动。
- `doc`：MongoDB，按需启动；当前实例处于运行状态。
- `sql`：MariaDB，按需启动。
- `full`：启动全部六个服务。

## DBX 与 NAS 的边界

- NAS 当前维护六个服务；DBX 已登记除 MinIO 外的五个数据库/数据服务。
- DBX 连接名固定为 `nas-re-db-postgres`、`nas-re-db-redis`、`nas-re-db-mongodb`、`nas-re-db-mariadb`、`nas-re-db-elasticsearch`。
- Claude / Codex 的 DBX MCP 均允许常规写 SQL：`DBX_MCP_ALLOW_WRITES=1`。
- 危险 SQL 保持关闭：`DBX_MCP_ALLOW_DANGEROUS_SQL=0`。
- PostgreSQL、MariaDB/MySQL、Redis 可由 MCP 直接连接；MongoDB、Elasticsearch 使用 DBX desktop bridge。本次热刷新未加载新 connection ID，需完整重启 DBX 桌面端。
- MariaDB、Elasticsearch 的连接已登记，但对应 NAS profile 当前未启动；使用前先通过 `nas` skill 启动并复核状态。
- NAS `.env` 值不得写入项目配置、skill、提示词或日志。

## 同步与验证

1. Compose 服务、镜像、profile 或端口变更时，先更新本文。
2. 同步更新 Claude / Codex `nas` skill 的 `references/re-db-inventory.md`。
3. DBX 新增或删除连接时，更新“DBX 登记”列以及 `CLAUDE.md` / `AGENTS.md` 的 DBX 约束。
4. 运行状态属于时间点快照；使用前通过 `nas_db.py status` 或 NAS Container Manager 复核。
5. 提交前扫描仓库与两个 skill，确认不存在 `.env`、密码值、token 或私钥。
