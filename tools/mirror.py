"""Mirror the Fischer 2023 IMC data (EBI spora release and Zenodo record 7494509, both CC BY 4.0) into release assets of this repository,
in tar batches under 1.9 GB, with a manifest of every file (size) and every asset (size, SHA-256). Resumable: assets already in the
release are skipped."""
import os, re, sys, json, time, tarfile, hashlib, subprocess, shutil, urllib.request, urllib.parse

S3 = "https://livingobjects.ebi.ac.uk/bioimaging-01-pub"
DS = "fischer2023multiplex"
TAG = os.environ.get("RELEASE_TAG", "fischer-data-v1")
WORK = os.environ.get("WORK", "/mnt/work")
MAX = int(1.85e9)
ZENODO = [("SingleCellExperiment_IMC.rds", 1006608177, "5165c9cfdc53864214c60224d3df271b"),
          ("Patient_metadata.csv", 556027, "4bb16e1f817f538a3776a7220c1ed7cb"),
          ("Panel.csv", 1945, "c7c0267ce0acc5d19ec1d3ff3c5babff")]

def get(url, dest=None, tries=8):
    for a in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "mirror"})
            with urllib.request.urlopen(req, timeout=300) as r:
                if dest is None: return r.read()
                with open(dest + ".part", "wb") as f: shutil.copyfileobj(r, f, 1 << 20)
            os.replace(dest + ".part", dest); return dest
        except Exception as e:
            print(f"retry {a+1} {url}: {e}", flush=True); time.sleep(10 * (a + 1))
    raise RuntimeError(f"failed: {url}")

def s3_list(prefix):
    tok, out = None, []
    while True:
        q = {"list-type": "2", "prefix": prefix, "max-keys": "1000"}
        if tok: q["continuation-token"] = tok
        x = get(S3 + "/?" + urllib.parse.urlencode(q)).decode()
        out += [(k, int(s)) for k, s in re.findall(r"<Key>([^<]*)</Key>.*?<Size>(\d+)</Size>", x)]
        m = re.search(r"<NextContinuationToken>([^<]*)</NextContinuationToken>", x)
        if not m: return out
        tok = m.group(1)

def gh(*a, check=True):
    return subprocess.run(["gh", *a], check=check, capture_output=True, text=True)

def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""): h.update(b)
    return h.hexdigest()

def md5(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""): h.update(b)
    return h.hexdigest()

def existing_assets():
    r = gh("release", "view", TAG, "--json", "assets", check=False)
    if r.returncode != 0:
        gh("release", "create", TAG, "--title", "Fischer 2023 IMC data mirror", "--notes",
           "Mirror of the EBI spora release fischer2023multiplex and files of Zenodo record 7494509 (Fischer et al., Cell Reports Medicine 2023), both CC BY 4.0. See manifest.json.")
        return {}
    return {a["name"]: a["size"] for a in json.loads(r.stdout)["assets"]}

def upload(path, have):
    name = os.path.basename(path)
    if have.get(name) == os.path.getsize(path): return
    if name in have: gh("release", "delete-asset", TAG, name, "-y", check=False)
    for a in range(5):
        if gh("release", "upload", TAG, path, "--clobber", check=False).returncode == 0: return
        time.sleep(30 * (a + 1))
    raise RuntimeError(f"upload failed: {name}")

def main():
    os.makedirs(WORK, exist_ok=True); have = existing_assets()
    files = s3_list(f"spora-submissions/{DS}/")
    total = sum(s for _, s in files); print(f"spora {DS}: {len(files)} files, {total/1e9:.1f} GB", flush=True)
    groups = {}
    for k, s in files:
        rel = k.split(f"spora-submissions/{DS}/", 1)[1]
        m = re.search(r"(fischer2023multiplex_[a-z]+_\d{4})", rel)
        groups.setdefault(m.group(1) if m else "_dataset", []).append((rel, s))
    keys = ["_dataset"] + sorted(k for k in groups if k != "_dataset")
    batches, cur, cs = [], [], 0
    for g in keys:
        gs = sum(s for _, s in groups[g])
        if cur and cs + gs > MAX: batches.append(cur); cur, cs = [], 0
        cur.append(g); cs += gs
    if cur: batches.append(cur)
    old = {}
    if "manifest.json" in have:
        try: old = {a["name"]: a for a in json.loads(get(f"https://github.com/{os.environ['GITHUB_REPOSITORY']}/releases/download/{TAG}/manifest.json"))["assets"]}
        except Exception: old = {}
    manifest = dict(source=dict(spora=f"{S3}/spora-submissions/{DS}/", zenodo="https://zenodo.org/records/7494509", license="CC BY 4.0"), assets=[])
    for name, size, m5 in ZENODO:
        if have.get(name) == size and name in old: manifest["assets"].append(old[name]); continue
        p = os.path.join(WORK, name); get(f"https://zenodo.org/api/records/7494509/files/{name}/content", p)
        if os.path.getsize(p) != size or md5(p) != m5: raise RuntimeError(f"zenodo checksum failed: {name}")
        manifest["assets"].append(dict(name=name, kind="zenodo", size=size, md5=m5, sha256=sha256(p), dest=f"zenodo/{name}"))
        upload(p, have); os.remove(p)
    for i, b in enumerate(batches):
        name = f"spora_{DS}_part{i:03d}.tar"
        entries = [(rel, s) for g in b for rel, s in groups[g]]
        if name in have and name in old and old[name]["files"] == [[r, s] for r, s in entries]:
            manifest["assets"].append(old[name]); continue
        tdir = os.path.join(WORK, "t"); shutil.rmtree(tdir, ignore_errors=True)
        def fetch(e):
            rel, s = e; d = os.path.join(tdir, rel); os.makedirs(os.path.dirname(d), exist_ok=True)
            for a in range(4):
                get(f"{S3}/spora-submissions/{DS}/{rel}", d)
                if os.path.getsize(d) == s: return
            raise RuntimeError(f"size mismatch {rel}")
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(12) as ex: list(ex.map(fetch, entries))
        tp = os.path.join(WORK, name)
        with tarfile.open(tp, "w") as tf:
            for rel, _ in entries: tf.add(os.path.join(tdir, rel), arcname=rel)
        manifest["assets"].append(dict(name=name, kind="spora", size=os.path.getsize(tp), sha256=sha256(tp), dest=f"spora/{DS}", files=[[r, s] for r, s in entries]))
        upload(tp, have); os.remove(tp); shutil.rmtree(tdir, ignore_errors=True)
        print(f"batch {i+1}/{len(batches)} done ({len(entries)} files)", flush=True)
    mp = os.path.join(WORK, "manifest.json"); json.dump(manifest, open(mp, "w"), indent=0)
    upload(mp, {}); print("finished:", len(manifest["assets"]), "assets", flush=True)

if __name__ == "__main__":
    main()
