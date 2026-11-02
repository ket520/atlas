# Delivery Desk 来源含义与对应关系核对

> **此初稿已被 [跨平台状态含义对照与现有分类复核](Cross_platform_status_crosswalk.md) 取代。**后续核对确认了 Delivery Desk 的统一业务分组及 XDP 的两层筛选设计；本页的部分“确认有错”判断不再适用。

核对日期：2026-11-02。依据：用户提供的 OW Google 工作簿只读导出、当前仓库代码，以及 XDP、Palletways、OptimoRoute、OrderWise 公开官方资料。本报告替代先前以状态数量和追踪号差异为主的初稿；没有修改 Guidance、OW 或应用代码。

## 先看结论

| 结论 | 应怎么理解 | 处理建议 |
|---|---|---|
| **确认有错：XDP 的 `DELIVERED` 未进入总体 `Delivered`** | XDP 官方说明 Delivered 是货物已成功送达。当前代码只把 `DAMAGE`、`DELETE`、`NOT RECEIVED` 改成 Failed，其他 XDP 状态初始为 Awaiting。导出快照中有 768 个当前 OW XDP 订单，其 XDP 状态为 `DELIVERED`。 | 在确认订单/托运单唯一且不是部分送达后，把 XDP `DELIVERED` 映射为总体 Delivered；保留原始状态和 POD。优先检查订单 658311。 |
| **已确认业务规则：OptimoRoute `scheduled` 归 `Out for Delivery`** | 官方定义是尚未开始服务；使用方确认，自家车放进 OptimoRoute 当天排线即代表当天会发出，所以 Delivery Desk 刻意归入 Out for Delivery。 | 保持现有映射，同时展示原始 `scheduled`，以免误认为司机已经出发。 |
| **确认有错：OptimoRoute `cancelled` 未映射** | OptimoRoute 官方状态列表包含 `cancelled`，现有映射没有这一项。 | 在已验证为同一订单的前提下，映射为 Cancelled；确认客户取消是否须优先于 OW。 |
| **高风险：OW `Completed` 被当成配送 `Delivered` 的兜底** | OW 的订单/出库状态和承运商实际送达是不同阶段。样本：OW 657281 为 Completed，但 Amazon 为 IN_TRANSIT；OW 658234 为 Completed，但 Palletways 为 IN TRANSIT；OW 660469 为 Completed，但 XDP 为 DELIVERY。公开 OrderWise 资料也把 Awaiting Despatch、Partially Despatched、Completed 放在订单出库进度语境。 | OW `Completed` 不应单独证明客户已收货。承运商没有可靠状态时，应显示“配送未确认”或另定明确的兜底规则。OW Sales Activity 的正式字段定义仍需内部支持文档确认。 |
| **确认有错：OW 文字 `Cancelled` 没有明确映射** | 当前代码只识别 `X` 为 Cancelled；OW 导出中也出现文字 `Cancelled`，通常落入 Unscheduled。配送方式 `TO BE CANCELLED` 有单独覆盖规则。 | 增加文字 `CANCELLED`，并明确订单取消与配送取消的优先级。 |
| **不是错误：Palletways 的 OW `Tracking No` 与 Palletways `Tracking ID` 大多不同** | Palletways 官方定义 TrackingID 是承运商分配给托运单的编号；`Reference` 是客户参考号。OW Tracking No 在样本中常是 BQS/VAN 号。979 个匹配订单的两个字段不相等，并不表示 979 个错单。 | 继续用 OW 订单号 ↔ Palletways `Customer Ref`/API `Reference` 定位，使用 Palletways 的 Tracking ID 跟踪；不要强求两个号码相等。 |

## 每个来源到底表示什么

