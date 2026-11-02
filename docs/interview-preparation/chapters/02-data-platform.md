# 02 数据工程平台：从元数据模型到身份、注册与 Agent

私人学习材料，2026-11-02。对应面试稿第 11—14 页。依据本地 `data_infra_platform` 快照 `36ffaff8`、主计划及实际函数体；只解释实现和设计，不包含服务地址、凭证、员工编号或业务规模。

状态标签含义：【已实现】有本地代码或提交依据；【理论/复现】报告模型或独立验证；【通用知识】用于解释原理；【改进建议】尚不能表述为交付成果。

## 1. 先建立项目地图，避免一上来背技术名

【已实现】团队项目是数据工程平台，用户包括数据工程师、产线开发者和资产治理人员。整体涉及资产接入、产线版本、生产任务、Runtime 执行、元数据管理与统一门户。DataHub 是其中的开源元数据底座，提供实体、属性、搜索、Schema 和血缘；它不是整个数据工程平台。

我的工作集中在元数据与治理：Python 的 Extensions API/注册 SDK；Java GMS 的企业身份、准入、角色与凭证；Play 服务端的会话和代理衔接；React/TypeScript 的资产、权限和注册页面；Data Agent 的工具交互。任务执行、制品版本等消费我的接口，不代表这些模块全部由我开发。

可以用一分钟讲清：

> 数据工程平台要回答“什么数据，用哪版产线，由谁执行，得到什么结果”。团队负责完整生产流程，我重点建设元数据接入和治理。基于 DataHub，我把注册逻辑拆成可复用 SDK 与 API，接入企业身份和领域权限，并打通前端与元数据 Agent。技术难点是让身份、实体约束、写入和查询语义跨 Python、Java 与前端保持一致。

【通用知识】把项目理解成四个域更容易深挖：身份域回答“谁”；治理域回答“可做什么”；资产域回答“操作什么对象”；生产域回答“如何执行并回写”。SSO 解决身份，RBAC/领域策略解决授权，二者不能互相替代。

## 2. 必须解释准确的六个元数据概念

【已实现】Entity 是一个可独立标识的对象，如数据集、产线和任务。Aspect 是围绕实体的一组结构化属性，例如注册信息、Schema、归属或运行属性。实体不是把所有字段塞在一个无边界 JSON；Aspect 允许分域维护和演进，但多个 Aspect 的更新不天然形成一个整体事务。

URN 是实体身份。稳定的同一身份让重复上报、查询和血缘引用指向同一对象。数据集名称、平台和环境可能参与 URN。本SDK的Task映射为DataJob，URN包含所属DataFlow与name；run_id是独立属性，不自动进入URN，也不是必填身份字段。不能只靠显示名判定两个实体相同，也不能在改名时忽略旧引用。构造规则由 `MetadataEntity.build_urn()` 和类型定义落实。

这里有两个不同的 MCP：

| 缩写 | 在哪里出现 | 实际含义 |
| --- | --- | --- |
| Metadata Change Proposal | 注册 SDK 的 `build_mcp_list()` | 提议修改一个实体的某个 Aspect 的元数据事件。 |
| Model Context Protocol | Agent 工具生态与工具适配命名 | 模型接入工具/资源的一类协议；与元数据变更提案不是一回事。 |

【已实现】本项目 Agent 代码有本地工具注册表和 `MCPToolAdapter`。不能凭类名就声称已经运行完整远程协议服务，必须继续检查调用链和传输。Emitter 是元数据写入适配；GraphQL 是服务查询接口；Elasticsearch/ES 是搜索索引。GraphQL 不是数据库，“走 GraphQL”也不是强一致性的通用保证，要看具体 resolver 读取什么。

## 3. 沿一条注册请求掌握真实实现

【已实现】HTTP 路由解析身份和请求，也可以在可信进程中直接使用 SDK。核心链路如下：

