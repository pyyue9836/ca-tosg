# 怎么画 §4.1 那张 Method Overview 框图

## 用什么工具

[draw.io](https://app.diagrams.net/) 免费、网页版、所见即所得，IEEE 论文标准选项。
- 打开 [https://app.diagrams.net/](https://app.diagrams.net/)
- 选 "Create New Diagram" → "Blank Diagram"
- 文件名：`ca_tosg_method_overview`

## 画布布局（横排，长宽比约 2:1，最终尺寸约 14cm × 6cm）

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  [Collaborator vehicle X_j]              ┌──── L branch ────┐                │
│         │ LiDAR                          │ obj-level msg    │                │
│         ▼                                │ {b,c,p}_k        │                │
│   ┌──────────┐    M_j      ┌──────────┐  └──────────────────┘                │
│   │PointPillars├───────────►│  Cue z_t │            ┌─────────────┐          │
│   │  backbone  │            │ extractor│            │             │          │
│   └────────────┘            └──────────┘            │             │ s_t      │
│         │                       │                   │             │  selected│
│         │ F_j,t                 │ z_t (21-d)        │  RF Selector│  message │
│         ▼                       │                   │             │ ◄────────│
│   ┌──────────┐                  │                   │  g(z,γ̂,c)   │ via V2V  │
│   │ C16/C256 │                  │                   │             │  channel │
│   │  feature │                  │                   └─────────────┘          │
│   │  codec   │                  │                   ▲      ▲                 │
│   └──────────┘                  │                   │ γ̂_t  │ c_t             │
│         │                       │                   │      │                 │
│         ▼                       └──────────────────►│      │                 │
│   ┌──── C branch ────┐                              │      │                 │
│   │ compressed BEV   │              ┌───────────────┴──────┴──┐              │
│   │ ~1.98 Mbit info  │              │ Channel quality estimator│              │
│   └──────────────────┘              │ γ̂_t (SNR dB), c_t (AWGN  │              │
│                                     │           or Rayleigh)   │              │
│                                     └──────────────────────────┘              │
│  ═══════════════════════ V2V channel ════════════════════════════════════════ │
│                                                                                │
│                                                          [Ego vehicle X_e]    │
│                            ┌──────────┐                       │ LiDAR          │
│                  m_t^s_t   │ Fusion   │     M_e               ▼                │
│                ───────────►│  module  │◄────────────  ┌──────────┐             │
│                            │   Ψ(·)   │               │PointPillars│            │
│                            └──────────┘               │  backbone  │            │
│                                  │                    └────────────┘            │
│                                  ▼                                              │
│                            ┌──────────┐                                         │
│                            │Detection │  →  Ŷ_t  (3D boxes)                     │
│                            │  head D  │                                         │
│                            └──────────┘                                         │
└──────────────────────────────────────────────────────────────────────────────┘
```

## 元素清单（务必都画上）

**左侧 Collaborator 侧**（4 个组件）：
1. 车图标 + LiDAR scan icon（draw.io 自带"Car"形状）
2. **PointPillars Backbone** 矩形块（蓝色填充推荐）
3. **Cue extractor** 椭圆（输出 z_t 21 维向量）
4. **Feature codec C16/C256** 矩形块（橙色填充推荐）

**中间 Selector**：
5. **RF Selector g(z_t, γ̂_t, c_t)** 大矩形块（绿色填充推荐）
6. 三个输出箭头分别标 `L`, `C16`, `C256` —— 但只画一个"selected message m_t^{s_t}"用粗虚线表示分支择一

**右上 Channel cue 来源**：
7. **Channel quality estimator** 小矩形（从 802.11bd 或 5G NR 接收机给出）
8. 两个箭头：γ̂_t（SNR in dB）和 c_t（channel type）射到 selector

**右侧 Ego 侧**（5 个组件）：
9. 车图标
10. **PointPillars backbone** 矩形块（蓝色，注明 weights shared with collaborator）
11. **Fusion module Ψ** 矩形块（紫色填充推荐）
12. **Detection head D** 矩形块
13. 最终输出 **Ŷ_t (3D bounding boxes)** 文字

**横跨中间**：
14. 一条粗水平线标注 `V2V wireless channel`（带 BLER 和 SNR 标记）

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
- 标注数值：`~0.024 Mbit/frame` (L 分支)、`~0.495 Mbit/frame` (C16)、`~0.248 Mbit/frame` (C256)

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
