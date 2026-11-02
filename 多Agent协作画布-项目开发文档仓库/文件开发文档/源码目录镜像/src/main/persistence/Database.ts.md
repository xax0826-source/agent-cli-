# src/main/persistence/Database.ts

## 1. 对应代码

- 源码相对路径：`src/main/persistence/Database.ts`。
- 状态：拟新增代码文件；当前没有产品代码实现。
- 文件职责：持久化流程层级、会话节点、真实边、配置与消息事件。。

## 2. 当前职责与工作方式

目前尚未创建对应的产品源码。本节为计划中的职责，不把设计当作已实现行为。

schema、transaction、migration、GraphRepository。

## 3. 关联功能、需求和流程图节点

- [06.01 数据模型与写入](../../../../../流程图/06-数据存储与恢复/06.01-数据模型与写入.md#task-01)：关联开发任务 T-01。

## 4. 具体开发计划

<a id="plan"></a>

建议 SQLite；投影边不建表；写边前二次校验端点为会话节点；迁移保留稳定 ID。

拟重点涉及：schema、transaction、migration、GraphRepository。

### 建议持久化表（未实现）

`flows(id, owner_subflow_node_id)`、`nodes(id, parent_flow_id, kind, child_flow_id, session_id, position)`、`real_session_edges(id, source_session_node_id, target_session_node_id)`、`sessions(id, cli_type, model_id, lifecycle_state)`、`events(id, session_id, edge_id, event_type, payload, sequence)`。

这里仅将 `real_session_edges` 视为可写的关系表；不创建 `aggregate_edges` 表。数据库约束可保证端点存在，端点节点类型需要在事务中的应用校验（或由明确的数据库约束机制保证）。删除与迁移必须维护引用完整性。

## 5. 相关文件与开发顺序

本文件与上述关联节点涉及的其他源码按对应节点任务的依赖关系推进；若修改共享领域类型，应先更新类型契约再调整 UI、存储或 Agent 运行时使用方。

## 6. 注意事项与验证方法

<a id="verification"></a>

- 验证目标：应用重启后节点、层级、真实边、模型配置可恢复，不出现人工聚合边。
- 对新增的产品代码：在真实源码出现后执行单元测试和端到端测试；当前无通过记录。
- 错误处理、兼容和安全行为以节点开发文档的验收标准为准，不用“已写计划”代替实际验收。

## 7. 当前具体进度

<a id="continue"></a>

待开始。继续位置：从第 4 节按计划创建实际源码，补充测试与结果后再更新上层任务状态。

## 8. 落盘更改记录

暂无实际源码更改记录。后续每次修改按批次追加实际更改、关键符号、原因、验证结果与继续位置。