1. `register()` 校验实体类型，解析 YAML/字典并合并参数，迁移旧字段。
2. 从可信 actor 或凭证反查主体，覆盖用户填写的 creator。不能允许调用者把自己写成另一个注册者。
3. 根据 SDK/REST 调用模式执行权限检查；“API 先查过”是明确的信任边界，不是所有直接调用默认安全。
4. `MetadataEntity.from_dict()` 形成实体，构造 URN，填充时间戳，检查字段与 Aspect；注册路径还校验 Domain。
5. 按 URN 获取进程内注册锁，在锁内再做存在性判断。已有对象且不覆盖时返回 skipped；任务按配置检查产线、输入等依赖。
6. 构造多个 Metadata Change Proposal，经 Emitter 发布；发布失败返回明确错误。
7. `_poll_verification()` 使用 GraphQL 的 `exists_by_urn()` 轮询存在性。超时会出现“发送已完成，但验证超时”，不能当作确定没有写入。

实体层主要做建模和纯计算，服务层编排，数据访问层承担查询，发布层承担写入。原因是 URN、校验和 MCP 构造可独立测试；替换发布通道或客户端时不必重写实体规则。替代方案是集中在一个大服务类，早期开发快，但连接、权限、序列化和业务规则会相互牵连。

【通用知识】幂等、互斥和事务分别回答“重复请求结果是否可控”“并发能否同时进入”“一组修改能否原子提交”。当前按 URN 的 `threading.Lock` 只能协调同一 Python 进程；多 worker、多副本各有锁。引用计数回收锁表可避免不同 URN 越积越多，但不解决分布式竞争。

【改进建议】真正跨副本的创建唯一性应考虑服务端约束、版本条件更新、请求幂等键或带 fencing 的协调；不能只加 Redis 锁就宣称 exactly-once。进程崩溃发生在部分 Aspect 已写后，重试可能覆盖或补齐，也可能看到部分状态，需要依据写入协议分析。

## 4. 查询一致性与修改约束

【已实现】SDK 通过搜索发现候选实体，通过已知 URN 的 GraphQL 精确获取和检查存在。搜索索引异步更新，所以“刚注册、能精确读、搜索暂时没有”并不矛盾。当前验证轮询检查存在，不证明所有字段都达到预期版本，更不证明所有搜索条件都可检索。

`amend()` 先精确定位对象，再对当前所属域检查修改权限，按 merge/overwrite/append/replace 等策略合并。creator、注册身份及类型相关不可变字段要单独保护；只保护页面控件挡不住 API 请求。先查旧对象也避免调用者通过篡改请求中的 Domain 把授权判断移到另一个域。

【通用知识】列表 append 重试可能产生重复，merge 去重也不等于任意复杂对象幂等；需要知道去重键和覆盖规则。超时后的重试应先以同一 URN 查询，而不是生成新名字重复创建。替代方案是异步提交后返回任务 ID，但这需要提交状态查询和用户反馈设计。

## 5. 登录、凭证与授权跨三层衔接

【已实现】GMS 是服务端元数据和授权能力的重要承载处。企业 SSO 接入验证外部身份，再做准入与用户供给；角色策略决定操作权。准入名单是“能否进入”的粗门槛，Publisher/Editor 等角色和领域策略是“进入后能做什么”。React 的按钮显隐只优化体验，最终判断必须在服务端。

Play frontend 是 Java 服务端，不等于 React 浏览器代码。它处理登录回调、平台会话、后端代理和凭证衔接；React 调用对应接口展示授权、注册、凭证等页面。`NeverTokenManager` 为用户供给长效 PAT，在代理层注入，失败时可回退会话 token。它用每用户锁和二次检查减少同进程重复发放，读取实时 Aspect 而非依赖可能延迟的搜索列表。

GMS 的 secret Aspect 通过 SecretService 加密存储可再次取用的凭证，并校验调用者为本人或具备凭证管理权限。面试要区分加密保存、凭证哈希、访问授权和撤销：它们处理不同风险；加密不意味着管理员无条件取用，也不意味着已有客户端缓存立刻失效。

### 用虚构用户“小林”串起凭证与 actor

【已实现】以下示例假设启用扩展 API 的 DataHub 权限模式，经 Play 代理访问 Chat，不使用简单共享 Token 放行，也不使用关闭鉴权的可信模式。小林只是虚构用户；名称不是凭证。若走同源反向代理直达扩展 API，应另查其头与 token 的转发配置，不能默认经过同一个 Play 方法。

