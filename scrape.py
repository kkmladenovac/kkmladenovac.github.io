#!/usr/bin/env python3
"""Preuzima raspored i tabelu grupe sa ksb.rs i upisuje matches.json."""
import json, re, sys, datetime
import requests
from bs4 import BeautifulSoup

URL = "https://www.ksb.rs/takmicenje1232/"
OUT = "matches.json"
GROUP = "Pioniri, Beogradska liga U14, grupa 1"

MAP = {}
for pair in ("а:a б:b в:v г:g д:d ђ:đ е:e ж:ž з:z и:i ј:j к:k л:l љ:lj м:m н:n њ:nj "
             "о:o п:p р:r с:s т:t ћ:ć у:u ф:f х:h ц:c ч:č џ:dž ш:š").split():
    c, l = pair.split(":")
    MAP[c] = l
    MAP[c.upper()] = l.capitalize()

def lat(s):
    return "".join(MAP.get(ch, ch) for ch in s)

def get_text():
    r = requests.get(URL, timeout=30, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Accept-Language": "sr,en;q=0.8"})
    r.raise_for_status()
    soup = BeautifulSoup(r.content, "html.parser")
    for t in soup(["script", "style"]):
        t.decompose()
    text = re.sub(r"\s+", " ", soup.get_text(" "))
    return text.split("©")[0]

ROUND_RE = re.compile(r"(\d+)\.\s*коло\s+(\d{2}\.\d{2}\.\d{4})", re.I)
ST_RE = re.compile(r"(\d{1,2})\.\s+(.{2,60}?)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+):(\d+)\s+(\d+)"
                   r"(?=\s+\d{1,2}\.\s|\s*$)")

def parse_standings(head):
    m = re.search(r"Група\s*\d+", head)
    seg = head[m.start():] if m else head
    return [dict(pos=int(x[1]), team=x[2].strip(), p=int(x[3]), w=int(x[4]), l=int(x[5]),
                 pf=int(x[6]), pa=int(x[7]), pts=int(x[8])) for x in ST_RE.finditer(seg)]

def parse_block(block, teams):
    def suffix(s):
        for t in teams:
            if s.endswith(t):
                return t
    def prefix(s):
        for t in teams:
            if s.startswith(t):
                return t
    bye = None
    k = block.find("слободна екипа")
    if k != -1:
        pre = block[:k].rstrip(" -–").rstrip()
        bye = suffix(pre)
        block = pre[:len(pre) - len(bye)] if bye else pre
    matches = []
    for seg in re.split(r"\b\d{6}\b", block):
        seg = re.sub(r"[^\w\)]+$", "", seg.strip())
        if " : " not in seg:
            continue
        score = None
        m = re.match(r"^(.*\S)\s+(\d{1,3})\s*:\s*(\d{1,3})$", seg)
        if m:
            seg, score = m.group(1), f"{m.group(2)}:{m.group(3)}"
        home_s, away_s = seg.split(" : ", 1)
        home, away = suffix(home_s.strip()), prefix(away_s.strip())
        if not home or not away:
            print("Preskacem:", seg, file=sys.stderr)
            continue
        matches.append(dict(home=home, away=away, score=score))
    return matches, bye

def main():
    text = get_text()
    first = ROUND_RE.search(text)
    if not first:
        sys.exit("Nisu pronadjena kola na stranici")
    standings = parse_standings(text[:first.start()])
    teams = sorted({s["team"] for s in standings}, key=len, reverse=True)
    if len(teams) < 4:
        sys.exit("Tabela nije prepoznata")
    parts = ROUND_RE.split(text[first.start():])
    rounds = {}
    for i in range(1, len(parts) - 2, 3):
        num, date, block = int(parts[i]), parts[i + 1], parts[i + 2]
        matches, bye = parse_block(block, teams)
        new = dict(round=num, date=date, matches=matches, bye=bye)
        old = rounds.get(num)
        if not old or sum(1 for m in matches if m["score"]) >= sum(1 for m in old["matches"] if m["score"]):
            rounds[num] = new
    if len(rounds) < 5:
        sys.exit("Premalo kola prepoznato")

    def conv(o):
        if isinstance(o, dict):
            return {k: conv(v) for k, v in o.items()}
        if isinstance(o, list):
            return [conv(v) for v in o]
        return lat(o) if isinstance(o, str) and k_is_text(o) else o
    def k_is_text(s):
        return not re.fullmatch(r"[\d.:]+", s)

    data = dict(updated=datetime.date.today().isoformat(), group=GROUP,
                standings=conv(standings), rounds=conv([rounds[n] for n in sorted(rounds)]))
    try:
        old = json.load(open(OUT, encoding="utf-8"))
        a = {k: v for k, v in old.items() if k != "updated"}
        b = {k: v for k, v in data.items() if k != "updated"}
        if a == b:
            print("Nema promena")
            return
    except FileNotFoundError:
        pass
    json.dump(data, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("Upisano:", len(rounds), "kola")

main()
