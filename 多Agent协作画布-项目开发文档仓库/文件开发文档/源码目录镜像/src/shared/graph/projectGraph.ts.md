# src/shared/graph/projectGraph.ts

## 1. 对应代码

- 源码相对路径：`src/shared/graph/projectGraph.ts`。
- 状态：拟新增代码文件；当前没有产品代码实现。
- 文件职责：将真实会话边投影到当前流程直接子节点；聚合同向同端点关系，输出底层边 ID。。

## 2. 当前职责与工作方式

目前尚未创建对应的产品源码。本节为计划中的职责，不把设计当作已实现行为。

projectToFlow(graph,flowId)、resolveVisibleChild、ProjectedEdge。

## 3. 关联功能、需求和流程图节点

- [02.02 分层聚合投影](../../../../../流程图/02-双视图投影与画布/02.02-分层聚合投影.md#task-01)：关联开发任务 T-01。

## 4. 具体开发计划

<a id="plan"></a>

仅展示两个端点都在当前流程后代中的边；相同直接可见节点内部的边隐藏；跨子流程的多条真实边汇成一条只读聚合边。

拟重点涉及：projectToFlow(graph,flowId)、resolveVisibleChild、ProjectedEdge。

### 建议投影伪代码（未实现）

```ts
function projectToFlow(flowId, tree, realEdges): ProjectedEdge[] {
  const buckets = new Map<string, string[]>();
  for (const edge of realEdges) {
    const a = visibleDirectChild(flowId, edge.sourceSessionNodeId, tree);
    const b = visibleDirectChild(flowId, edge.targetSessionNodeId, tree);
    if (!a || !b || a === b) continue;
    const key = `${a}::${b}`; // 有向聚合；方向语义待最终确认
    buckets.set(key, [...(buckets.get(key) ?? []), edge.id]);
  }
  return Array.from(buckets, ([key, ids]) => toReadonlyProjection(key, ids));
}
```

`visibleDirectChild` 应做真实祖先查询，严禁通过节点坐标或显示字符串猜测所属组；每次移动会话或修改真实边后应使投影缓存失效。

## 5. 相关文件与开发顺序

本文件与上述关联节点涉及的其他源码按对应节点任务的依赖关系推进；若修改共享领域类型，应先更新类型契约再调整 UI、存储或 Agent 运行时使用方。

## 6. 注意事项与验证方法

<a id="verification"></a>

- 验证目标：A1→B1、A2→B2 在父层仅有 A→B ×2；进入子层不生成虚假的跨层连接；投影可恢复原始边集合。
- 对新增的产品代码：在真实源码出现后执行单元测试和端到端测试；当前无通过记录。
- 错误处理、兼容和安全行为以节点开发文档的验收标准为准，不用“已写计划”代替实际验收。

## 7. 当前具体进度

<a id="continue"></a>

待开始。继续位置：从第 4 节按计划创建实际源码，补充测试与结果后再更新上层任务状态。

## 8. 落盘更改记录

暂无实际源码更改记录。后续每次修改按批次追加实际更改、关键符号、原因、验证结果与继续位置。
