# 跨平台状态含义对照与现有分类复核

核对日期：2026-11-02。依据：OW 工作簿只读导出、当前代码及本地数据库快照、平台官方说明，以及使用方确认的自家车排线规则。**本表把平台原意和 Delivery Desk 业务含义分开**；同一个显示分类可以包含业务上刻意合并的不同平台阶段。Guidance、工作簿和代码均未修改。

## 先按 Delivery Desk 现有业务含义读

统一筛选项是**运营分组**，不要求各平台原词逐字同义：`Scheduled` 可容纳已建单、待取件和运输中，只要还没有进入本地派送；`Out for Delivery` 对自家车包含当天已放进 OptimoRoute 排线，对外部承运商通常指最后一公里。XDP、STOPSTART 另有“承运商原始状态”筛选；它们在 Guidance 中的参考分组**不等于**保存的总体状态。具体原词仍在行内展示。

| 统一阶段 | 判断所需的证据 | 不能混同的情况 |
|---|---|---|
| 待交承运商 | 标签/托运单已建立，但承运商未取件 | 在现有宽泛的 `Scheduled` 分组内保留原始细节 |
| 已安排 | 确认了司机/路线或预约日期，尚未开始配送 | 在现有 `Scheduled` 分组内，不表示司机已出发 |
| 运输中 | 承运商已取件，在分拨、干线或配送站流转 | 在现有 `Scheduled` 分组内，不表示最后一公里派送 |
| 派送中（Delivery Desk `Out for Delivery`） | 承运商已装本地配送车/司机前往地址；**自家车例外：放入 OptimoRoute 当天排线，即代表当天会发出** | OptimoRoute `scheduled` 是业务上的当日派送计划，不代表司机已经出发；保留原始状态供查看 |
| 已送达 | 承运商明确送达，最好有 POD/签收或等效事件 | OW `Completed` 在无承运商结果时是系统现有的兜底代理值，需显示来源 |
| 配送异常 | 送货尝试失败、地址问题、损坏或拒收等；保留具体原因 | `Failed` 是运营问题分组，原始异常类型仍需保留 |
| 待核实 | 没有可靠承运商状态或连接不唯一 | XDP 总体 `Awaiting` 是专门的待核实类别，另可按 XDP 原始状态筛选 |

## 各平台的原意和现有映射

