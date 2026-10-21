"""合并 App 端上传的软件条目：读 payload，改 catalog.json，提交回仓库。

payload 由手机端的 CloudPublisher.dispatch 发来：
  {"mode": "new", "id", "name", "categoryId", "description", "officialSite",
   "packageName", "version", "assetUrl", "iconUrl", "fileSizeBytes", "versionCode"}
  {"mode": "append", "softwareId", "version", "downloadUrl", "iconUrl",
   "fileSizeBytes", "fileType"}
"""
import base64
import json
import subprocess
import sys
import time
import urllib.request

CATALOG = 'catalog.json'


def load():
    with open(CATALOG, 'r', encoding='utf-8') as f:
        return json.load(f)


def save(cat):
    with open(CATALOG, 'w', encoding='utf-8') as f:
        json.dump(cat, f, ensure_ascii=False, indent=1)
    print('catalog written, software=%d' % len(cat.get('software', [])))


def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'yzapp-upload'})
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.read()


def icon_data_uri(url):
    """把上传的图标转成 data URI。App 端已经缩到 192 了，这里只做编码。"""
    if not url:
        return ''
    try:
        raw = fetch(url)
    except Exception as e:  # 图标失败不该挡住整条上传
        print('icon download failed:', e)
        return ''
    return 'data:image/png;base64,' + base64.b64encode(raw).decode()


def version_entry(p, url_key):
    return {
        'version': str(p.get('version') or '1.0'),
        'downloadUrl': p[url_key],
        'releaseNotes': str(p.get('releaseNotes') or ''),
        'fileSizeBytes': int(p.get('fileSizeBytes') or 0),
        'fileType': str(p.get('fileType') or 'apk'),
    }


def main():
    path = sys.argv[1]
    with open(path, 'r', encoding='utf-8') as f:
        p = json.load(f)
    mode = str(p.get('mode') or 'new')
    cat = load()
    sw = cat.setdefault('software', [])

    if mode == 'append':
        sid = str(p.get('softwareId') or '')
        target = None
        for s in sw:
            if str(s.get('id')) == sid:
                target = s
                break
        if target is None:
            print('softwareId not found:', sid)
            sys.exit(1)
        ver = version_entry(p, 'downloadUrl')
        vers = [v for v in target.get('versions', [])
                if str(v.get('version')) != ver['version']]
        vers.insert(0, ver)
        target['versions'] = vers
        if p.get('iconUrl') and not target.get('icon'):
            inner = icon_data_uri(p['iconUrl'])
            if inner:
                target['icon'] = inner
        summary = 'catalog: %s v%s' % (target.get('name'), ver['version'])
    else:
        name = str(p.get('name') or '').strip()
        if not name:
            print('name required')
            sys.exit(1)
        sid = str(p.get('id') or int(time.time() * 1000))
        for s in sw:
            if str(s.get('id')) == sid:
                print('id already exists:', sid)
                sys.exit(1)
        entry = {
            'id': sid,
            'name': name,
            'categoryId': str(p.get('categoryId') or ''),
            'description': str(p.get('description') or ''),
            'icon': icon_data_uri(p.get('iconUrl') or ''),
            'packageName': str(p.get('packageName') or ''),
            'recommended': False,
            'pinned': False,
            'star': 0,
            'screenshots': [],
            'versions': [version_entry(p, 'assetUrl')],
        }
        site = str(p.get('officialSite') or '').strip()
        if site.startswith('http'):
            entry['officialSite'] = site
        sw.append(entry)
        summary = 'catalog: add %s v%s' % (name, entry['versions'][0]['version'])

    cat['dataVersion'] = int(cat.get('dataVersion') or 0) + 1
    save(cat)

    subprocess.run(['git', 'config', 'user.name', 'yzapp-bot'], check=True)
    subprocess.run(['git', 'config', 'user.email', 'bot@users.noreply.github.com'], check=True)
    subprocess.run(['git', 'add', CATALOG], check=True)
    subprocess.run(['git', 'commit', '-m', summary], check=True)
    subprocess.run(['git', 'push'], check=True)
    print('done:', summary, 'dataVersion=', cat['dataVersion'])


if __name__ == '__main__':
    main()