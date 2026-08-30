"""扫榜确定性实现（D9：US-24）：采集 → 清洗 → 质量过滤 → 趋势 → 选题。

无外部爬虫服务时，`collect_rankings` 返回两平台（起点/番茄）结构真实的榜单样例
（真实抓取可在 collect 节点换成 ScanService 工具）；清洗/趋势/选题为确定性计算，非占位。
"""

from collections import Counter

PLATFORMS = ["qidian", "fanqie"]
PLATFORM_NAMES = {"qidian": "起点", "fanqie": "番茄"}

MIN_VALID_WORDS = 10  # 万字
MIN_VALID_RATING = 7.0


def _book(rank, title, author, genre, words, followers, growth, rating, tags):
    return {
        "rank": rank, "title": title, "author": author, "genre": genre,
        "words": words, "followers": followers, "growth_7d": growth, "rating": rating, "tags": tags,
    }


# ---- 平台样例榜单（结构真实，数字示意） ----

QIDIAN_BOOKS = [
    _book(1, "我在凡人修仙世界当掌门", "尘归尘", "玄幻", 468, 328900, 18200, 8.9, ["系统流", "凡人流", "升级流"]),
    _book(2, "洪荒：开局签到先天灵宝", "一叶知秋", "洪荒", 212, 265400, 15300, 8.6, ["洪荒", "签到流", "无敌流"]),
    _book(3, "深空之下", "罗天", "科幻", 351, 244100, 12900, 9.2, ["星际", "硬科幻", "文明流"]),
    _book(4, "我的徒弟都是万中无一", "笑春风", "仙侠", 298, 231000, 12100, 8.8, ["师徒", "轻松流", "养成"]),
    _book(5, "都市：神豪从退婚开始", "键盘侠", "都市", 156, 218700, 11400, 8.2, ["神豪流", "退婚流", "日常"]),
    _book(6, "遮天蔽日：我以凡人之躯比肩神明", "山河", "玄幻", 402, 209300, 10800, 9.0, ["无敌流", "热血", "大帝流"]),
    _book(7, "回到九零当文豪", "牧野", "历史", 188, 198400, 10200, 8.7, ["穿越", "年代文", "文化兴国"]),
    _book(8, "奶爸的修真日常", "一只喵", "都市", 143, 187900, 9600, 8.4, ["奶爸", "日常", "温馨"]),
    _book(9, "深渊之主", "夜雨声烦", "悬疑", 264, 176300, 9100, 8.9, ["克苏鲁", "末世", "诡异流"]),
    _book(10, "从精神病院走出的武神", "胖虎", "玄幻", 231, 168900, 8700, 8.5, ["废柴流", "崛起", "热血"]),
    _book(11, "全球高武：从觉醒开始", "孤舟", "科幻", 319, 159800, 8300, 8.8, ["高武", "进化流", "国运"]),
    _book(12, "女帝的贴身高手", "夜星", "玄幻", 277, 152400, 7900, 8.1, ["女帝", "贴身", "暧昧"]),
    _book(13, "大秦：开局召唤十万铁骑", "秦失鹿", "历史", 206, 147600, 7400, 8.3, ["秦穿", "召唤流", "争霸"]),
    _book(14, "我在末世捡属性", "野火", "末世", 189, 142300, 7200, 8.6, ["末世", "系统流", "进化"]),
    _book(15, "我的治愈系游戏", "青衫客", "悬疑", 174, 138700, 6900, 8.9, ["诡异流", "治愈", "规则怪谈"]),
    _book(16, "都市之万能回收", "小李飞刀", "都市", 122, 134500, 6500, 7.9, ["回收流", "金手指", "轻松"]),
    _book(17, "我是神话生物", "白泽", "玄幻", 346, 131200, 6200, 9.1, ["神话生物", "无敌流", "吞噬流"]),
    _book(18, "剑道独尊", "剑客无名", "仙侠", 287, 128900, 5900, 8.7, ["剑修", "独尊流", "热血"]),
    _book(19, "相亲对象是顶流", "奶油泡芙", "都市", 98, 125600, 5400, 8.0, ["甜宠", "相亲", "娱乐圈"]),
    _book(20, "星海中的拾荒者", "流浪者", "科幻", 243, 122800, 5100, 8.5, ["拾荒", "星际", "成长"]),
]