| 来源 | 订单连接键 | 状态/日期的含义 | 当前代码状况 |
|---|---|---|---|
| **OW Sales Activity** | A `Order no` 是本系统订单主键；E `Order reference` 用于 OptimoRoute 匹配；S `Tracking No` 用于 Amazon 匹配。 | J `Status` 是 OW 订单流程状态，不能无条件视为最终配送结果。B `Order date` 是下单日期，X `Despatch Date` 是出库日期，不是承运商送达日期。 | 代码把 `Completed` 兜底映射为 Delivered；这与跨来源样本冲突。 |
| **XDP** | XDP A `Order No` ↔ OW A。当前快照 952/952 个 OW XDP 订单可按订单号找到 XDP 行。 | XDP I `Latest Status` 是承运商原始状态；E 是托运单编号；T 是 POD 链接。官方明确 Delivered 为已成功送达。 | `DELIVERED` 没有映射到总体 Delivered；`DELETE` 被当成 Failed，但没有找到官方资料证明 DELETE 就是配送失败，应复核。 |
| **Palletways** | 工作簿 A `Customer Ref` ↔ OW A；API `Reference` 是客户参考号；B `Tracking ID` 是承运商追踪号。当前快照 1,076/1,080 个 OW Palletways 订单可在工作簿中按订单号找到行。 | F `Palletways Status` 是工作簿状态；API notes/events 及 POD 是实际物流证据。Tracking ID 和 Consignment Number 不是 OW 的订单号。 | 现行读取器按 A/B/C/F/Z/AA 固定列取值；API 优先用 11 位 OW Tracking No，再按 API Reference=OW 订单号查。工作簿 B 已保存，但主 API 查找没有直接使用它；若 API Reference 不一致，会有漏配风险，需要用真实样本验证。 |
| **OptimoRoute** | OW E `Order reference` ↔ OptimoRoute `orderNo`，代码要求唯一匹配。 | 官方：`scheduled` 尚未开始，`on_route` 司机在路上，`servicing` 正在现场服务，`success` 完成，`failed` 未完成，`rejected` 司机拒绝，`cancelled` 客户取消。自家车业务上把当天已排线视作 Out for Delivery。 | `scheduled` 映射保留；`cancelled` 漏映射。当前未获取实时 API 全量导出，匹配覆盖率不能下结论。 |
| **Amazon Shipping** | OW S `Tracking No` ↔ Amazon B `TrackingId`。 | G `Order status` 是承运商状态；M 是预计送达时间，源值注明 UTC。 | 当前快照 181 个已匹配订单的追踪号出现不同 G 状态；代码保守回退 OW。需定义同一追踪号多行时如何选当前有效记录。 |

## 还不能直接改的地方

1. **OW 官方字段语义：**公开资料只支持“这些词与订单/出库流程有关”，不足以证明此公司 `Sales Activity!J` 每个值的精确定义。需要内部 OrderWise 帮助页或导出配置说明，尤其 `Completed`、`Cancelled`、`Invoice waiting to be printed`。
2. **XDP `DELETE`：**当前代码把它归 Failed。XDP 公开状态说明没有给这个内部事件码下定义；可能是托运单删除而非一次失败配送。先核对具体事件与订单结果。
3. **Palletways API 连接：**工作簿编号差异不是错。需要抽查 API `Reference`、`TrackingID`、工作簿 A/B 和 OW A/S 的同一订单，确认没有错误关联或漏配。
4. **OptimoRoute 实际覆盖：**代码规则已核，但没有对实时提供方订单做全量匹配统计。尤其要检查 OW `Order reference` 重复或不等于 provider `orderNo` 的情况。

## 证据索引

- 本地代码：`delivery_data.py` 的 `delivery_status`、`optimoroute_status_name`、`ow_status_name`、`apply_palletways_api_data`；`xdp_sheet.py` 的 `apply_status`；`palletways_live.py` 的 `derive_status`；`google_sheets.py` 的各工作簿读取器。
- [XDP 官方状态说明](https://xdp.co.uk/faqs/)
- [OptimoRoute 官方 API 状态定义](https://optimoroute.com/api/#order-status-values)
- [Palletways 官方 API 文档](https://api.palletways.com/documentation/en/index-en.html)
- [OrderWise 官方公开说明：订单出库进度词汇](https://orderwise.co.uk/en/blog/control-manage-bulk-orders-call-offs-inventory-draw-down)

统计只代表 2026-11-02 的只读工作簿快照。没有登录或调用实时 XDP、Palletways、OptimoRoute 接口，也没有验证每笔订单在运行页面中的最终显示。
