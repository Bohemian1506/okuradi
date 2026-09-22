"""`timeline.yml` の読み書きと、錨（いかり）から番組の時刻を出す計算。

決めたことは #79 の論点1（2026-09-22）。要点だけ書く。

- **保存するのは「どのクリップの、先頭から何秒か」だけ。**
  番組の先頭から何秒かは、そのつど計算して出す（`positions`）。
  絶対秒で持つと、コーナーを録り直して長さが変わるたびに、後ろ全部の数字を書き直すことになる。
- **時刻は2つある。混ぜない**（Premiere などと同じ分け方。#79 の論点1・2026-09-22）。
  - **素材に対する指示**（カット・エコー）= `edits`。**生音（`00_raw`）の時刻**。
    トリムのしかたを変えても、ここの数字は動かない
  - **出来上がりに対する位置**（クリップの配置・SE・文字起こし・章）= **出来上がった音の時刻**
- **`timeline.yml` が無い回は、今までどおり音源1本で動く。** `read` が None を返す。

このファイルは**まだ工程に繋がっていない**（#144 のスコープ外）。繋ぐのは次の PR。
"""

import yaml

from web import episodes

NAME = "timeline.yml"
VERSION = 1

# レーンは3つ（#86 の案E'）。本編 / BGM / SE・合いの手
LANES = ["main", "bgm", "se"]

# 編集点の種類。1つの並びに種類を付けて持つ（#79 の論点1）
KINDS = ["cut", "echo"]

# 人が手で書く値は config.yml にある。ここに現れたら混ざっている（#79 の論点1）
CONFIG_ONLY = {"episode", "recorded_on", "concept", "segments", "series_rules",
               "audio", "transcribe", "images", "youtube"}


def path(ep_dir):
    return ep_dir / NAME


def read(ep_dir):
    """タイムラインを読む。無ければ None（今までどおり音源1本で動く回）。"""
    found = path(ep_dir)
    if not found.exists():
        return None
    try:
        raw = yaml.safe_load(found.read_text(encoding="utf-8")) or {}
    except (yaml.YAMLError, OSError, UnicodeDecodeError) as exc:
        reason = str(exc).splitlines()[0][:80]
        raise episodes.EpisodeError(f"{ep_dir.name}/{NAME} が読めません: {reason}") from exc
    return validate(raw)


