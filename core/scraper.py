import json
import random
import re
import subprocess
import time
from typing import Optional
from urllib.parse import quote

HARNESS_BIN = "/opt/miniconda3/envs/fa-matching/bin/browser-harness"


def _get_chrome_cookies() -> list:
    try:
        import browser_cookie3
        return [
            {"name": c.name, "value": c.value, "domain": c.domain,
             "path": c.path or "/", "secure": bool(c.secure),
             "httpOnly": False, "expires": int(c.expires) if c.expires else -1}
            for c in browser_cookie3.chrome(domain_name="itjuzi.com")
        ]
    except Exception:
        return []


def _inject_cookies_script(cookies: list) -> str:
    return f"""
cookies = {repr(cookies)}
cdp("Network.enable")
for c in cookies:
    try:
        args = dict(name=c["name"], value=c["value"], domain=c["domain"],
                    path=c.get("path","/"), secure=c.get("secure",False),
                    httpOnly=c.get("httpOnly",False))
        if c.get("expires",-1) > 0:
            args["expires"] = c["expires"]
        cdp("Network.setCookie", **args)
    except Exception:
        pass
"""


def _is_valid_record(rec: dict) -> bool:
    """过滤明显不是投资事件的行（新闻区块、统计数字等）。"""
    date_re = re.compile(r'^\d{4}-\d{2}-\d{2}$')
    stage_kw = re.compile(r'轮|IPO|三板|挂牌|上市|战略|种子|天使')
    # sector 是日期 → 新闻动态区块误命中
    if date_re.match(rec.get("sector", "")):
        return False
    # amount 是日期 → 同上
    if date_re.match(rec.get("amount", "")):
        return False
    # company_name 超长 → 新闻标题
    if len(rec.get("company_name", "")) > 20:
        return False
    # stage 既不含轮次关键词也不含"未透露/未披露" → 统计数字或其他垃圾
    stage = rec.get("stage", "")
    if stage and not stage_kw.search(stage) and not re.search(r'透露|披露', stage):
        return False
    return True


def _parse_sectors_from_text(lines: list) -> str:
    """从页面文本行中找"关注领域"段落，提取后续标签。"""
    for i, line in enumerate(lines):
        if line == "关注领域" and i + 1 < len(lines):
            next_line = lines[i + 1]
            tags = [t.strip() for t in re.split(r'\s+', next_line) if t.strip()]
            # 过滤掉明显不是标签的长文本
            tags = [t for t in tags if 1 < len(t) <= 15]
            if tags:
                return ",".join(tags)
    return ""


def _parse_investment_records(lines: list) -> list:
    """从页面文本行中解析投资事件记录。"""
    records = []
    i = 0
    date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}$')
    while i < len(lines):
        if date_pattern.match(lines[i]):
            # 格式: 日期 / 公司名 / 行业 / 轮次 / 金额 / 详情
            if i + 4 < len(lines):
                rec = {
                    "invested_date": lines[i],
                    "company_name":  lines[i+1] if i+1 < len(lines) else "",
                    "sector":        lines[i+2] if i+2 < len(lines) else "",
                    "stage":         lines[i+3] if i+3 < len(lines) else "",
                    "amount":        lines[i+4] if i+4 < len(lines) else "",
                }
                # 跳过「详情」行
                skip = 5
                if i+5 < len(lines) and lines[i+5] == "详情":
                    skip = 6
                records.append(rec)
                i += skip
                continue
        i += 1
    return [r for r in records if _is_valid_record(r)]


def _parse_company_funding_from_text(lines: list) -> list:
    """从公司详情页文本中解析投融资记录。"""
    rounds = []
    date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}$')
    noise = {"反馈", "举报", "纠错", "更多", "展开", "收起", "详情", "查看"}
    i = 0
    while i < len(lines):
        if not date_pattern.match(lines[i]):
            i += 1
            continue
        round_date = lines[i]
        round_type = lines[i + 1].strip() if i + 1 < len(lines) else ""
        amount = lines[i + 2].strip() if i + 2 < len(lines) else ""
        investors = []
        j = i + 3
        while j < len(lines):
            line = lines[j].strip()
            if date_pattern.match(line) or line == "反馈":
                break
            if line and line not in noise and len(line) <= 30:
                investors.append(line)
            j += 1
        rounds.append({
            "round_date": round_date,
            "round_type": round_type,
            "amount": amount,
            "investors": ",".join(investors),
        })
        i = j
    return rounds


