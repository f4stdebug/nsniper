import itertools
import json
import os
import random
import re
import socket
import string
import sys
import threading
import time
import urllib.parse
from queue import Queue

import requests

try:
    from rich.progress import (
        BarColumn,
        Progress,
        SpinnerColumn,
        TextColumn,
        TimeElapsedColumn,
    )
    HAS_RICH = True
except ImportError:
    HAS_RICH = False


API = "https://guns.lol/api/auth/username/{}/availability"
PAGE = "https://guns.lol/{}"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
LETTERS = string.ascii_lowercase
ALNUM = string.ascii_lowercase + string.digits

R = "\033[0m"
B = "\033[1m"
D = "\033[2m"
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
WHITE = "\033[97m"

FREE_MARKERS = ["username not found", "claim this username"]
CHALLENGE_MARKERS = [
    "just a moment", "cf-chl", "checking your browser",
    "verify you are human", "attention required",
    "enable javascript and cookies", "cf_chl_opt",
]

WORDS = """
love hate dead alive live life death soul mind heart blood bone skin eye tear smile laugh cry
fear hope dream sleep wake night day dawn dusk moon sun star sky cloud rain snow ice fire flame
ember ash smoke wind storm thunder light dark shadow shade ghost spirit angel demon devil god
king queen lord knight sword shield blade arrow spear crown throne castle tower bridge road path
gate door key lock chain wall stone rock cliff cave hill valley river lake ocean sea wave tide
shore sand beach island forest tree leaf root branch seed flower rose thorn grass moss vine wood
metal iron steel gold silver bronze copper glass crystal diamond pearl ruby jade neon pixel cyber
virtual digital analog signal static noise sound voice echo music song melody rhythm beat drum
guitar piano violin chord note tone pitch verse poem story tale myth legend fable lore magic spell
curse hex rune witch wizard mage oracle prophet priest monk saint sinner hero villain rogue thief
assassin hunter warrior ranger druid bard paladin nomad wander traveler stranger friend enemy ally
rival partner lover crush kiss hug touch hold warm cold hot cool chill freeze burn melt flow drift
float fly fall rise climb run walk crawl jump dance sing speak whisper shout scream silence quiet
loud soft gentle harsh cruel kind sweet bitter sour salty spicy fresh stale clean dirty pure holy
evil good bad right wrong true false real fake vision sight blind deaf mute numb pain ache wound
scar heal cure poison venom antidote pill drug drink water wine beer coffee tea milk honey sugar
salt bread meat fruit apple orange lemon grape cherry peach mango berry bean rice corn wheat cake
pie candy cookie cream butter cheese egg fish bird hawk eagle crow raven owl wolf fox bear lion
tiger snake shark whale dolphin horse deer rabbit mouse cat dog rat bat frog moth spider ant bee
bug worm dragon phoenix griffin unicorn mermaid fairy elf dwarf giant titan ogre troll goblin orc
imp sprite nymph kraken serpent drake beak claw fang wing tail horn scale fur feather shell skull
spine rib pulse vein nerve cell atom matter energy plasma quantum gravity orbit planet comet meteor
galaxy nebula cosmos void space time clock hour minute second moment instant forever always never
maybe perhaps certain doubt faith trust truth lie secret mystery enigma riddle puzzle clue answer
question reason logic chaos order balance harmony discord peace war battle fight duel clash strike
defend attack charge march siege raid quest journey voyage route map compass anchor sail ship boat
raft port harbor lighthouse beacon alarm siren bell whistle banner flag emblem crest symbol icon
logo brand mark sign omen seal stamp press print write read book page word letter line script code
cipher binary data file disk drive cache stack queue thread kernel shell root boot loop bug patch
build deploy test debug source branch merge commit push pull fork clone repo node edge graph tree
heap array list map hash value type cast byte bit host server client proxy tunnel socket packet ping
route gateway firewall virus worm trojan admin user guest login token session cookie auth scope role
guild clan team squad crew gang pack herd flock swarm hive nest den lair camp fort base home house
room floor roof window stair yard garden farm field meadow prairie desert jungle swamp marsh glacier
volcano crater canyon gorge ridge peak summit apex zenith abyss pit chasm rift breach crack tear rip
cut slash stab pierce drill dig mine forge craft shape mold bend break crush grind polish shine glow
gleam spark flicker fade vanish appear emerge reveal conceal hide seek find lose keep give take share
trade buy sell cost price worth rich poor wealth fortune luck fate destiny karma blessing prayer wish
desire want need crave yearn long miss remember forget recall imagine create destroy ruin rebuild
restore renew burn burst bloom wither grow shrink expand contract swift fast slow quick rapid steady
calm serene stormy wild tame fierce brave bold shy meek proud humble wise foolish clever smart dull
sharp blunt smooth rough tender soft hard firm good better best pure simple plain fancy ornate vivid
bright pale dark deep shallow wide narrow tall short huge tiny vast grand noble royal humble common
ancient modern future past present eternal mortal divine sacred profane gentle kind
"""