| 一跳或阶段 | 携带与校验什么 | actor、权限与边界 |
| --- | --- | --- |
| 登录结果到浏览器 | 企业认证链确认小林身份；Play 登录流程接收 GMS 访问 token，建立含 actor/token 的平台 session。 | 浏览器 session 的存在，不证明其中 GMS token 此刻仍有效。 |
| 浏览器访问 Play | Play 框架解析 session；`Authenticator` 按配置检查可转发资格，包括 Cookie/actor 一致性或 Authorization 头存在。 | 启用 GMS 认证时，这里不是最终 token 验签点；`AuthUtils` 明确将 token 有效性留给下游 GMS。React 不产生权威身份。 |
| Play 获取或选择凭证 | `NeverTokenManager` 用小林自己的 GMS session token 读写其 PAT；GMS 检查对应操作权。代理优先小林 PAT，回退 session token，无 session 时才透传原 Authorization。 | 不是 Play 拿管理员身份替小林无条件发放凭证。代理剔除客户端 actor 头，再从服务端 session 写入 actor 头；不能把任意来源的同名头视为可信。 |
| 扩展 API 解析登录身份 | `require_login_with_actor()` 提取 Authorization，权限客户端用该 token 向 GMS 查询本人身份和权限，可利用权限缓存。 | Python 以 token 反查结果中的 username 为首选 actor；该值再用于 creator。成功登录只说明身份解析通过，不等于具有注册权。 |
| Chat 到注册工具 | 路由计算 `can_register`：global 模式看全局角色，domain 模式看是否存在可编辑域；工具在 False 时拒绝，并把 actor 传给注册服务。 | 这是注册动作门禁，不能直接推导对任意目标域有写权限。actor 是操作主体信息，不会自动把下游调用切成小林的凭证。目标域约束仍需沿具体注册路径核查。 |
| 适配器访问 GMS | `MCPToolAdapter` 的 SDK/GraphQL 客户端使用其初始化 token；注册使用注入的 MetadataService 或适配器 token 创建的服务。 | 下游 GMS 按实际携带的 token 判权。因此 API 确认了小林身份，仍不证明工具的每次数据读取都以小林权限执行；读工具逐用户可见性尚待验证。 |

【通用知识】session、PAT、actor 和 `can_register` 分别是会话/凭证、可用于 API 的访问凭证、主体标识和动作判定结果，不能互相充当。这里的“API/PAT”是扩展 API 接受的 DataHub 访问凭证，不是模型网关的 LiteLLM API key。上述依据分别在 `Authenticator`/`AuthUtils`、`Application.proxy()`/`getAuthorizationHeaderValueToProxy()`、权限依赖、Chat 路由和 `MCPToolAdapter`；不要仅根据变量叫 user 就判断实际用了用户权限。
【改进建议】长效凭证适合减少调用衔接摩擦，同时需要轮换、撤销、最小权限与缓存失效策略。不能把已实现的便利性说成完备的密钥治理。若被问多副本供给，承认本地锁范围，并进一步讨论后端唯一约束或创建冲突处理。

## 6. Data Agent 的读写权限边界

【已实现】当前 Chat 路由使用 `require_login_with_actor()` 登录依赖；旧 docstring 中“chat 不设鉴权门禁”的描述不能覆盖当前函数体。路由解析 actor 与 can_register，再传到工具适配器；注册工具无权时拒绝，身份解析失败时关闭注册能力。搜索、实体、血缘、Schema、Profile 与注册使用不同工具，返回实体链接供用户检查。

【已实现】会话历史当前保存在服务进程的字典中。不能把随机 session_id 当作已证明的用户隔离，也不能宣传多副本共享持久历史。读工具的逐用户数据可见性，要追踪实际传给下游的 token 与策略，不能只看 Chat 已登录就断言完成。

【通用知识】语言模型做工具选择不具有授权权威；工具参数也属于不可信输入。元数据描述中的指令不应扩大工具权限。【改进建议】逐用户 token/受控委托、工具 allowlist、资源级授权、会话所有权绑定、结果审计都可继续补强，应说“我会如何做”，不要说“项目已经全部具备”。

