# 怎么画 §4.1 那张 Method Overview 框图

> ## ⚠️ 2026-08-02 更新 (Q2, S={L,C16}) —— 重画/改图时必须落实（Josh 手动 draw.io）
> 配合 S={L,C16} 形式化改动（Eq.(1) 已改为 2 元），overview 图要一次编辑做三件事：
> 1. **C16/C256 归组进同一个 feature-level 分支块**（已经是"Feature codec C16/C256"块，确认视觉上归组）。
> 2. **C256 行/标签加注**：`C256 (dominated — excluded from deployment, §III-B)`；部署选择器只在 {L, C16}
>    间择一，C256 只作 granularity ladder 的第三个 PHY 码点存在、不被选。
> 3. **载荷标注改成 channel-use Msym 值**（旧的 Mbit 值是错的、且单位错）：
>    `L ≈ 0.024 Msym/frame`、`C16 ≈ 0.99 Msym/frame`、`C256 ≈ 0.495 Msym/frame`（rate-1/2）。
> 4. selector 输出的分支择一：主箭头 `s_t ∈ {L, C16}`（2-bit 请求；'11' 及 C256 码点未用，§VI-M）。
> 下面正文的旧标注（第"文字标注"节）已按此更新；画完截图发我核 IEEE 风格。


## 用什么工具