PROXY_RE = re.compile(r"(?:(socks[45]|https?)://)?((?:\d{1,3}\.){3}\d{1,3}):(\d{1,5})")

SOURCES = [
    ("TheSpeedX http", "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt"),
    ("TheSpeedX socks5", "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt"),
    ("ShiftyTR http", "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt"),
    ("proxyscrape http", "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all"),
    ("proxyscrape socks5", "https://api.proxyscrape.com/v2/?request=getproxies&protocol=socks5&timeout=10000&country=all"),
    ("proxyspace http", "https://proxyspace.pro/http.txt"),
    ("proxyspace socks5", "https://proxyspace.pro/socks5.txt"),
    ("openproxylist http", "https://openproxylist.xyz/http.txt"),
    ("sunny9577", "https://sunny9577.github.io/proxy-scraper/proxies.txt"),
]

THREADS = 30
PROXY_THREADS = 300
PROXY_TIMEOUT = 3
CONNECT_TIMEOUT = 3
MAX_LATENCY = 5
RETRIES = 5
FAILS = 3
COOLDOWN = 60
SOURCE_TIMEOUT = 15

OUT = "available.txt"
PROXY_FILE = "proxies.txt"
LOG_FILE = "latest.log"
COOKIE = ""
SYMBOLS = ""

stop = threading.Event()
logfile = None


def strip_ansi(s):
    return re.sub(r"\033\[[0-9;]*m", "", s)


def start_log():
    global logfile
    logfile = open(LOG_FILE, "w", encoding="utf-8")


def say(line, plain=None):
    print(line)
    if logfile:
        logfile.write("[%s] %s\n" % (time.strftime("%H:%M:%S"), plain or strip_ansi(line)))
        logfile.flush()


def ask(prompt, default=""):
    got = input(prompt).strip()
    return got if got else default


def ask_int(prompt, default):
    got = input(prompt).strip()
    if not got:
        return default
    try:
        return int(got)
    except ValueError:
        return default


def ask_yes(prompt, default=False):
    got = input(prompt).strip().lower()
    if not got:
        return default
    return got in ("y", "yes", "д", "да")


def clear():
    os.system("cls" if os.name == "nt" else "clear")


def banner():
    print()
    print(f"{MAGENTA}{B}  n s n i p e r{R}")
    print(f"{D}  guns.lol username finder{R}")
    print()