def scrape_company_funding(company_name: str, state_path: str) -> list:
    """搜索 IT桔子 /company/ 页面，提取该公司的历史融资记录。"""
    time.sleep(random.uniform(0.5, 1.5))
    try:
        cookies = _get_chrome_cookies()
        js_company_links = json.dumps(
            'Array.from(document.querySelectorAll("a[href]"))'
            '.map(l=>({href:l.getAttribute("href"),text:l.innerText.trim()}))'
            '.filter(x=>x.href&&/\\/company\\/\\d+/.test(x.href)&&x.text&&x.text.length>1)'
        )
        js_text = json.dumps("document.body.innerText")

        script = f"""
import json, time, re
{_inject_cookies_script(cookies)}
ensure_real_tab()

name = {json.dumps(company_name)}
goto_url("https://www.itjuzi.com/search?data=" + {json.dumps(quote(company_name))})
wait_for_network_idle(timeout=15)
time.sleep(3)

links = js({js_company_links})
detail_url = None
for l in (links or []):
    href = l.get("href","")
    text = l.get("text","")
    if re.search(r'/company/\\d+', href):
        if name in text or len(links) == 1:
            detail_url = "https://www.itjuzi.com" + href if href.startswith("/") else href
            break
if not detail_url and links:
    href = links[0].get("href","")
    if href:
        detail_url = "https://www.itjuzi.com" + href if href.startswith("/") else href

if not detail_url:
    print(json.dumps({{"rounds":[],"ok":False}}))
else:
    goto_url(detail_url)
    wait_for_network_idle(timeout=15)
    time.sleep(3)

    for _ in range(20):
        js("window.scrollBy(0,600)")
        time.sleep(0.15)
    wait_for_network_idle(timeout=10)
    time.sleep(2)

    page_text = js({js_text}) or ""
    print(json.dumps({{"rounds":[], "page_text": page_text, "ok":True}}, ensure_ascii=False))
"""
        result = subprocess.run(
            [HARNESS_BIN, "-c", script],
            capture_output=True, text=True, timeout=180,
        )
        if result.returncode != 0:
            print(f"[scraper] company funding 错误: {result.stderr[-300:]}")
            return []

        data = None
        for line in reversed(result.stdout.strip().splitlines()):
            line = line.strip()
            if line.startswith("{"):
                try:
                    data = json.loads(line)
                    break
                except Exception:
                    continue

        if not data or not data.get("ok"):
            return []

        page_text = data.get("page_text", "")
        lines = [l.strip() for l in page_text.split("\n") if l.strip()]
        return _parse_company_funding_from_text(lines)

    except Exception as e:
        print(f"[scraper] scrape_company_funding 失败 {company_name}: {e}")
        return []


