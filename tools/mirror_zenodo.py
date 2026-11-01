"""Mirror every file of a Zenodo record into a release of this repository as is, checking each against Zenodo's own MD5 and recording
size, MD5 and SHA-256 in manifest.json. Used for SPACE-GM's processed CODEX data (Zenodo 13179600, CC BY 4.0)."""
import os, sys, json, time, hashlib, subprocess, urllib.request

REC = os.environ.get("ZENODO_RECORD", "13179600"); TAG = os.environ.get("RELEASE_TAG", "spacegm-codex-v1"); WORK = os.environ.get("WORK", "/mnt/work")

def get(url, dest=None):
    for a in range(8):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "mirror"}), timeout=300) as r:
                if dest is None: return r.read()
                with open(dest, "wb") as f:
                    while True:
                        b = r.read(1 << 20)
                        if not b: break
                        f.write(b)
            return dest
        except Exception as e: print("retry", a + 1, url, e, flush=True); time.sleep(10 * (a + 1))
    raise RuntimeError(url)

def h(p, algo):
    x = hashlib.new(algo)
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""): x.update(b)
    return x.hexdigest()

def main():
    os.makedirs(WORK, exist_ok=True); rec = json.loads(get(f"https://zenodo.org/api/records/{REC}"))
    title = rec["metadata"]["title"]; lic = rec["metadata"].get("license", {}).get("id", "")
    if subprocess.run(["gh", "release", "view", TAG], capture_output=True).returncode != 0:
        subprocess.run(["gh", "release", "create", TAG, "--title", f"Zenodo {REC} mirror", "--notes",
                        f"Unmodified copy of Zenodo record {REC} ({title}), license {lic}: https://zenodo.org/records/{REC}. See manifest.json."], check=True)
    man = dict(source=f"https://zenodo.org/records/{REC}", title=title, license=lic, assets=[])
    for f in rec["files"]:
        name, size, md5 = f["key"], f["size"], f["checksum"].split(":", 1)[1]; p = os.path.join(WORK, name)
        get(f["links"]["self"], p)
        if os.path.getsize(p) != size or h(p, "md5") != md5: raise RuntimeError(f"checksum failed: {name}")
        man["assets"].append(dict(name=name, kind="zenodo", size=size, md5=md5, sha256=h(p, "sha256"), dest=f"zenodo/{name}"))
        subprocess.run(["gh", "release", "upload", TAG, p, "--clobber"], check=True); os.remove(p); print("uploaded", name, flush=True)
    mp = os.path.join(WORK, "manifest.json"); json.dump(man, open(mp, "w"), indent=1)
    subprocess.run(["gh", "release", "upload", TAG, mp, "--clobber"], check=True); print("finished", len(man["assets"]), "files", flush=True)

if __name__ == "__main__":
    main()