## 7. 十组分级深挖问答

### Q1【基础】你做的是 DataHub 还是数据工程平台？

答：团队做完整平台，我基于 DataHub 负责元数据接入、治理和交互。上游模型、搜索与血缘能力是基础，我实现企业适配与注册框架。

第一层追问：为什么不从零写？答：复用成熟元数据模型与生态，把精力放在平台差异和接入契约。

第二层追问：如何避免深度 fork？答：扩展 API/SDK 尽量独立；必须修改的身份、角色和前端接入保持清晰补丁边界。不能声称已做到完全无侵入。

### Q2【基础】Entity、Aspect 和 URN 如何协作？

答：URN 标识对象，Aspect 表达对象某一方面的属性，Entity 组织这些属性。注册把属性转换成针对该身份的变更提案。

第一层追问：显示名重复怎么办？答：身份依赖平台、环境和类型键，不按显示名裸比。

第二层追问：URN 改了呢？答：等同身份迁移，旧血缘和引用需要处理；不能只修改 UI 名称就认为完成重命名。

### Q3【进阶】为什么要拆 SDK 和 API？

答：API 为浏览器或远程客户端提供身份与边界；SDK 让任务和 Runtime 等可信组件复用同一实体与编排规则，避免 HTTP 成为唯一调用方式。

第一层追问：直接 SDK 会绕鉴权吗？答：取决于 require_auth、user_token 和可信模式配置，必须明确部署边界。

第二层追问：哪个层注入 creator？答：服务从可信主体注入，强制覆盖用户字段；HTTP 路由传 actor 不等于任意客户端头都可信。

### Q4【进阶】加锁以后注册就是幂等的吗？

答：不是。锁串行化竞争；稳定 URN、存在性检查及 skip/overwrite 决定重复行为。当前锁还只在进程内。

第一层追问：两个副本同时判断不存在？答：两边可能同时写；同 URN 不保证多个 Aspect 原子一致。

第二层追问：怎么改？答：把唯一性/版本判定推到可靠服务端，结合幂等键；分布式锁只是协调手段，还要考虑超时、租约和旧持有者写入。

### Q5【进阶】为什么注册成功却搜不到？

答：写入确认、实体存在和搜索索引可见是不同阶段。当前轮询 GraphQL 存在性，不等于验证 ES 所有字段。

第一层追问：GraphQL 天然强一致？答：不是，要看 resolver，不能用接口名替代存储语义。

第二层追问：轮询超时怎么报？答：明确“已发送、验证超时”，保留 URN/trace_id 供查询，不盲目创建新对象。

### Q6【进阶】如何防止伪造请求中的域绕过原对象授权？

答：【已实现】`amend()` 先按 URN 读取原对象，再以 `existing_data` 的当前域检查 EDIT 权限，之后才合并请求；调用者不能只在请求里填一个自己有权限的域，就替代对原对象的授权判断。这证明的是原对象修改授权的取值顺序，不等于已证明目标域迁移受控。

第一层追问：能否据此说用户不能把对象迁到任意域？答：不能。当前 `_check_protected_fields()` 明确保护 name 以及数据集的 dataset_name/version，creator 在后续单独保护；这不等于 Domain 也不可改。在本段尚未看到合并后目标域的二次授权，需继续核对 API、SDK guard 和下游写入规则，再判断迁移约束是否完整；也不能仅凭这里没有检查就宣布已证明存在漏洞。

第二层追问：怎样验证，而不是停在推测？答：【改进建议】构造虚构域 A/B：用户可改原域 A 但不可写目标域 B，分别走 API 与直接 SDK，检查拒绝位置、实际写入与审计；另覆盖没有原域权限却伪造请求域的用例。原对象授权、目标域迁移授权和检查至写入的 TOCTOU 是三个问题，需分别验证；版本条件或事务是并发改进方向，不是当前已排除竞争的证据。

### Q7【进阶】为什么 Java、Play 和 React 都要改？

答：GMS 承担身份和权限，Play 承担服务端会话与代理凭证，React 承担用户操作；只改其中一层会产生登录成功但 API 身份不一致等断点。

第一层追问：认证与授权的区别？答：认证证明谁，授权决定其对资源的动作。