def scrape_institution_investments(name: str, state_path: str) -> dict:
    """用 browser-harness 连接本地 Chrome 抓取 IT桔子机构数据。"""
    time.sleep(random.uniform(0.5, 1.5))
    try:
        cookies = _get_chrome_cookies()
        js_links = json.dumps(
            'Array.from(document.querySelectorAll("a[href]"))'
            '.map(l=>({href:l.getAttribute("href"),text:l.innerText.trim()}))'
            '.filter(x=>x.href&&x.href.includes("/investfirm/")&&x.text&&x.text.length>1)'
        )
        js_nuxt = json.dumps("JSON.stringify(window.__NUXT__||{})")
        js_text = json.dumps("document.body.innerText")
        js_event_links = json.dumps(
            'Array.from(document.querySelectorAll(\'a[href*="investevent/"]\'))'
            '.filter(a=>/investevent\\/\\d+/.test(a.getAttribute("href")))'
            '.map(a=>a.getAttribute("href"))'
        )
        # 从 DOM 中直接提取"关注领域"标签（通过 TreeWalker 定位文本节点后取兄弟元素）
        js_sectors = json.dumps(
            '(function(){'
            '  var items=[];'
            '  var walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT,null,false);'
            '  var node;'
            '  while(node=walker.nextNode()){'
            '    if(node.textContent.trim()==="关注领域"){'
            '      var labelEl=node.parentElement;'
            '      var sibling=labelEl.nextElementSibling;'
            '      if(sibling){'
            '        sibling.querySelectorAll("span,a").forEach(function(el){'
            '          if(el.children.length===0){'
            '            var t=(el.textContent||"").trim();'
            '            if(t&&t.length>1&&t.length<=15) items.push(t);'
            '          }'
            '        });'
            '      }'
            '      if(items.length===0){'
            '        var container=labelEl.parentElement;'
            '        for(var d=0;d<4&&items.length===0;d++){'
            '          container.querySelectorAll("span,a").forEach(function(el){'
            '            if(el.children.length===0){'
            '              var t=(el.textContent||"").trim();'
            '              if(t&&t.length>1&&t.length<=15&&t!=="关注领域") items.push(t);'
            '            }'
            '          });'
            '          container=container.parentElement;'
            '          if(!container) break;'
            '        }'
            '      }'
            '      break;'
            '    }'
            '  }'
            '  return [...new Set(items)];'
            '})()'
        )

        script = f"""
import json, time, re
{_inject_cookies_script(cookies)}
ensure_real_tab()

# Step 1: 搜索机构
name = {json.dumps(name)}
goto_url("https://www.itjuzi.com/search?data=" + {json.dumps(quote(name))})
wait_for_network_idle(timeout=15)
time.sleep(3)

links = js({js_links})
detail_url = None
for l in (links or []):
    href = l.get("href","")
    text = l.get("text","")
    if name in text and href.startswith("/investfirm/") and href[12:].isdigit():
        detail_url = "https://www.itjuzi.com" + href
        break
if not detail_url:
    for l in (links or []):
        href = l.get("href","")
        if href.startswith("/investfirm/") and href[12:].isdigit():
            detail_url = "https://www.itjuzi.com" + href
            break

if not detail_url:
    print(json.dumps({{"institution":{{}}, "records":[]}}))
else:
    # Step 2: 详情页
    goto_url(detail_url)
    wait_for_network_idle(timeout=15)
    time.sleep(3)

    # Step 3: 滚动加载投资事件
    for _ in range(30):
        js("window.scrollBy(0,600)")
        time.sleep(0.15)
    wait_for_network_idle(timeout=10)
    time.sleep(3)

    # Step 4: 提取机构基本信息
    nuxt_str = js({js_nuxt})
    inst_info = {{}}
    try:
        nd = json.loads(nuxt_str)
        d = nd.get("data",[{{}}])[0].get("data",{{}})
        inst_info = {{
            "website":          d.get("url",""),
            "founded_year":     str(d.get("year","")) if d.get("year") else "",
            "aum":              (str(d.get("capital_rmb",""))+"亿人民币") if d.get("capital_rmb") else "",
            "key_partners":     ",".join(g.get("name","") for g in (d.get("gp_info") or []) if g.get("name")),
            "preferred_sectors":    ",".join(c2.get("name","") for c2 in (d.get("invse_cat_list") or []) if c2.get("name")),
            "preferred_stages":     ",".join(r2.get("name","").split("(")[0] for r2 in (d.get("investment_round") or [])),
        }}
    except Exception:
        pass

    # Step 5: 提取投资事件URL列表
    event_urls = (js({js_event_links}) or [])

    # Step 6: 从DOM提取关注领域标签（NUXT备选）
    dom_sectors = (js({js_sectors}) or [])

    # Step 7: 提取页面文本（含投资事件表格）
    page_text = js({js_text})
    print(json.dumps({{"institution":inst_info,"page_text":(page_text or ""),"event_urls":event_urls,"dom_sectors":dom_sectors,"ok":True}}, ensure_ascii=False))
"""
        result = subprocess.run(
            [HARNESS_BIN, "-c", script],
            capture_output=True, text=True, timeout=180,
        )
        if result.returncode != 0:
            print(f"[scraper] harness 错误: {result.stderr[-500:]}")
            return {"institution": {}, "records": []}

        data = None
        for line in reversed(result.stdout.strip().splitlines()):
            line = line.strip()
            if line.startswith("{"):
                try:
                    data = json.loads(line)
                    break
                except Exception:
                    continue

        if not data:
            return {"institution": {}, "records": []}

        inst_info = data.get("institution", {})
        page_text = data.get("page_text", "")
        event_urls = data.get("event_urls", [])
        dom_sectors = data.get("dom_sectors", [])

        # 从页面文本解析投资记录
        lines = [l.strip() for l in page_text.split("\n") if l.strip()]
        records = _parse_investment_records(lines)

        # 若 NUXT 未给出 preferred_sectors，用 DOM 提取的标签补全
        if not inst_info.get("preferred_sectors"):
            if dom_sectors:
                inst_info["preferred_sectors"] = ",".join(dom_sectors)
            else:
                inst_info["preferred_sectors"] = _parse_sectors_from_text(lines)

        # 将 event_url 按顺序附加到记录上
        for i, rec in enumerate(records):
            if i < len(event_urls):
                url = event_urls[i]
                rec["event_url"] = ("https://www.itjuzi.com" + url
                                    if url.startswith("/") else url)

        return {"institution": inst_info, "records": records}

    except Exception as e:
        print(f"[scraper] 爬取失败 {name}: {e}")
        return {"institution": {}, "records": []}