| 来源原值 / 事件 | 平台原意与证据 | 现有总体状态 | 建议统一阶段 / 处理 | 判断 |
|---|---|---|---|---|
| **OW `Completed` / `C`** | OW 订单流程完成；本工作簿中可与 Amazon `IN_TRANSIT`、Palletways `IN TRANSIT`、XDP `DELIVERY` 同时存在。公开 OrderWise 资料在出库进度语境使用 Completed，不能证明本公司导出字段的完整定义。 | Delivered（承运商缺失时兜底） | 作为**无承运商结果时的代理值**保留，并显示来源 OW；不能把它描述成承运商已签收。 | **业务兜底，需核对说明文字** |
| OW `Awaiting despatch`、`Invoice waiting to be printed`、`Partially despatched` | 订单/发货准备状态；不是物理配送扫描。 | Unscheduled（未识别值兜底） | 宽泛的未安排/未发运分组可保留；保留 OW 原词。 | **合理合并**；OW 内部定义仍待确认 |
| OW `Cancelled` 文字 | OW 订单取消。 | Unscheduled；仅 `X` 或配送方式 `TO BE CANCELLED` 有取消映射 | 订单取消；与承运商取消分开记录。 | **漏映射** |
| **XDP `DELIVERED`** | 官方：货物成功送达；源表可另有 POD URL。 | 总体 Awaiting；XDP 专属筛选/显示为 DELIVERED | 当前是**双层状态设计**，代码测试明确锁定；保留。只有业务决定统一总体状态也要反映 XDP 送达时才改。 | **有意分离，非已证实错误** |
| XDP `NEXT STOP` | 司机即将到达；XDP 官方描述 next stop 通知。 | 总体 Awaiting；Guidance 参考分组 Out for Delivery | 原始 XDP 状态可筛选/显示；参考分组说明其业务阶段。 | **合理双层分组** |
| XDP `DELIVERY`，样本详情 `At Delivery Depot` | 到达配送站；单靠事件名不能说已装上本地车。 | 总体 Awaiting；Guidance 参考分组 Scheduled | 属于广义 Scheduled（未到本地派送），保留原始详情。 | **合理合并** |
| XDP `COLLECT`，样本详情 `At Collection Depot` | 在揽收站。 | 总体 Awaiting | 原始状态单独展示；没有强制对应总体阶段。 | **按现有双层设计保留** |
| XDP `DAMAGE`、`NOT RECEIVED`、`DELETE` | 样本分别显示“损坏可退回”“托运单未收到”“无详情”；官方公开 FAQ 未定义这些内部事件码。 | Failed | `Failed` 是需要处理的异常队列，可保留；其中 `DELETE` 的业务原因仍需内部确认。 | **保留异常分组；仅 DELETE 含义待核** |
| XDP `EMAIL`、空白 | 通知事件/无状态；不是配送阶段。 | Awaiting | 待核实类别；原始通知事件另存。 | **合理** |
| **Palletways `POD/POD`** | API note 中有 POD 日期、时间、签名；官方示例含 POD 事件。 | Delivered | 已送达。 | 合理 |
| Palletways `VL/SCN/800`、`VP/DAR` | 代码解释为装本地配送车、司机到达。官方 API 提供 group/type/code 字段，但这些组合的业务定义主要来自本地实现。 | Out for Delivery | 派送中。 | 基本合理，建议与真实事件复核 |
| Palletways hub/depot 扫描（BAY/VU/VL/JIN/ARC） | 承运网络流转。 | Scheduled（API In Transit 经二次映射） | 广义 Scheduled＝尚未进入本地派送；原始 In Transit 保留。 | **合理合并** |
| Palletways `BIN/BIN` 已预约 | 预约活动。 | Scheduled | 已安排。 | 合理，需确认实际预约成功 |
| Palletways `BIN/BIN` 仅留言/无人接听 | 代码标签是 Awaiting customer booking。 | Scheduled | 广义 Scheduled 的预约流程中，原始标签说明尚待客户确认。 | **合理合并** |
| Palletways `POC` | API 事件组为 POC；本地代码把它标作 Consignment created，未找到官方定义证实这个解释。 | Scheduled | 广义 Scheduled 可容纳建单阶段；POC 标签的准确含义仍待内部验证。 | **分组可保留，标签待核** |
| Palletways Damaged / Lost / Refused / Return | 损坏 / 丢失 / 收件人拒收 / 退回，来源和处理不同。 | Failed / Lost / Rejected / Return | 统一类别用于运营筛选；原始原因仍单独展示。 | **合理合并** |
| **OptimoRoute `unscheduled`** | 官方：订单未被安排。 | Unscheduled | 未安排。 | 合理 |
| OptimoRoute `scheduled` | 官方：订单尚未开始服务；使用方确认，自家车放入 OptimoRoute 排线通常表示当天会发出。 | Out for Delivery | 保持现有业务分类；同时保留原始 `scheduled`，避免误解为司机已上路。 | **已确认的业务规则，不是错误** |
| OptimoRoute `on_route` | 官方：司机正在去订单地点。 | Out for Delivery | 派送中。 | 合理 |
| OptimoRoute `servicing` | 官方：正在现场服务。 | Out for Delivery | 派送中/服务中，保留子状态。 | 可接受但较粗 |
| OptimoRoute `success`、`failed` | 官方：服务成功 / 司机未能完成。 | Delivered / Failed | 已送达 / 配送失败。 | 合理（success 最好保留 POD） |
| OptimoRoute `rejected` | 官方：**司机**拒绝该订单。 | Rejected | 统一 Rejected 异常队列；原始来源可区分司机拒单与收件人拒收。 | **合理合并** |
| OptimoRoute `cancelled` | 官方：客户取消。 | 回退 OW | 已取消，保留取消来源。 | **漏映射** |
| **Amazon `READY_FOR_RECEIVE`** | 官方：包裹已建立，在发件地等待承运商取件。 | Scheduled | 广义 Scheduled 涵盖进入发运流程但未到本地派送；原始标签保留。 | **合理合并** |
| Amazon `IN_TRANSIT` | 官方：承运商已取件，正在运输。 | Scheduled | 广义 Scheduled 涵盖未到最后一公里的运输；原始标签保留。 | **合理合并** |
| Amazon `OUT_FOR_DELIVERY`、`DELIVERED` | 官方：派送中 / 已成功送达。 | Out for Delivery / Delivered | 派送中 / 已送达。 | 合理 |
| Amazon `LOST` | 官方：包裹丢失。 | Failed | 进入 Failed Deliveries 运营处理队列，原始 Lost 仍显示。 | **合理合并** |
| Amazon `UNDELIVERABLE`、`DELIVERY_ATTEMPTED` | 官方：无法送达 / 已尝试但未送达。后者在当前代码中未映射。 | Failed / 回退 OW | 配送异常，分别保留原因。 | 后者**漏映射** |
| Amazon `REJECTED`、`AWAITING_CUSTOMER_PICKUP`、`PICKUP_CANCELLED` 等 | 官方分别为收件人拒收、待客户自提、取件取消；不等于已送达。 | 未映射，回退 OW | 按具体含义归异常/待自提/取消取件；保留原词。 | **漏映射** |
| **Routine Dashboard - Live 白/橙/黄填色** | 内部运营表颜色规则，不是承运商官方状态。 | Own van 白/橙 Scheduled，黄 Failed，且优先于 OptimoRoute | 需主管确认颜色业务定义和覆盖优先级，尤其已送达后是否还允许白色覆盖。 | 内部规则待确认 |

