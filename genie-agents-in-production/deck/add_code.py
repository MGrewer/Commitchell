"""Draw code panes on the deck's code slides (slides whose spec entry has "code").

Run after build-from-spec, on the same spec:
  python3 deck/add_code.py --pres-id <id> --spec <spec.json>

Each code slide gets: a kind chip (Variables / Resource / SQL / Overview), one or two
dark code panes with a file label, and a caption. Highlights: ${var.*} and SQL
parameters (:catalog) in yellow, ${resources.*} in green, comments muted.
"""
import argparse
import json
import os
import re
import sys
import uuid

sys.path.insert(0, os.path.expanduser("~/.vibe/marketplace/plugins/fe-google-tools/skills/google-slides/resources"))
import gslides_builder as gb  # noqa: E402

EMU = 914400
C = gb.DATABRICKS_COLORS
KIND_COLOR = {"Variables": C["yellow"], "Resource": C["green"], "SQL": C["red"], "Overview": C["muted_teal"]}
CODE_TEXT = {"red": 0.93, "green": 0.95, "blue": 0.96}
MONO = "Roboto Mono"


def rgb(c):
    return {"opaqueColor": {"rgbColor": c}}


def oid():
    return "c" + uuid.uuid4().hex[:16]


def box(page, x, y, w, h, shape="RECTANGLE"):
    i = oid()
    return i, {"createShape": {"objectId": i, "shapeType": shape, "elementProperties": {
        "pageObjectId": page,
        "size": {"width": {"magnitude": w * EMU, "unit": "EMU"}, "height": {"magnitude": h * EMU, "unit": "EMU"}},
        "transform": {"scaleX": 1, "scaleY": 1, "translateX": x * EMU, "translateY": y * EMU, "unit": "EMU"}}}}


def fill(i, color, outline=False):
    props = {"shapeBackgroundFill": {"solidFill": {"color": {"rgbColor": color}}},
             "outline": {"propertyState": "NOT_RENDERED"}, "contentAlignment": "TOP"}
    return {"updateShapeProperties": {"objectId": i, "shapeProperties": props,
                                      "fields": "shapeBackgroundFill.solidFill.color,outline.propertyState,contentAlignment"}}


def no_fill(i, align="TOP"):
    return {"updateShapeProperties": {"objectId": i, "shapeProperties": {
        "shapeBackgroundFill": {"propertyState": "NOT_RENDERED"}, "outline": {"propertyState": "NOT_RENDERED"},
        "contentAlignment": align},
        "fields": "shapeBackgroundFill.propertyState,outline.propertyState,contentAlignment"}}


def text(i, t, size, color, font=None, bold=False):
    style = {"fontSize": {"magnitude": size, "unit": "PT"}, "foregroundColor": rgb(color), "bold": bold}
    fields = "fontSize,foregroundColor,bold"
    if font:
        style["fontFamily"] = font
        fields += ",fontFamily"
    return [{"insertText": {"objectId": i, "text": t}},
            {"updateTextStyle": {"objectId": i, "textRange": {"type": "ALL"}, "style": style, "fields": fields}},
            {"updateParagraphStyle": {"objectId": i, "textRange": {"type": "ALL"}, "style": {"alignment": "START"},
                                      "fields": "alignment"}}]


def color_range(i, start, end, color):
    return {"updateTextStyle": {"objectId": i, "textRange": {"type": "FIXED_RANGE", "startIndex": start, "endIndex": end},
                                "style": {"foregroundColor": rgb(color)}, "fields": "foregroundColor"}}


def highlights(i, code):
    reqs = []
    for m in re.finditer(r"(#|--) .*$", code, re.M):  # comments
        reqs.append(color_range(i, m.start(), m.end(), C["light_teal"]))
    for m in re.finditer(r"\$\{var\.[a-z_]+\}|(?<![\w:]):(catalog|schema)\b", code):
        reqs.append(color_range(i, m.start(), m.end(), C["yellow"]))
    for m in re.finditer(r"\$\{resources\.[a-z_.]+\}", code):
        reqs.append(color_range(i, m.start(), m.end(), C["green"]))
    return reqs


def draw(pres, page, s):
    reqs = []
    # Kind chip, top right.
    chip, r = box(page, 10.75, 0.45, 2.0, 0.42, "ROUND_RECTANGLE")
    reqs += [r, fill(chip, KIND_COLOR[s["kind"]])]
    reqs += text(chip, s["kind"], 13, C["dark_teal"] if s["kind"] in ("Variables",) else C["white"], bold=True)
    reqs.append({"updateParagraphStyle": {"objectId": chip, "textRange": {"type": "ALL"},
                                          "style": {"alignment": "CENTER"}, "fields": "alignment"}})
    reqs.append({"updateShapeProperties": {"objectId": chip, "shapeProperties": {"contentAlignment": "MIDDLE"},
                                           "fields": "contentAlignment"}})
    panes = s["code"]
    n = len(panes)
    left, total, gap = 0.6, 12.15, 0.25
    w = (total - gap * (n - 1)) / n
    size = 14 if n == 1 else 12
    for k, (label, code) in enumerate(panes):
        x = left + k * (w + gap)
        lab, r = box(page, x, 1.45, w, 0.35)
        reqs += [r, no_fill(lab, "BOTTOM")] + text(lab, label, 12, C["teal"], font=MONO, bold=True)
        pane, r = box(page, x, 1.85, w, 4.4)
        reqs += [r, fill(pane, C["dark_teal"])] + text(pane, code, size, CODE_TEXT, font=MONO)
        reqs.append({"updateParagraphStyle": {"objectId": pane, "textRange": {"type": "ALL"},
                                              "style": {"lineSpacing": 112, "spaceAbove": {"magnitude": 0, "unit": "PT"},
                                                        "spaceBelow": {"magnitude": 0, "unit": "PT"}},
                                              "fields": "lineSpacing,spaceAbove,spaceBelow"}})
        reqs += highlights(pane, code)
    cap, r = box(page, left, 6.32, total, 0.55)
    reqs += [r, no_fill(cap, "MIDDLE")] + text(cap, s["caption"], 14, C["dark_teal"])
    return reqs


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--pres-id", required=True)
    p.add_argument("--spec", required=True)
    a = p.parse_args()
    spec = json.load(open(a.spec))["slides"]
    slides = gb.get_presentation(a.pres_id)["slides"]
    if len(slides) != len(spec):
        sys.exit(f"slide count {len(slides)} != spec {len(spec)}; a slide was dropped, fix before drawing")
    for s, page in zip(spec, slides):
        if "code" not in s:
            continue
        # Remove the empty body placeholder and anything a previous run drew (ids "c" + 16 hex).
        reqs = [{"deleteObject": {"objectId": e["objectId"]}} for e in page.get("pageElements", [])
                if e.get("shape", {}).get("placeholder", {}).get("type") == "BODY"
                or (len(e["objectId"]) == 17 and e["objectId"].startswith("c"))]
        reqs += draw(a.pres_id, page["objectId"], s)
        gb.batch_update(a.pres_id, reqs)
        print(f"drew {s['id']}")


if __name__ == "__main__":
    main()