def scrape_event_description(event_url: str) -> str:
    """抓取 investevent 详情页，返回公司简介文本。"""
    time.sleep(random.uniform(0.3, 0.8))
    try:
        cookies = _get_chrome_cookies()
        js_nuxt = json.dumps("JSON.stringify(window.__NUXT__||{})")
        js_text = json.dumps("document.body.innerText")

        script = f"""
import json, time
{_inject_cookies_script(cookies)}
ensure_real_tab()
goto_url({json.dumps(event_url)})
wait_for_network_idle(timeout=15)
time.sleep(2)

desc = ""
nuxt_str = js({js_nuxt})
try:
    nd = json.loads(nuxt_str)
    d = nd.get("data",[{{}}])[0].get("data",{{}})
    # 尝试常见字段名
    for key in ("comp_intro","introduce","intro","brief","description","company_intro","startup_intro"):
        v = d.get(key,"")
        if v and len(v) > 20:
            desc = v
            break
    # 也尝试嵌套 company 子对象
    if not desc:
        comp = d.get("company",{{}}) or d.get("startup",{{}})
        for key in ("intro","introduce","description","brief"):
            v = comp.get(key,"") if isinstance(comp,dict) else ""
            if v and len(v) > 20:
                desc = v
                break
except Exception:
    pass

if not desc:
    page_text = js({js_text}) or ""
    for line in page_text.split("\\n"):
        line = line.strip()
        if len(line) > 50 and sum(1 for c in line if "\\u4e00"<=c<="\\u9fff") > 10:
            desc = line
            break

print(json.dumps({{"desc": desc}}, ensure_ascii=False))
"""
        result = subprocess.run(
            [HARNESS_BIN, "-c", script],
            capture_output=True, text=True, timeout=60,
        )
        for line in reversed(result.stdout.strip().splitlines()):
            line = line.strip()
            if line.startswith("{"):
                try:
                    return json.loads(line).get("desc", "")
                except Exception:
                    continue
        return ""
    except Exception as e:
        print(f"[scraper] 抓取事件描述失败 {event_url}: {e}")
        return ""


def get_itjuzi_url(name: str) -> Optional[str]:
    try:
        cookies = _get_chrome_cookies()
        js_links = json.dumps(
            'Array.from(document.querySelectorAll("a[href]"))'
            '.map(l=>({href:l.getAttribute("href"),text:l.innerText.trim()}))'
            '.filter(x=>x.href&&x.href.includes("/investfirm/")&&x.text)'
        )
        script = f"""
import time, re, json
{_inject_cookies_script(cookies)}
goto_url("https://www.itjuzi.com/search?data=" + {json.dumps(quote(name))})
wait_for_network_idle(timeout=15)
time.sleep(3)
links = js({js_links})
name = {json.dumps(name)}
result = None
for l in (links or []):
    href = l.get("href","")
    text = l.get("text","")
    if name in text and href.startswith("/investfirm/") and href[12:].isdigit():
        result = "https://www.itjuzi.com" + href
        break
print(result or "")
"""
        r = subprocess.run([HARNESS_BIN, "-c", script], capture_output=True, text=True, timeout=60)
        lines = r.stdout.strip().splitlines()
        url = lines[-1].strip() if lines else ""
        return url if url.startswith("https://www.itjuzi.com/investfirm/") else None
    except Exception:
        return None