## 审核结果：保留与待核

**保留现有规则：**OptimoRoute `scheduled` → Out for Delivery（使用方确认的自家车当天排线）；Amazon `READY_FOR_RECEIVE`/`IN_TRANSIT` 与 Palletways 运输/预约阶段 → 广义 Scheduled；Amazon `LOST` 与 Palletways Damaged → Failed 运营处理队列；不同来源的拒单/拒收 → Rejected 队列。XDP/STOPSTART 的原始状态筛选与总体状态是两层设计，Guidance 已有说明，不能因为原词 `DELIVERED` 就认定总体 Awaiting 是程序错误。

**需要处理或确认的少数项目：**

1. **OW `Cancelled` 文字漏映射。**Guidance 把它列为取消，但 `ow_status_name` 只列 `X`。快照中 155 个独立 OW 订单的 J 列是 `Cancelled`，其中仅 74 个的配送方式是 `TO BE CANCELLED`；其余 81 个不能靠这条方式规则识别取消。应确认是否给 J 列文字值增加明确映射。
2. **OptimoRoute `cancelled` 漏映射。**官方有该状态，现有 mapper 没有；若这类订单进入当前同步流程，会回退 OW。应确认取消来源优先级。
3. **Amazon 少数明确的原始状态未映射。**快照中匹配 OW 的 `DELIVERY_ATTEMPTED` 7 单、`REJECTED` 1 单、`AWAITING_CUSTOMER_PICKUP` 1 单、`RETURNED_TO_SELLER` 2 单，其 OW J 列均为 Completed。代码对这些值回退 OW，因而可能把“尝试未送达/拒收/待自提/退回”归为总体 Delivered。先定它们属于哪个既有运营队列，再补规则；不要只按英文词面推断。
4. **OW `Completed` → Delivered 的兜底标签应说清楚。**本地数据库快照中，Own van 有 3,362 笔总体 Delivered 但没有 OptimoRoute providerStatus；Palletways 1,042 笔状态来源是 OW、38 笔来源是 Palletways。这是现有业务代理规则，不等于有承运商签收证据。保留映射时应在说明和页面来源标签上明确。
5. **XDP `DELETE` 和 Palletways `POC` 的内部事件语义待核。**现有运营分组可以保留；不要把事件名解释成“配送失败”或“已预约”这样的精确事实，除非有来源定义。

## 实际数据核对与限制

- 工作簿快照：当前 OW XDP 订单 952 笔均能按订单号连到 XDP 页；其中 768 笔的 XDP 原始状态为 `DELIVERED`。本地数据库快照的 XDP 总体状态为 Awaiting 948 笔、Failed 4 笔。这符合代码测试锁定的**两层状态设计**；是否让 XDP 原始 Delivered 同步改变总体状态，是业务规则选择而非已证实程序错误。
- Amazon 页实际有 `READY_FOR_RECEIVE` 226 行、`LOST` 27 行、`DELIVERY_ATTEMPTED` 7 行，以及多种当前代码未映射值。行数不等于独立 OW 订单数。
- Palletways 页 F 列实际有 `DELIVERED` 1,073 行、`IN TRANSIT` 33 行、`AWAITING PALLETWAYS MAPPING` 86 行。F 是工作簿的归纳状态；实际配送证据应追溯 API notes/POD。
- 尚未获取实时 OptimoRoute API 全量导出，也未直接调用实时 Palletways 或 XDP 系统。代码含义和快照能证明映射问题；不能由此断言每个运行页面的实时最终状态。
- 公开 OrderWise 资料没有给出本公司 `Sales Activity!J` 每个代码的正式定义。OW `Completed` 与承运商未送达并存，足以说明两者不能直接等同；具体 OW 流程含义仍需内部帮助文档或导出配置确认。

## 证据

- [OptimoRoute 官方 API：Order Status Values](https://optimoroute.com/api/)
- [Amazon Shipping 官方状态定义](https://developer-docs.shipping.amazon.com/apis/docs/shipping-api-v2-model)
- [XDP 官方常见状态说明](https://xdp.co.uk/faqs/)
- [Palletways 官方 API 字段和事件示例](https://api.palletways.com/documentation/en/index-en.html)
- [OrderWise 公开资料：订单出库状态语境](https://orderwise.co.uk/en/blog/control-manage-bulk-orders-call-offs-inventory-draw-down)
- 本地实现：`delivery_data.py`、`xdp_sheet.py`、`palletways_live.py`、`server.py`、`src/admin.js`。