FANQIE_BOOKS = [
    _book(1, "神级龙卫", "任凡", "都市", 322, 512000, 26400, 8.7, ["战神归来", "贴身高手", "兵王"]),
    _book(2, "开局签到荒古圣体", "老猫", "玄幻", 268, 468000, 24100, 8.4, ["签到流", "圣体", "无敌流"]),
    _book(3, "重生之都市修仙", "归来仍是少年", "都市", 341, 455000, 22800, 8.8, ["重生", "修仙", "扮猪吃虎"]),
    _book(4, "四合院：开局一缸咸菜", "胡同串子", "年代", 187, 421000, 21900, 8.5, ["四合院", "年代文", "家长里短"]),
    _book(5, "神藏", "不灭", "悬疑", 296, 398000, 20500, 8.9, ["寻宝", "盗墓", "探险"]),
    _book(6, "战神：我是您的兵", "铁血", "军事", 234, 386000, 19200, 8.6, ["战神", "军事", "热血"]),
    _book(7, "我在万界捡宝", "捡宝小能手", "玄幻", 178, 375000, 18400, 8.3, ["万界", "金手指", "轻松"]),
    _book(8, "神医下山", "南拳北腿", "都市", 156, 363000, 17700, 8.2, ["神医", "下山", "扮猪吃虎"]),
    _book(9, "至尊弃少", "起风了", "都市", 289, 351000, 16900, 8.1, ["赘婿", "弃少", "逆袭"]),
    _book(10, "我的师傅是大白鹅", "鹅蛋", "仙侠", 143, 342000, 16100, 8.4, ["萌宠", "师徒", "轻松流"]),
    _book(11, "重生的我只想当学霸", "学霸归来", "都市", 217, 335000, 15400, 8.7, ["重生", "学霸", "校园"]),
    _book(12, "末世之我是最强召唤师", "召唤师", "末世", 254, 328000, 14800, 8.5, ["召唤流", "末世", "军团"]),
    _book(13, "我有亿点钱", "财神", "都市", 133, 321000, 14200, 8.0, ["神豪流", "轻松", "日常"]),
    _book(14, "斗罗：开局废武魂", "小熊猫", "玄幻", 312, 314000, 13600, 8.6, ["斗罗", "废武魂", "逆袭"]),
    _book(15, "万古神帝之永恒", "永恒", "玄幻", 405, 307000, 13100, 8.9, ["万古", "修炼", "热血"]),
    _book(16, "我在直播带货当主角", "带货一哥", "都市", 178, 298000, 12500, 7.8, ["直播", "带货", "商战"]),
    _book(17, "长夜余火", "熬夜选手", "悬疑", 233, 291000, 11900, 8.8, ["规则怪谈", "诡异", "烧脑"]),
    _book(18, "奶爸是全能巨星", "奶爸顶流", "都市", 121, 285000, 11300, 8.1, ["奶爸", "明星", "温馨"]),
    _book(19, "开局一只大荒鸡", "养鸡场主", "玄幻", 165, 279000, 10800, 8.3, ["宠物流", "搞笑", "轻松"]),
    _book(20, "我靠种田成神", "农夫", "玄幻", 152, 272000, 10200, 8.2, ["种田", "发育流", "悠闲"]),
]


def collect_rankings(platform: str) -> list[dict]:
    """采集平台榜单（demo 返回样例；真实环境换成 ScanService 工具调用）。"""
    src = QIDIAN_BOOKS if platform == "qidian" else FANQIE_BOOKS
    return [dict(b) for b in src]


def clean_books(books: list[dict]) -> tuple[list[dict], int]:
    """清洗：去重 + 字段规整 + 丢弃脏数据。"""
    cleaned: list[dict] = []
    seen: set[str] = set()
    dropped = 0
    for b in books:
        title = (b.get("title") or "").strip()
        if not title or title in seen:
            dropped += 1
            continue
        seen.add(title)
        try:
            rank = int(b.get("rank", 0))
            words = int(b.get("words", 0))
            followers = int(b.get("followers", 0))
            growth = int(b.get("growth_7d", 0))
        except (TypeError, ValueError):
            dropped += 1
            continue
        if rank <= 0 or words <= 0:
            dropped += 1
            continue
        cleaned.append(
            {
                "rank": rank,
                "title": title,
                "author": (b.get("author") or "").strip(),
                "genre": (b.get("genre") or "未知").strip(),
                "words": words,
                "followers": followers,
                "growth_7d": growth,
                "rating": float(b.get("rating", 0) or 0),
                "tags": [str(t).strip() for t in (b.get("tags") or []) if str(t).strip()],
            }
        )
    cleaned.sort(key=lambda x: x["rank"])
    return cleaned, dropped


def validate_quality(books: list[dict]) -> tuple[list[dict], list[dict]]:
    """质量过滤：字数达标 + 评分及格，返回（有效榜，剔除榜）。"""
    valid = [b for b in books if b["words"] >= MIN_VALID_WORDS and b["rating"] >= MIN_VALID_RATING]
    invalid = [b for b in books if b not in valid]
    return valid, invalid