第二层追问：白名单与角色重复吗？答：准入是粗门槛，角色与域是细操作权，不能互相代替。

### Q8【深入】长效 PAT 自动供给如何避免重复和泄露？

答：使用稳定名称/实时 secret 读取、每用户锁与二次检查；服务端用调用者权限读写加密 Aspect，代理使用时注入。

第一层追问：加密与 hash 为什么都可能需要？答：验证可只用 hash，再次取回原值则需受控可逆存储，两者用途不同。

第二层追问：撤销后缓存呢？答：缓存可能短期陈旧，应结合失效、短 TTL 或下游拒绝处理；这是需要核验和改进的边界。

### Q9【深入】Agent 已登录，为何还说读权限待验证？

答：登录只保护入口；读取范围取决于工具以谁的 token 访问什么资源。注册有 can_register 门禁，但不能推导所有读工具都逐用户隔离。

第一层追问：注册被拒后模型重试参数怎么办？答：权限错误不是格式错误，工具继续拒绝并向用户解释。

第二层追问：要证明没有越权，需要什么？答：不同用户、不同域的正反例，检查真实下游身份和审计结果，覆盖直接 HTTP 与工具路径。

### Q10【深入】如何证明重构有价值，而不是代码变多？

答：展示一条实体规则如何被 HTTP 和库调用复用，列出 SDK 消费方、独立测试和错误隔离；用具体维护与接入问题说明价值。

第一层追问：代码量能代表贡献吗？答：只能辅助盘点，模块职责、设计决策和可验证补丁更有说服力。

第二层追问：你最愿意承认的不足？答：跨副本一致性、权限边界和异步可见性仍需系统验证；明确不足比把基础组件说成原创更可信。

## 8. 两个白板练习

**练习一：两个进程注册同一 URN。** 画“查不存在→发A→发B→验证”，让一进程在A后超时，另一进程覆盖。答案须指出：进程锁不跨进程，重试不回滚，存在不证明B正确；再提出版本约束或幂等键并说明代价。

**练习二：登录后调用 Agent 注册。** 逐跳标 actor、session token、PAT、can_register、目标域与 creator。篡改 actor 头、撤销角色或传别人的 session_id 时，哪层应拒绝？按身份表区分已有检查与待测边界，页面按钮不作授权证据。

## 9. 源码阅读路线与个人证据

本地源码根：`D:\博士后出站考核\相关项目\data_infra_platform`。先读 `docs/architecture/数据工程架构设计说明书.md` 看团队功能域；再进入 `libs/datahub_extensions/`：

1. `datahub_register/metadata/entity/metadata_entity.py`：URN、校验、MCP 构造，确认纯计算边界。
2. `datahub_register/metadata/service/metadata_service.py`：register、amend、锁、exists 与 verification。
3. `datahub_register/metadata/data_access/`、`publish/`：GraphQL、搜索和 Emitter 分工。
4. `datahub_extensions_api/api/routers/register.py`、`permission/dependencies.py`：HTTP 主体与域权限。
5. `datahub_extensions_api/api/routers/chat.py` → `datahub_chat/chat/service/chat_service.py` → `mcp/tool_adapter.py` → `tools/register/register_metadata.py`：Agent 全链路。
6. `third_party/datahub/metadata-service/auth-servlet-impl/src/main/java/com/datahub/auth/authentication/IDaaSAuthController.java`：企业身份入口；文件名是本地历史命名。
7. `third_party/datahub/datahub-frontend/app/auth/nevertoken/NeverTokenManager.java` 与 `app/controllers/Application.java`：凭证和代理。
8. `third_party/datahub/datahub-graphql-core/src/main/java/com/linkedin/datahub/graphql/resolvers/auth/` 与 `datahub-web-react/src/app/`：服务端凭证读写和浏览器页面。

【已实现】个人补丁入口：`fe241aca` SDK/API；`b6f7ef59` 身份；`e2013a93` 准入；`360cc996` 角色；`9dd6c201` 凭证；`65b1edb6` 对话；`523ed8e2` 配置和链接。用 `git show <hash>` 读具体改动，区分后续团队补丁。