[draw.io](https://app.diagrams.net/) 免费、网页版、所见即所得，IEEE 论文标准选项。
- 打开 [https://app.diagrams.net/](https://app.diagrams.net/)
- 选 "Create New Diagram" → "Blank Diagram"
- 文件名：`ca_tosg_method_overview`

## 画布布局（横排，长宽比约 2:1，最终尺寸约 14cm × 6cm）

```
     COLLABORATOR (X_j)                                      EGO (X_e)   <-- selector lives HERE
     -----------------                                       ---------
        | LiDAR                                                 | LiDAR
        v                                                       v
  +------------+                                          +------------+
  |PointPillars| <--------- weights shared -------------> |PointPillars|
  |  backbone  |                                          |  backbone  |
  +-----+------+                                          +-----+------+
        | F_j,t                                                 | F_ego,t  (local feature + local detections)
    +---+-----+                                     +-----------+------------+
    v         v                                     v           |            v
 +--------+ +--------+                          +--------+      |       +----------+
 |L branch| |C branch|                          |  Cue   |      |       | Channel  |
 |obj msg | |codec-> |                          |extractor|     |       |estimator |
 |{b,c,p}_k| |comp.BEV|                          | -> z_t |      |       | ^gamma_t |
 +---+----+ +---+----+                          +---+----+      |       |   c_t    |
     |          |                                   | z_t(21-d) |       +----+-----+
     |  transmit ONLY the                           +----> +----+-------+ <--+ (^gamma,c)
     |  requested message                                 | RF Selector|      (ego receiver-side
     |     m_t^{s_t}                                       | g(z,^g,c)  |       link-adaptation)
     +----------+---------                                 +-----+------+
                |                                                | s_t
   m_t^{s_t}    |                     s_t : EGO --> COLLABORATOR  | (2-bit request)
 (collab->ego) v   <=============== 2-bit request s_t ============+
   ============================== V2V wireless channel ==============================
                |  (requested message m_t^{s_t} arrives at ego)
                v
          +----------+        F_ego,t (skip)        (F_ego,t)
          | Fusion   | <---------------------------------+
          | module   |
          |  Psi(.)  |
          +----+-----+
               v
          +----------+
          |Detection | -->  Y_hat_t  (3D boxes)
          |  head D  |
          +----------+
```

## 元素清单（务必都画上）

**左侧 Collaborator 侧（X_j）——只负责按请求发消息**：
1. 车图标 + LiDAR scan icon
2. **PointPillars Backbone** 矩形块（蓝，注明 weights shared with ego）
3. **L branch**：object-level message `{b,c,p}_k`（橙）
4. **C branch**：Feature codec C16 → compressed BEV feature（橙）
5. 收到 2-bit 请求 `s_t` 后，**只发被选中的那一条** `m_t^{s_t}`（不同时发两条）

**右侧 Ego 侧（X_e）——选择器、cue、信道估计都在这边（正文 §III-B / L228 为准）**：
6. 车图标 + LiDAR
7. **PointPillars backbone**（蓝）→ 本地特征 `F_ego,t` + 本地检测流
8. **Cue extractor** 椭圆 → `z_t`（21 维）——**从 ego 自己的检测流算，不依赖 collaborator**
9. **Channel quality estimator** 小矩形 → `γ̂_t`(SNR dB)、`c_t`(信道类型)——ego 接收机侧链路自适应（802.11bd / 5G NR）
10. **RF Selector g(z_t, γ̂_t, c_t)**（绿，大块）——输入 `(z_t, γ̂_t, c_t)`，输出 `s_t`
11. **Fusion module Ψ**（紫）——把收到的 `m_t^{s_t}` 与本地 `F_ego,t` 融合
12. **Detection head D** → `Ŷ_t`（3D bounding boxes）

**横跨中间的 V2V channel（两条方向相反的箭头）**：
13. **`s_t` 2-bit 请求箭头：ego → collaborator**（粗虚线，标 "2-bit request `s_t`"）——决策在 ego，先发请求
14. **`m_t^{s_t}` 消息箭头：collaborator → ego**（标 "requested message"）——collaborator 收到请求后回传
15. 一条粗水平线标注 `V2V wireless channel`（带 BLER / SNR 标记）

## 颜色建议（统一 IEEE 图风格）

| 模块 | 填充色 | 描边 |
|---|---|---|
| Backbone (left + right) | `#DAE8FC` 浅蓝 | `#6C8EBF` |
| Cue extractor | `#D5E8D4` 浅绿 | `#82B366` |
| RF Selector | `#FFF2CC` 浅黄 | `#D6B656` |
| Feature codec C16/C256 | `#F8CECC` 浅橙 | `#B85450` |
| Fusion + detection | `#E1D5E7` 浅紫 | `#9673A6` |
| V2V channel 线 | 黑色实线（约 3pt） | — |
| 数据流箭头 | 黑色 1.5pt 实线，end arrow filled | — |
| Decision 分支虚线 | 黑色 1.5pt 虚线 | — |

## 文字标注（要写在框里的字）

- 公式记号用 LaTeX 风格的 italic 字符：`X_j`、`F_{j,t}`、`M_j`、`z_t`、`γ̂_t`、`c_t`、`s_t`、`m_t^{s_t}`、`Ψ`、`Ŷ_t`
- 函数名等用 mono 字体：`PointPillars`, `Cue extractor`, `RF Selector`, `Fusion`
- 标注数值（channel-use Msym，rate-1/2）：`~0.024 Msym/frame` (L 分支)、`~0.99 Msym/frame` (C16)、`~0.495 Msym/frame` (C256, dominated/excluded — 见顶部 Q2 更新)

## 导出步骤

1. File → Export as → PDF
2. 选 "Selection" 而不是 "Whole page"（去掉白边）
3. 文件名 `ca_tosg_method_overview.pdf`

## 放进 LaTeX 工程

1. 把 `ca_tosg_method_overview.pdf` 放到 `paper/figures/`
2. 打开 `paper/main.tex`，找到 line 189 那个红色的 `\todo{Insert overview figure...}`
3. 替换为：
   ```latex
   \includegraphics[width=\textwidth]{ca_tosg_method_overview.pdf}
   ```
4. 重新 Recompile 即可

## 参考样例

如果想找好图参照样式，看 SComCP 论文 Fig. 2（已经在我们 repo 里的 `SComCP_Task-Oriented_Semantic_Communication...pdf` page 3）——你画的图风格目标就是那种"双车 + backbone + codec + channel + fusion"。

## 时间预算

- 熟手 draw.io：1-1.5 小时
- 第一次用 draw.io：2-3 小时（含学习时间）

画完截图发给我，我可以检查标记是否符合 IEEE 风格要求。
