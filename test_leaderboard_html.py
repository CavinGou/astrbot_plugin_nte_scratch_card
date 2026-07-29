"""测试排行榜 HTML 模板（独立版，不依赖 astrbot）"""
from pathlib import Path

LEADERBOARD_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;700;900&display=swap');
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:"Noto Sans SC","Microsoft YaHei",sans-serif;background:#1a1208;width:840px;padding:16px}
.outer-frame{border:3px solid #8a6a20;border-radius:20px;background:linear-gradient(180deg,#2a2218,#1e1810 50%,#161208);padding:16px;box-shadow:inset 0 0 40px rgba(0,0,0,.5),0 0 20px rgba(120,80,20,.3)}
.header{display:flex;align-items:center;background:linear-gradient(180deg,#3a3020,#2a2218);border:1px solid #6a5a30;border-radius:12px;padding:10px 20px;margin-bottom:12px;box-shadow:inset 0 1px 0 rgba(255,255,255,.08)}
.header span{font-size:15px;font-weight:700;color:#c0a860;text-shadow:0 1px 2px rgba(0,0,0,.5);letter-spacing:3px}
.h-rank{width:110px;text-align:center}.h-name{flex:1;text-align:center}.h-money{width:280px;text-align:right;padding-right:8px}
.card{margin-bottom:8px;border-radius:14px;overflow:hidden}
.row{display:flex;align-items:stretch;min-height:78px;border-radius:14px;overflow:hidden;position:relative}
.badge{width:110px;display:flex;flex-direction:column;align-items:center;justify-content:center;position:relative;flex-shrink:0}
.badge .num{font-size:40px;font-weight:900;line-height:1;text-shadow:2px 2px 6px rgba(0,0,0,.4);z-index:1}
.badge .paw-icon{position:absolute;top:6px;right:8px;font-size:28px;opacity:.25;transform:rotate(-15deg)}
.badge .line{position:absolute;right:0;top:10%;height:80%;width:1px}
.name-section{flex:1;display:flex;flex-direction:column;justify-content:center;padding:12px 16px;position:relative;min-width:0}
.id-text{font-size:10px;letter-spacing:1.5px;opacity:.5;margin-bottom:3px;font-weight:700}
.name-text{font-size:20px;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;text-shadow:0 1px 2px rgba(0,0,0,.2)}
.barcode{margin-top:6px;height:14px;width:200px;opacity:.25}
.money-section{width:280px;display:flex;align-items:center;justify-content:flex-end;padding:12px 20px 12px 0;gap:10px;flex-shrink:0}
.coin-icon{width:36px;height:36px;border-radius:50%;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:16px;font-weight:900;border:2px solid #a08020;box-shadow:inset 0 2px 6px rgba(255,255,255,.2),0 2px 8px rgba(0,0,0,.3)}
.money-text{font-size:20px;font-weight:700;text-shadow:0 1px 3px rgba(0,0,0,.3)}
.hot-tag{position:absolute;right:16px;bottom:4px;font-size:8px;letter-spacing:1px;opacity:.25;font-weight:700}
.dash{width:1px;align-self:stretch;margin:12px 0;border-left:1px dashed rgba(150,130,80,.4);flex-shrink:0}
.card-r1 .row{background:linear-gradient(135deg,#5a4a18,#a07a20 25%,#c8a030 50%,#a07a20 75%,#5a4a18);border:2px solid #d4a840;box-shadow:0 0 30px rgba(200,160,40,.25),inset 0 1px 0 rgba(255,255,255,.15)}
.card-r1 .badge{background:linear-gradient(180deg,#c8a030,#8a6a18);border-right:1px solid rgba(255,255,255,.15)}
.card-r1 .badge .num{color:#fff8e0}.card-r1 .badge .line{background:rgba(255,255,255,.2)}
.card-r1 .name-text{color:#fff}.card-r1 .id-text{color:rgba(255,255,255,.5)}
.card-r1 .barcode{background:repeating-linear-gradient(90deg,transparent 0,transparent 2px,rgba(255,255,255,.12) 2px,rgba(255,255,255,.12) 3px,transparent 3px,transparent 5px)}
.card-r1 .money-text{color:#ffe880;text-shadow:0 0 12px rgba(200,160,40,.5)}
.card-r1 .coin-icon{background:linear-gradient(135deg,#f0d050,#c0a030);color:#6a5010}
.card-r1 .dash{border-left-color:rgba(255,255,255,.2)}.card-r1 .hot-tag{color:rgba(255,255,255,.3)}
.card-r2 .row{background:linear-gradient(135deg,#3a3a3a,#8a8a8a 25%,#b8b8b8 50%,#8a8a8a 75%,#3a3a3a);border:2px solid #c0c0c0;box-shadow:0 0 25px rgba(180,180,180,.2),inset 0 1px 0 rgba(255,255,255,.2)}
.card-r2 .badge{background:linear-gradient(180deg,#b0b0b0,#707070);border-right:1px solid rgba(255,255,255,.2)}
.card-r2 .badge .num{color:#f0f0f0}.card-r2 .badge .line{background:rgba(255,255,255,.2)}
.card-r2 .name-text{color:#fff}.card-r2 .id-text{color:rgba(255,255,255,.5)}
.card-r2 .barcode{background:repeating-linear-gradient(90deg,transparent 0,transparent 2px,rgba(255,255,255,.12) 2px,rgba(255,255,255,.12) 3px,transparent 3px,transparent 5px)}
.card-r2 .money-text{color:#e0e0e0;text-shadow:0 0 8px rgba(200,200,200,.3)}
.card-r2 .coin-icon{background:linear-gradient(135deg,#d0d0d0,#a0a0a0);color:#2a2a2a}
.card-r2 .dash{border-left-color:rgba(255,255,255,.2)}.card-r2 .hot-tag{color:rgba(255,255,255,.3)}
.card-r3 .row{background:linear-gradient(135deg,#4a3020,#a06830 25%,#c08040 50%,#a06830 75%,#4a3020);border:2px solid #c09050;box-shadow:0 0 25px rgba(180,120,60,.2),inset 0 1px 0 rgba(255,255,255,.12)}
.card-r3 .badge{background:linear-gradient(180deg,#c08040,#7a4a20);border-right:1px solid rgba(255,255,255,.12)}
.card-r3 .badge .num{color:#fff0e0}.card-r3 .badge .line{background:rgba(255,255,255,.15)}
.card-r3 .name-text{color:#fff}.card-r3 .id-text{color:rgba(255,255,255,.5)}
.card-r3 .barcode{background:repeating-linear-gradient(90deg,transparent 0,transparent 2px,rgba(255,255,255,.12) 2px,rgba(255,255,255,.12) 3px,transparent 3px,transparent 5px)}
.card-r3 .money-text{color:#ffcc80;text-shadow:0 0 8px rgba(180,120,60,.4)}
.card-r3 .coin-icon{background:linear-gradient(135deg,#e0a050,#a07030);color:#3a2000}
.card-r3 .dash{border-left-color:rgba(255,255,255,.15)}.card-r3 .hot-tag{color:rgba(255,255,255,.3)}
.card-normal .row{background:linear-gradient(180deg,#f2f0ea,#e6e4dc);border:1px solid #c8c0a8;box-shadow:inset 0 1px 0 rgba(255,255,255,.6),0 2px 6px rgba(0,0,0,.15)}
.card-normal .badge{background:linear-gradient(180deg,#e8e4dc,#d0ccc0);border-right:1px solid #c0b898}
.card-normal .badge .num{color:#6a5a30}.card-normal .badge .line{background:#c0b090}
.card-normal .name-text{color:#2a2218}.card-normal .id-text{color:#a09070}
.card-normal .barcode{background:repeating-linear-gradient(90deg,transparent 0,transparent 2px,rgba(100,80,40,.12) 2px,rgba(100,80,40,.12) 3px,transparent 3px,transparent 5px)}
.card-normal .money-text{color:#8a6a20}
.card-normal .coin-icon{background:linear-gradient(135deg,#e8d8a0,#c0b080);color:#6a5010;border-color:#a09060}
.card-normal .dash{border-left-color:#c0b090}.card-normal .hot-tag{color:#a09070}
</style></head><body>
<div class="outer-frame">
<div class="header"><span class="h-rank">排名</span><span class="h-name">名称</span><span class="h-money">财富值</span></div>
{% for item in items %}
<div class="card {% if item.rank <= 3 %}card-r{{ item.rank }}{% else %}card-normal{% endif %}">
    <div class="row">
        <div class="badge"><div class="paw-icon">🐾</div><div class="num">{{ item.rank }}</div><div class="line"></div></div>
        <div class="name-section">
            <div class="id-text">NTE ID NO.{{ '%06d' % item.uid_int if item.uid_int else '000000' }}</div>
            <div class="name-text">{{ item.name }}</div>
            <div class="barcode"></div>
        </div>
        <div class="dash"></div>
        <div class="money-section"><div class="coin-icon">¥</div><div class="money-text">{{ item.amount }}</div></div>
        <div class="hot-tag">HOTEE®</div>
    </div>
</div>
{% endfor %}
</div>
</body></html>"""

# 测试数据
items = [
    {"rank": 1, "name": "冲矢昴#7707", "net": 880000, "amount": "880,000", "uid_int": 7707},
    {"rank": 2, "name": "源始九劫大罗无上无上大罗", "net": 550000, "amount": "550,000", "uid_int": 123456},
    {"rank": 3, "name": "ℱ𝒾𝒸𝓀𝓁ℯ★礴郬", "net": 270000, "amount": "270,000", "uid_int": 234567},
    {"rank": 4, "name": "千秋瞳", "net": 220000, "amount": "220,000", "uid_int": 345678},
    {"rank": 5, "name": "AAA汽修丸山彩", "net": 190000, "amount": "190,000", "uid_int": 456789},
    {"rank": 6, "name": "喵喵家族一代目•萤", "net": -270000, "amount": "270,000", "uid_int": 567890},
    {"rank": 7, "name": "狐狸爱吃油豆腐", "net": -350000, "amount": "350,000", "uid_int": 678901},
    {"rank": 8, "name": "电磁银子酱", "net": -380000, "amount": "380,000", "uid_int": 789012},
    {"rank": 9, "name": "瓷胎竹编", "net": -480000, "amount": "480,000", "uid_int": 890123},
    {"rank": 10, "name": "CNYA", "net": -510000, "amount": "510,000", "uid_int": 901234},
    {"rank": 11, "name": "浅青瞳", "net": -730000, "amount": "730,000", "uid_int": 12345},
    {"rank": 12, "name": "伱卟懂莪の悲傷", "net": -780000, "amount": "780,000", "uid_int": 23456},
    {"rank": 13, "name": "厉毒张雪峰", "net": -1190000, "amount": "1,190,000", "uid_int": 34567},
]

try:
    from jinja2 import Template
    html = Template(LEADERBOARD_HTML).render(total=len(items), items=items)
    out = Path(__file__).parent / "test_leaderboard_preview.html"
    out.write_text(html, encoding="utf-8")
    print(f"✅ HTML 已生成: {out}")
except ImportError:
    print("❌ 需要安装 jinja2: pip install jinja2")
except Exception as e:
    print(f"❌ 渲染失败: {e}")