def headers(html=False):
    h = {
        "User-Agent": UA,
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8" if html else "*/*",
    }
    if COOKIE:
        h["Cookie"] = COOKIE
    if not html:
        h["Referer"] = "https://guns.lol/register?ref=header"
        h["Origin"] = "https://guns.lol"
    return h


def proxy_url(p):
    return {"http": p, "https": p}


def parse_proxy(line, default="http"):
    m = PROXY_RE.search(line)
    if not m:
        return None
    scheme, host, port = m.group(1), m.group(2), m.group(3)
    scheme = scheme or default
    if scheme.startswith("socks"):
        scheme = "socks5" if "5" in scheme else "socks4"
    elif scheme not in ("http", "https"):
        scheme = default
    if not 1 <= int(port) <= 65535:
        return None
    return "%s://%s:%s" % (scheme, host, port)


def read_proxy_file(path):
    if not os.path.exists(path):
        return []
    out, seen = [], set()
    for raw in open(path, "r", encoding="utf-8-sig", errors="ignore"):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        p = parse_proxy(line)
        if p and p not in seen:
            seen.add(p)
            out.append(p)
    return out


def grab_source(name, url):
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=SOURCE_TIMEOUT)
        r.raise_for_status()
    except Exception as e:
        return name, [], str(e)[:50]
    default = "socks5" if "socks5" in name else ("socks4" if "socks4" in name else "http")
    found = [p for p in (parse_proxy(l, default) for l in r.text.splitlines()) if p]
    return name, found, None


def scrape_proxies():
    say(f"{CYAN}[*] Парсю прокси из {len(SOURCES)} источников...{R}", "scrape started")
    results = []
    lock = threading.Lock()

    def worker(name, url):
        _, found, err = grab_source(name, url)
        with lock:
            if err:
                say(f"  {RED}[-]{R} {name:<20} {D}{err}{R}", "source %s FAIL %s" % (name, err))
            else:
                say(f"  {GREEN}[+]{R} {name:<20} {D}{len(found)}{R}", "source %s: %d" % (name, len(found)))
            results.append(found)

    threads = [threading.Thread(target=worker, args=s, daemon=True) for s in SOURCES]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    allp, seen = [], set()
    for found in results:
        for p in found:
            if p not in seen:
                seen.add(p)
                allp.append(p)
    say(f"{CYAN}[i] Собрано уникальных: {WHITE}{len(allp)}{R}", "scraped %d" % len(allp))
    return allp


def proxy_ok(proxy):
    host, _, port = proxy.split("://", 1)[1].rpartition(":")
    try:
        with socket.create_connection((host, int(port)), timeout=CONNECT_TIMEOUT):
            pass
    except Exception:
        return None
    start = time.time()
    try:
        r = requests.get("https://guns.lol/", headers={"User-Agent": UA},
                         proxies=proxy_url(proxy), timeout=(CONNECT_TIMEOUT, PROXY_TIMEOUT))
    except Exception:
        return None
    if r.status_code >= 500:
        return None
    lat = time.time() - start
    if MAX_LATENCY and lat > MAX_LATENCY:
        return None
    return lat


def check_proxies(proxies):
    if not proxies:
        return []
    alive = []
    done = [0]
    lock = threading.Lock()
    q = Queue()
    for p in proxies:
        q.put(p)

    def worker():
        while not stop.is_set():
            try:
                p = q.get_nowait()
            except Exception:
                return
            lat = proxy_ok(p)
            with lock:
                done[0] += 1
                if lat is not None:
                    alive.append((p, lat))

    if HAS_RICH and sys.stdout.isatty():
        with Progress(SpinnerColumn(), TextColumn("[magenta]{task.description}"), BarColumn(),
                      TextColumn("{task.completed}/{task.total}"),
                      TextColumn("[green]живых {task.fields[n]}"), TimeElapsedColumn(),
                      transient=True) as bar:
            task = bar.add_task("Проверка прокси", total=len(proxies), n=0)
            threads = [threading.Thread(target=worker, daemon=True) for _ in range(min(PROXY_THREADS, len(proxies)))]
            for t in threads:
                t.start()
            while any(t.is_alive() for t in threads):
                with lock:
                    bar.update(task, completed=done[0], n=len(alive))
                time.sleep(0.2)
            with lock:
                bar.update(task, completed=len(proxies), n=len(alive))
            for t in threads:
                t.join()
    else:
        threads = [threading.Thread(target=worker, daemon=True) for _ in range(min(PROXY_THREADS, len(proxies)))]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    alive.sort(key=lambda x: x[1])
    say(f"{CYAN}[i] Живых прокси: {GREEN}{len(alive)}{R}/{len(proxies)}", "alive %d/%d" % (len(alive), len(proxies)))
    return [p for p, _ in alive]


def save_proxies(proxies):
    with open(PROXY_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(proxies) + ("\n" if proxies else ""))


class Pool:
    def __init__(self, proxies):
        self.all = list(proxies)
        self.fails = {}
        self.off = {}
        self.lock = threading.Lock()
        self.i = 0

    def get(self):
        now = time.time()
        with self.lock:
            for _ in range(len(self.all)):
                p = self.all[self.i % len(self.all)]
                self.i += 1
                if self.off.get(p, 0) <= now:
                    return p
            return None

    def ok(self, p):
        with self.lock:
            self.fails[p] = 0
            self.off[p] = 0

    def fail(self, p):
        with self.lock:
            self.fails[p] = self.fails.get(p, 0) + 1
            if self.fails[p] >= FAILS:
                self.off[p] = time.time() + COOLDOWN

    def alive(self):
        now = time.time()
        with self.lock:
            return sum(1 for p in self.all if self.off.get(p, 0) <= now)


def is_challenge(text, code):
    low = text.lower()
    if any(m in low for m in CHALLENGE_MARKERS):
        return True
    if code in (403, 503) and ("challenge" in low or "cloudflare" in low or "cf-" in low):
        return True
    return False


def page_state(text):
    low = text.lower()
    if any(m in low for m in FREE_MARKERS):
        return "free"
    if any(m in low for m in CHALLENGE_MARKERS):
        return "challenge"
    return "taken"


def build_names(modes, limit, opts):
    pool, seen = [], set()

    def add(items, do_shuffle=True):
        items = list(items)
        if do_shuffle:
            random.shuffle(items)
        for n in items:
            if n not in seen:
                seen.add(n)
                pool.append(n)

    extra = opts.get("symbols", "")
    cs = ALNUM + extra

    def numbers():
        return [str(i) for i in range(1, 101)]

    def short():
        return ["".join(c) for r in (1, 2, 3) for c in itertools.product(cs, repeat=r)]

    def two():
        return ["".join(c) for c in itertools.product(cs, repeat=2)]

    def combos():
        return ["".join(c) for c in itertools.product(cs, repeat=3)]

    def repeaters():
        return ["".join([ch] * r) for r in (2, 3, 4) for ch in LETTERS]

    def words():
        return WORDS.split()

    def custom():
        out = []
        if opts.get("digits"):
            out += [str(i) for i in range(1, 10 ** opts["digits"])]
        if opts.get("letters"):
            out += ["".join(c) for r in range(1, opts["letters"] + 1)
                    for c in itertools.product(LETTERS + extra, repeat=r)]
        if opts.get("alnum"):
            out += ["".join(c) for r in range(1, opts["alnum"] + 1)
                    for c in itertools.product(cs, repeat=r)]
        if opts.get("with_words"):
            out += WORDS.split()
        return out

    if opts.get("extra_names"):
        add(opts["extra_names"], do_shuffle=False)

    makers = {"numbers": numbers, "short": short, "two": two, "combos": combos,
              "repeaters": repeaters, "words": words, "custom": custom}

    order = []
    if "beauty" in modes:
        order += ["numbers", "short", "words"]
    for m in modes:
        if m != "beauty" and m not in order:
            order.append(m)

    for m in order:
        if m in makers:
            add(makers[m]())

    if limit:
        pool = pool[:limit]
    return pool


VOWELS = "aeiouy"
LEET = {"0": "o", "1": "l", "3": "e", "4": "a", "5": "s", "6": "g", "7": "t", "8": "b", "9": "g"}


def beauty(name):
    n = len(name)
    letters = sum(c.isalpha() for c in name)
    digits = sum(c.isdigit() for c in name)
    s = (12 if n == 3 else 8 if n == 2 else 4)
    s += letters * 3 - max(0, digits - 1) * 2
    s += 4 if name[0].isalpha() else -1
    if any(c in VOWELS for c in name):
        s += 5
    mapped = "".join(LEET.get(c, c) for c in name)
    if digits and all(c.isalpha() or c in LEET for c in name):
        s += 5
        if any(v in mapped for v in VOWELS):
            s += 5
        s += sum(1 for a, b in zip(mapped, mapped[1:]) if (a in VOWELS) != (b in VOWELS))
    if n == 3 and digits == 1 and letters == 2 and not any(v in mapped for v in VOWELS):
        s += 8
    if name[0].isdigit() and name[-1].isdigit():
        s += 6
    if len(set(name)) == 1:
        s -= 6
    if any(d in name for d in "975"):
        s += 3
    if any(d in name for d in "36"):
        s += 2
    return s


def check_name(name, pool):
    for attempt in range(RETRIES + 1):
        if stop.is_set():
            return "stop"
        proxy = None
        if pool:
            proxy = pool.get()
            if proxy is None:
                for _ in range(20):
                    time.sleep(0.5)
                    if pool.alive() > 0:
                        break
                else:
                    return "noprox"
                continue
        try:
            r = requests.get(API.format(urllib.parse.quote(name, safe="")), headers=headers(),
                             proxies=proxy_url(proxy) if proxy else None,
                             timeout=(CONNECT_TIMEOUT, PROXY_TIMEOUT) if proxy else (10, 10))
        except requests.RequestException:
            if proxy:
                pool.fail(proxy)
            continue

        if is_challenge(r.text, r.status_code):
            if proxy:
                pool.fail(proxy)
            continue
        if r.status_code == 429:
            if proxy:
                pool.fail(proxy)
            continue
        if r.status_code != 200:
            continue

        if proxy:
            pool.ok(proxy)

        try:
            data = json.loads(r.text)
        except Exception:
            data = None

        if data is not None:
            if data.get("available") is True:
                return "free"
            err = (data.get("error") or "").lower()
            if "valid username" in err:
                return "invalid"
            if "too many" in err or "rate" in err:
                if proxy:
                    pool.fail(proxy)
                continue
            return "taken"

        state = page_state(r.text)
        if state == "free":
            return "free"
        if state == "challenge":
            if proxy:
                pool.fail(proxy)
            continue
        return "taken"
    return "error"


def run_checks(names, pool):
    total = len(names)
    q = Queue()
    for n in names:
        q.put(n)
    free, taken, bad, err = [], [0], [0], [0]
    done = [0]
    lock = threading.Lock()

    def worker():
        while not stop.is_set():
            try:
                name = q.get_nowait()
            except Exception:
                return
            status = check_name(name, pool)
            with lock:
                if status == "stop":
                    return
                if status == "noprox":
                    continue
                done[0] += 1
                if status == "free":
                    free.append(name)
                    say(f"{GREEN}{B}[+]{R} {GREEN}{name}{R} {D}свободен{R}", "[+] %s" % name)
                    with open(OUT, "a", encoding="utf-8") as f:
                        f.write(name + "\n")
                elif status == "taken":
                    taken[0] += 1
                    if not opts_hide:
                        say(f"{RED}[-]{R} {name} {D}занят{R}", "[-] %s" % name)
                elif status == "invalid":
                    bad[0] += 1
                    say(f"{YELLOW}[?]{R} {name} {D}невалидный{R}", "[?] %s" % name)
                else:
                    err[0] += 1
                    say(f"{BLUE}[!]{R} {BLUE}{name}{R}", "[!] %s" % name)

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(min(THREADS, total))]
    for t in threads:
        t.start()
    try:
        for t in threads:
            while t.is_alive():
                t.join(0.3)
                if stop.is_set():
                    break
    except KeyboardInterrupt:
        stop.set()

    print()
    say(f"{B}Итог:{R} проверено {done[0]}  {GREEN}свободно {len(free)}{R}  "
        f"{RED}занято {taken[0]}{R}  {YELLOW}невалид {bad[0]}{R}  {BLUE}ошибок {err[0]}{R}",
        "summary: %d free %d taken %d invalid %d errors" % (len(free), taken[0], bad[0], err[0]))
    if free:
        print(f"{GREEN}{B}Свободные:{R} {', '.join(free)}")
        print(f"{CYAN}Сохранено в {OUT}{R}")


opts_hide = False


def pick_modes():
    menu = [
        ("beauty", "цифры 1-100 + короткие 1-3 + слова"),
        ("numbers", "числа 1..100"),
        ("short", "1-3 символа (буквы+цифры)"),
        ("two", "ровно 2 символа (буквы+цифры)"),
        ("words", "словарь слов"),
        ("repeaters", "aa / aaa / aaaa"),
        ("combos", "ровно 3 символа (a-z0-9)"),
        ("custom", "вручную — длина каждого"),
        ("file", "список юзов из файла"),
    ]
    print(f"{B}Что генерим:{R}")
    for i, (m, info) in enumerate(menu, 1):
        print(f"  {CYAN}{i}{R}) {m:<10} {D}{info}{R}")
    raw = input(f"Номера через запятую [{CYAN}1{R}]: ").strip() or "1"
    names = [m for m, _ in menu]
    picked = []
    for tok in raw.replace(" ", ",").split(","):
        tok = tok.strip()
        if tok.isdigit() and 1 <= int(tok) <= len(menu):
            picked.append(menu[int(tok) - 1][0])
        elif tok in names:
            picked.append(tok)
    return picked or ["beauty"]


def do_search():
    global opts_hide
    clear()
    banner()
    modes = pick_modes()
    opts = {}

    if "custom" in modes:
        print(f"{D}custom (0 = выключить){R}")
        opts["digits"] = ask_int("  цифры до N знаков [3]: ", 3)
        opts["letters"] = ask_int("  буквы до N символов [3]: ", 3)
        opts["alnum"] = ask_int("  буквы+цифры до N символов [3]: ", 3)
        opts["with_words"] = ask_yes("  добавить словарь? [y/N]: ")

    extra = None
    if "file" in modes:
        path = ask("Путь к файлу: ")
        if path and os.path.exists(path):
            raw = open(path, encoding="utf-8-sig", errors="ignore").read()
            extra = [x for x in re.split(r"[,\s]+", raw) if x and not x.startswith("#")]
    if extra:
        opts["extra_names"] = extra

    sym = ask("Доп. символы (Enter = нет, напр. \"._\"): ")
    if sym:
        opts["symbols"] = sym

    limit = ask_int("Лимит кандидатов (0 = все) [0]: ", 0)
    globals()["THREADS"] = max(1, ask_int(f"Потоков [{THREADS}]: ", THREADS))
    globals()["OUT"] = ask(f"Файл свободных [{OUT}]: ", OUT)
    opts_hide = ask_yes("Скрывать занятые? [y/N]: ")

    names = build_names(modes, limit, opts)
    if not names:
        say(f"{RED}Пусто, нечего проверять{R}", "no candidates")
        return

    pool = prepare_proxies()
    if pool is None and not ask_yes("Живых прокси нет. Работать напрямую? [y/N]: "):
        return

    if os.path.exists(OUT):
        os.remove(OUT)
    if pool:
        say(f"{CYAN}[i] Прокси {pool.alive()}, кандидатов {len(names)}, потоков {THREADS}{R}", "start")
    else:
        say(f"{CYAN}[i] Напрямую, кандидатов {len(names)}, потоков {THREADS}{R}", "start direct")
    print()
    run_checks(names, pool)


def prepare_proxies():
    proxies = read_proxy_file(PROXY_FILE)
    if proxies:
        say(f"{CYAN}[i] Загружено прокси: {len(proxies)} ({PROXY_FILE}){R}", "loaded %d proxies" % len(proxies))
        if ask_yes("Проверить прокси перед поиском? [Y/n]: ", True):
            proxies = check_proxies(proxies)
    if not proxies:
        if ask_yes("Парсить прокси автоматически? [Y/n]: ", True):
            proxies = check_proxies(scrape_proxies())
            if proxies:
                save_proxies(proxies)
                say(f"{CYAN}[i] Живые прокси сохранены в {PROXY_FILE}{R}", "saved proxies")
    return Pool(proxies) if proxies else None


def do_scrape():
    clear()
    banner()
    proxies = check_proxies(scrape_proxies())
    if proxies:
        save_proxies(proxies)
        say(f"{GREEN}[ok]{R} {len(proxies)} живых прокси в {PROXY_FILE}", "saved %d proxies" % len(proxies))
    else:
        say(f"{RED}Живых прокси нет{R}", "no alive proxies")


def do_sort():
    clear()
    banner()
    proxies = read_proxy_file(PROXY_FILE)
    if not proxies:
        say(f"{RED}Нет {PROXY_FILE}{R}", "no proxy file")
        return
    alive = check_proxies(proxies)
    save_proxies(alive)
    say(f"{GREEN}[ok]{R} {PROXY_FILE} отсортирован: {len(alive)} живых", "sorted %d" % len(alive))


def do_rank():
    clear()
    banner()
    path = ask("Файл с никами [available.txt]: ", "available.txt")
    if not os.path.exists(path):
        say(f"{RED}Нет файла {path}{R}", "no file")
        return
    raw = open(path, encoding="utf-8-sig", errors="ignore").read()
    names = [x for x in re.split(r"[,\s]+", raw) if x and not x.startswith("#")]
    top = ask_int("Сколько показать [30]: ", 30)
    names.sort(key=lambda x: (-beauty(x), x))
    print(f"\n{B}Топ {top} по красоте (из {len(names)}):{R}")
    for i, n in enumerate(names[:top], 1):
        print(f"  {CYAN}{i:>3}{R}) {GREEN}{n}{R} {D}{beauty(n)}{R}")
    with open("available_ranked.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(names) + "\n")
    say(f"{CYAN}Полный рейтинг -> available_ranked.txt{R}", "rank saved")


def main():
    global COOKIE
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if os.name == "nt":
        os.system("")
    start_log()

    ck = ask_yes("Подставить свою куку guns.lol (для премиум-символов)? [y/N]: ")
    if ck:
        COOKIE = ask("Cookie: ")

    while True:
        clear()
        banner()
        print(f"{B}Меню:{R}")
        print(f"  {CYAN}1{R}) Искать ники")
        print(f"  {CYAN}2{R}) Спарсить прокси")
        print(f"  {CYAN}3{R}) Отсортировать прокси (proxies.txt)")
        print(f"  {CYAN}4{R}) Оценить найденные ники по красоте")
        print(f"  {CYAN}0{R}) Выход")
        choice = ask("Выбор [1]: ", "1")
        try:
            if choice == "0":
                break
            elif choice == "1":
                do_search()
            elif choice == "2":
                do_scrape()
            elif choice == "3":
                do_sort()
            elif choice == "4":
                do_rank()
        except KeyboardInterrupt:
            stop.set()
            print()
            say(f"{YELLOW}Прервано{R}", "interrupted")
            stop.clear()
        except EOFError:
            break
        try:
            input(f"\n{D}Enter...{R}")
        except EOFError:
            break

    if logfile:
        logfile.close()


if __name__ == "__main__":
    main()