def save(ep_dir, data):
    """画面から来たタイムラインを書く。検証してから書く。"""
    clean = validate(data)
    path(ep_dir).write_text(
        yaml.safe_dump(clean, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    return clean


# ---------------------------------------------------------------- 検証

def _number(value, where):
    try:
        got = float(value)
    except (TypeError, ValueError):
        raise episodes.EpisodeError(f"{where} は数字で書いてください") from None
    if got < 0:
        raise episodes.EpisodeError(f"{where} が0より小さい値になっています")
    return round(got, 3)


def _ranges(rows, where):
    """編集点の並びを整える。開始で並べ直す。

    **1つの並びに、種類を付けて持つ**（#79 の論点1・2026-09-22）。
    カットとエコーを別々の並びで持つと、原点の違いが見えなくなる。

    知らないキーはそのまま残す（README の設計メモ。あとから足せるように）。
    """
    out = []
    for row in rows or []:
        if not isinstance(row, dict):
            raise episodes.EpisodeError(f"{where} の形が違います")
        kind = str(row.get("kind") or "").strip()
        if kind not in KINDS:
            raise episodes.EpisodeError(
                f"{where} の種類が {kind or '空'} になっています（使えるのは {'・'.join(KINDS)}）")
        start = _number(row.get("start", 0), f"{where} の開始")
        end = _number(row.get("end", 0), f"{where} の終了")
        if end <= start:
            raise episodes.EpisodeError(
                f"{where} の終了が開始より後になっていません（{start} → {end}）")
        made = dict(row)
        made["kind"] = kind
        made["start"] = start
        made["end"] = end
        out.append(made)
    out.sort(key=lambda r: r["start"])
    return out


def _clip(row, lane, index):
    where = f"{lane} の{index + 1}番目"
    if not isinstance(row, dict):
        raise episodes.EpisodeError(f"{where} の形が違います")
    clip_id = str(row.get("id") or "").strip()
    if not clip_id:
        raise episodes.EpisodeError(f"{where} に id がありません")
    source = str(row.get("source") or "").strip()
    if not source:
        raise episodes.EpisodeError(f"{where}（{clip_id}）に音源がありません")

    made = dict(row)
    made["id"] = clip_id
    made["source"] = source
    if lane == "main":
        made["gap"] = _number(row.get("gap", 0), f"{where}（{clip_id}）の間")
        made["edits"] = _ranges(row.get("edits"), f"{clip_id} の編集点")
    else:
        # 本編以外に編集点は書けない。黙って残すと、値の形すら確かめないまま通ってしまう
        if "edits" in row:
            raise episodes.EpisodeError(
                f"{where}（{clip_id}）に edits は書けません。編集点は本編のクリップに書いてください")
        anchor = str(row.get("anchor") or "").strip()
        if not anchor:
            raise episodes.EpisodeError(
                f"{where}（{clip_id}）に錨がありません。どのクリップに付くかを書いてください")
        made["anchor"] = anchor
        made["at"] = _number(row.get("at", 0), f"{where}（{clip_id}）の位置")
    return made


def validate(data):
    """形を確かめて整える。おかしければ、画面にそのまま出せる文で断る。"""
    if not isinstance(data, dict):
        raise episodes.EpisodeError(f"{NAME} の形が違います")

    mixed = CONFIG_ONLY & set(data)
    if mixed:
        raise episodes.EpisodeError(
            f"{NAME} に config.yml の項目が混ざっています: {'・'.join(sorted(mixed))}")

    version = data.get("version", VERSION)
    if version != VERSION:
        raise episodes.EpisodeError(
            f"{NAME} の version が {version} です。このアプリが読めるのは {VERSION} だけです")

    lanes = data.get("lanes") or {}
    if not isinstance(lanes, dict):
        raise episodes.EpisodeError(f"{NAME} の lanes の形が違います")
    unknown = set(lanes) - set(LANES)
    if unknown:
        raise episodes.EpisodeError(
            f"知らないレーンです: {'・'.join(sorted(unknown))}（使えるのは {'・'.join(LANES)}）")

    made = {}
    seen = set()
    for lane in LANES:
        rows = lanes.get(lane) or []
        if not isinstance(rows, list):
            raise episodes.EpisodeError(f"{lane} の形が違います（並びで書いてください）")
        made[lane] = []
        for index, row in enumerate(rows):
            clip = _clip(row, lane, index)
            if clip["id"] in seen:
                raise episodes.EpisodeError(f"id が重なっています: {clip['id']}")
            seen.add(clip["id"])
            made[lane].append(clip)

    for lane in ("bgm", "se"):
        for clip in made[lane]:
            if clip["anchor"] not in {c["id"] for c in made["main"]}:
                raise episodes.EpisodeError(
                    f"{clip['id']} の錨「{clip['anchor']}」が本編にありません")

    out = dict(data)
    out["version"] = VERSION
    out["lanes"] = made
    return out


# ---------------------------------------------------------------- 番組の時刻

def check_edits(data, raw_durations):
    """編集点が、生音の長さの中に収まっているか（#144 の受け入れ条件）。

    **渡すのは生音（`00_raw`）の長さ。** 編集点は生音の時刻で書くため。
    長さは音を読まないと分からないので、`validate` ではなくここで見る。
    """
    data = validate(data)
    known = raw_durations or {}
    for clip in data["lanes"]["main"]:
        if clip["id"] not in known:
            raise episodes.EpisodeError(f"{clip['id']} の生音の長さが分かりません")
        length = float(known[clip["id"]])
        for row in clip["edits"]:
            if row["end"] > length:
                raise episodes.EpisodeError(
                    f"{clip['id']} の編集点が生音の長さをはみ出しています"
                    f"（{row['start']}〜{row['end']} 秒 / 生音は {round(length, 3)} 秒）")
    return True


def positions(data, durations):
    """錨から、番組の先頭からの秒数を出す。

    durations は {クリップの id: 秒}。**出来上がった音の長さ**（カットとトリムの後）を渡す。
    生音の長さではない。生音の長さを使うのは `check_edits` だけ。
    **ここで出した値は保存しない。** 長さが変われば、そのつど出し直す。
    """
    data = validate(data)
    known = durations or {}
    out = {}

    at = 0.0
    for clip in data["lanes"]["main"]:
        if clip["id"] not in known:
            raise episodes.EpisodeError(f"{clip['id']} の長さが分かりません")
        length = float(known[clip["id"]])
        at = round(at + clip["gap"], 3)
        out[clip["id"]] = at
        at = round(at + length, 3)

    for lane in ("bgm", "se"):
        for clip in data["lanes"][lane]:
            out[clip["id"]] = round(out[clip["anchor"]] + clip["at"], 3)
    return out


def program_seconds(data, durations, clip_id, inside):
    """クリップの中の秒数を、番組の先頭からの秒数に直す。

    文字起こし・章・SE の位置は、どれもこの計算で番組の時刻になる（#88）。
    """
    return round(positions(data, durations)[clip_id] + float(inside), 3)


def total_seconds(data, durations):
    """番組全体の長さ。

    **足し算は positions に1つだけ置く。** 同じ答えを2か所で出すと、丸め方が少し違うだけで
    食い違う（レビューで 0.0013秒 の食い違いが出た）。ここは最後のクリップの終わりを返す。
    """
    data = validate(data)
    main = data["lanes"]["main"]
    if not main:
        return 0.0
    last = main[-1]
    return round(positions(data, durations)[last["id"]] + float((durations or {})[last["id"]]), 3)
