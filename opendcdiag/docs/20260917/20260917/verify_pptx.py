# -*- coding: utf-8 -*-
"""Verify PPTX text integrity: flag mojibake / replacement chars / suspicious glyphs."""
from pptx import Presentation
from pptx.util import Emu

PATH = r"C:\Users\xupeng\Desktop\华为sdc报告\0102机器时序研究\20260917\CORE179硅失效诊断_20260917.pptx"
prs = Presentation(PATH)

issues = []
all_runs = 0
for si, slide in enumerate(prs.slides, 1):
    for shp in slide.shapes:
        # tables
        if shp.has_table:
            for row in shp.table.rows:
                for cell in row.cells:
                    for p in cell.text_frame.paragraphs:
                        for r in p.runs:
                            all_runs += 1
                            t = r.text
                            if '\ufffd' in t or '\x00' in t:
                                issues.append((si, 'table', repr(t)))
        if shp.has_chart:
            try:
                ch = shp.chart
                for plot in ch.plots:
                    for ser in plot.series:
                        for v in ser.values:
                            pass
                # categories / series names
                for cat in ch.plots[0].categories:
                    if cat is not None and ('\ufffd' in str(cat)):
                        issues.append((si, 'chart-cat', repr(cat)))
            except Exception as e:
                issues.append((si, 'chart', str(e)))
        if shp.has_text_frame:
            for p in shp.text_frame.paragraphs:
                for r in p.runs:
                    all_runs += 1
                    t = r.text
                    if '\ufffd' in t or '\x00' in t:
                        issues.append((si, 'text', repr(t)))

print("Slides:", len(prs.slides._sldIdLst))
print("Total runs scanned:", all_runs)
print("Replacement-char issues:", len(issues))
for it in issues:
    print("  ISSUE", it)

# Print a per-slide dump to eyeball Chinese text
print("\n===== TEXT DUMP =====")
for si, slide in enumerate(prs.slides, 1):
    texts = []
    for shp in slide.shapes:
        if shp.has_table:
            for row in shp.table.rows:
                for cell in row.cells:
                    texts.append(cell.text)
        if shp.has_text_frame and shp.text_frame.text.strip():
            texts.append(shp.text_frame.text.replace("\n", " | "))
    print(f"\n--- Slide {si} ---")
    for t in texts:
        print("  ", t)