def analyze_trends(books: list[dict]) -> dict:
    """趋势：题材分布（均值）、热词、头部增速、总览。"""
    total = len(books)
    genre_count: Counter = Counter()
    genre_followers: dict[str, int] = {}
    genre_growth: dict[str, int] = {}
    for b in books:
        g = b["genre"]
        genre_count[g] += 1
        genre_followers[g] = genre_followers.get(g, 0) + b["followers"]
        genre_growth[g] = genre_growth.get(g, 0) + b["growth_7d"]
    dist = [
        {
            "genre": g,
            "count": genre_count[g],
            "avg_followers": int(genre_followers[g] / genre_count[g]),
            "avg_growth": int(genre_growth[g] / genre_count[g]),
        }
        for g in genre_count
    ]
    dist.sort(key=lambda d: (-d["avg_growth"], -d["count"]))

    tag_count: Counter = Counter(t for b in books for t in b.get("tags", []))
    hot_tags = [{"tag": t, "count": c} for t, c in tag_count.most_common(12)]

    top = sorted(books, key=lambda b: -b["growth_7d"])[:5]
    top_books = [f"{b['title']}（{b['genre']}，7日+{b['growth_7d']}）" for b in top]

    avg_growth = sum(b["growth_7d"] for b in books) / total if total else 0
    insights = (
        f"本期有效 {total} 本；头部「{top[0]['title']}」7日增速 {top[0]['growth_7d']}，"
        f"全榜均增 {avg_growth:.0f}。"
    )
    return {"total": total, "insights": insights, "genre_distribution": dist, "hot_tags": hot_tags, "top_books": top_books}


def topic_decision(stats: dict, books: list[dict]) -> dict:
    """选题决策：增速×（1-份额）选蓝海题材，取该题材头部热词成题。"""
    dist = stats.get("genre_distribution") or []
    if not dist:
        return {
            "topic": "观察市场后再定", "genre": "", "hot_tag": "", "rationale": "本期数据不足，无法决策",
            "hooks": [], "risk": "数据量过小，结论仅供参考",
        }
    total_share = sum(d["count"] for d in dist) or 1
    scored = []
    for d in dist:
        saturation = d["count"] / total_share
        score = d["avg_growth"] * (1 - saturation)
        scored.append((score, d))
    scored.sort(key=lambda x: -x[0])
    pick = scored[0][1]
    genre = pick["genre"]

    genre_tags: Counter = Counter()
    for b in books:
        if b["genre"] == genre:
            # 排除与题材名同名的标签（如题材「洪荒」自带标签「洪荒」），避免选题「洪荒 × 洪荒」
            genre_tags.update(t for t in b.get("tags", []) if t != b["genre"])
    if not genre_tags:
        for b in books:
            if b["genre"] == genre:
                genre_tags.update(b.get("tags", []))
    hot_tag = genre_tags.most_common(1)[0][0] if genre_tags else (stats.get("hot_tags") or [{}])[0].get("tag", "系统流")

    genre_books = [b for b in books if b["genre"] == genre]
    sample = genre_books[0]["title"] if genre_books else "同类头部作品"
    rationale = (
        f"「{genre}」本期 {pick['count']} 本、均增 {pick['avg_growth']}，增速×蓝海系数最高；"
        f"该题材热词「{hot_tag}」出现 {genre_tags.get(hot_tag, 0)} 次，仍有空间，参考「{sample}」。"
    )
    hooks = [
        f"黄金三章冲突：开局 {hot_tag} 金手指落地 + 被轻视反杀",
        f"人设钩子：反差型主角（{genre} 标配 废柴/归来 开局，500 字内揭示目标）",
        f"题材钩子：复用 {hot_tag} 榜单爆点，差异化放在 设定/反派 维度",
    ]
    return {
        "topic": f"{genre} × {hot_tag} 轻爽文",
        "genre": genre,
        "hot_tag": hot_tag,
        "rationale": rationale,
        "hooks": hooks,
        "risk": f"「{genre}」头部效应强，上架竞争激烈；建议首周 3 万字冲量验证反馈",
    }


def generate_report(platform: str, stats: dict, decision: dict) -> str:
    """汇总报告文本（含选题决策）。"""
    name = PLATFORM_NAMES.get(platform, platform)
    dist = stats.get("genre_distribution") or []
    hot = stats.get("hot_tags") or []
    lines = [
        f"# {name}扫榜报告",
        "",
        stats.get("insights", ""),
        "",
        "## 题材分布",
        "",
        "| 题材 | 数量 | 均收藏 | 均增速 |",
        "|---|---|---|---|",
    ]
    for d in dist:
        lines.append(f"| {d['genre']} | {d['count']} | {d['avg_followers']} | {d['avg_growth']} |")
    lines += ["", "## 热词 Top", ""]
    lines += [f"- {h['tag']}（{h['count']}）" for h in hot]
    lines += ["", "## 头部增速", ""]
    lines += [f"- {t}" for t in stats.get("top_books", [])]
    lines += [
        "",
        "## 选题决策",
        "",
        f"- **推荐选题**：{decision.get('topic')}",
        f"- **理由**：{decision.get('rationale')}",
        f"- **钩子**：",
    ]
    lines += [f"  - {h}" for h in decision.get("hooks", [])]
    lines += [f"- **风险**：{decision.get('risk')}"]
    return "\n".join(lines)
