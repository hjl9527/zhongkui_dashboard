# 钟馗 · 舆情看板

一支 15 分钟实机演示的社区舆论数据看板：B站 / 小红书 / 小黑盒 / 微博评论 **11,280 条** ＋ B站弹幕 **24,733 条**。
把「情感打标 → 主题归并 → 峰谷定位」的分析链路收成一个可点击的界面，并保留「换一份 CSV 复跑」的最小闭环。

## 本地运行

```bash
pip install -r requirements.txt
streamlit run app.py
```

浏览器打开 `http://localhost:8501`。首屏直接出图，不需要上传任何文件。

## 目录

```
dashboard/
├── app.py                 # 六个页面 + 上传模式入口
├── config.py              # 中式编辑风色板与 CSS
├── data.py                # parquet 加载、按样本量加权合并
├── charts.py              # Plotly 图表（统一坐标轴与配色）
├── fastlane.py            # 上传模式：词典打标 + TF-IDF/KMeans + 时间窗
├── scripts/build_data.py  # 从分析产物重建 data/*.parquet
├── scripts/make_wordcloud.py
├── data/                  # 全量数据，约 1.0 MB（zstd parquet）
├── assets/                # 预生成词云（约 1.4 MB）
├── reports/               # 成品报告：一页摘要 PDF/JPG + 总报告 + 五问拆解
├── samples/               # 可直接试上传的小样例
├── requirements.txt
├── packages.txt           # 云端安装 Noto CJK 字体
└── .streamlit/config.toml # 宣纸底色主题
```

## 六个页面

| 页面 | 回答的问题 |
|---|---|
| 概览 | 这次传播是围观型还是深度讨论型？平台优先级怎么排？ |
| 情感结构 | 哪个平台、哪一层评论、哪个主题在正向或负向？ |
| 弹幕时间轴 | 弹幕量与情感指数随视频时间怎么变？峰谷对应什么画面？ |
| 主题与平台 | 13 个统一主题的份额、代表词（可拆平台×情感）、词云 |
| 数据与口径 | 全量文本、筛选与导出、可信度边界 |
| 研究报告 | 一页摘要 PDF、总报告、五问拆解 |

## 替换数据

侧边栏切到「上传我的 CSV」：

- 必需：`text_clean` / `text` / `content` 之一（一行一条）
- 可选：`progress`（弹幕秒数）、`platform`
- 输出：情感分布、TF-IDF + KMeans 主题、评论样本；弹幕额外输出 10 秒窗口时间轴
- `samples/` 里有两个可直接试的样例

上传模式是**快速版口径**（词典 + KMeans），与 Demo 的外部 AI 打标 + BERTopic 不可直接横向比较；Demo 的结论以 `data/` 里的产物为准。

## 重建 Demo 数据

```bash
python scripts/build_data.py --source "D:\找工啦\简历\游科_运营\数据分析"
python scripts/make_wordcloud.py
```

`build_data.py` 读取 `outputs/01_sentiment/labels_*.csv`、`outputs/03_topics_bt/`、
`outputs/04_report/theme_*_matrix.csv`、`outputs/02_danmaku/`，只保留看板需要的字段。
词云是预生成图片，避免在云端依赖中文字体与实时渲染。

## 部署到 Streamlit Community Cloud

1. 把 `dashboard/` 作为仓库根目录推到 GitHub（数据、词云与报告一并提交，总体积约 3 MB）。
2. 在 share.streamlit.io 新建 App：Main file 选 `app.py`。
3. `requirements.txt` 与 `packages.txt` 会被自动安装（后者用于 Noto CJK 字体）。

## 体积与性能

- 全量 parquet：评论 480 KB、弹幕 334 KB、主题与汇总约 195 KB，合计约 **1.0 MB**（原始 CSV 14.35 MB）
- 词云 JPG：六张（四平台合并 + 四个单平台 + 弹幕），约 1.4 MB
- 成品报告：两份 Markdown + 一页摘要 PDF/JPG，约 0.6 MB
- 仓库总计约 **3 MB**，远低于 Community Cloud 1 GB 与 GitHub 100 MB 建议值
- `st.cache_data` 全量加载，Plotly 关闭动画；首屏 3 秒内出图

## 口径边界

1. AI×AI 一致性 kappa 0.58–0.75，占比结论可用，不宜声称「高度可靠」。
2. 弹幕负向仅 3.4%，不代表满意；负向判断必须以评论为主。
3. 547 个 BERTopic 簇归并为 13 类，「其他/综合」占 15%–41%，影响绝对值、不影响跨平台比较。
4. 单条视频、非概率抽样，不能外推到整个产品周期。
5. 峰谷必须人工回看画面，这是唯一不可自动化的环节。
