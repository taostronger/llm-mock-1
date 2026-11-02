"""Deterministic OOXML layout normalization for the interview manual."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches,Pt,RGBColor

def child(parent,tag):
    result=parent.find(qn(tag))
    if result is None:
        result=OxmlElement(tag);parent.append(result)
    return result

def font_xml(rpr,east='宋体',latin='Calibri',size=22):
    fonts=child(rpr,'w:rFonts')
    for key,value in [('ascii',latin),('hAnsi',latin),('cs',latin),('eastAsia',east)]: fonts.set(qn('w:'+key),value)
    for key in list(fonts.attrib):
        if key.endswith('Theme'): del fonts.attrib[key]
    color=child(rpr,'w:color');color.set(qn('w:val'),'000000')
    for key in [qn('w:themeColor'),qn('w:themeTint'),qn('w:themeShade')]: color.attrib.pop(key,None)
    child(rpr,'w:sz').set(qn('w:val'),str(size))
    child(rpr,'w:szCs').set(qn('w:val'),str(size))

def normalize(src: Path,dest: Path):
    doc=Document(src)
    # docx-js includes built-in defaults before custom style overrides.
    # Keep the last definition, rather than shipping duplicate styleIds.
    style_root=doc.styles.element
    seen={}
    for el in list(style_root):
        if el.tag!=qn('w:style'):continue
        sid=el.get(qn('w:styleId'))
        if sid in seen:style_root.remove(seen[sid])
        seen[sid]=el
    by_id={s.style_id:s for s in doc.styles}
    for sid,st in by_id.items():
        if sid=='Normal':st.element.set(qn('w:default'),'1')
        elif st.element.get(qn('w:type'))=='paragraph':st.element.attrib.pop(qn('w:default'),None)
    if 'VerbatimChar' in by_id:
        by_id['VerbatimChar'].element.set(qn('w:type'),'character')
        for e in by_id['VerbatimChar'].element.findall(qn('w:pPr')):by_id['VerbatimChar'].element.remove(e)
    for sec in doc.sections:
        sec.page_width=Inches(8.5);sec.page_height=Inches(11)
        sec.top_margin=sec.bottom_margin=Inches(.8)
        sec.left_margin=sec.right_margin=Inches(.8)
        sec.header_distance=sec.footer_distance=Inches(.4)
        sec.different_first_page_header_footer=True
    for st in doc.styles:
        rpr=st.element.find(qn('w:rPr'))
        if rpr is None: rpr=OxmlElement('w:rPr');st.element.append(rpr)
        code=st.style_id in {'VerbatimChar','SourceCode','Source Code'}
        font_xml(rpr,'微软雅黑' if code else ('黑体' if 'Heading' in st.style_id or st.style_id in {'Title','Subtitle'} else '宋体'),'Consolas' if code else 'Calibri',19 if code else 22)
        for el in st.element.findall('.//'+qn('w:pBdr')):el.getparent().remove(el)
        if st.type==1:
            pf=st.paragraph_format;pf.line_spacing=1.15
            pf.space_after=Pt(5);pf.keep_with_next=False;pf.keep_together=False;pf.widow_control=True
    for name,size in [('Title',24),('Subtitle',14),('Heading1',16),('Heading2',13.5),('Heading3',12),('Heading4',11)]:
        st=by_id[name];st.font.size=Pt(size);st.font.color.rgb=RGBColor(0,0,0)
        st.paragraph_format.keep_with_next=True
        st.paragraph_format.space_before=Pt(10 if 'Heading' in name else 0)
        st.paragraph_format.space_after=Pt(6)
    by_id['Heading1'].paragraph_format.page_break_before=True
    by_id['Title'].paragraph_format.space_before=Pt(105)
    by_id['Title'].paragraph_format.space_after=Pt(16)
    by_id['Subtitle'].paragraph_format.space_after=Pt(74)
    by_id['TOCHeading'].font.size=Pt(16)
    by_id['TOCHeading'].paragraph_format.keep_with_next=True
    by_id['TOCHeading'].paragraph_format.page_break_before=True
    # Never inherit keepNext on body paragraphs or every row of a large table.
    for p in doc.paragraphs:
        sid=p.style.style_id if p.style else ''
        pf=p.paragraph_format
        if sid.startswith('Heading'):
            pf.keep_with_next=True;pf.keep_together=True
            if sid=='Heading1':pf.page_break_before=True
        else:
            pf.keep_with_next=False;pf.keep_together=False
        for bad in p._p.findall('.//'+qn('w:pBdr')):bad.getparent().remove(bad)
        code=sid in {'SourceCode','Source Code'}
        if code:
            pf.line_spacing=1.05;pf.space_before=Pt(4);pf.space_after=Pt(7)
            child(p._p.get_or_add_pPr(),'w:wordWrap').set(qn('w:val'),'0')
        for run in p.runs:
            # Preserve emphasis and OMML. Set character size only for body/code.
            rpr=run._r.get_or_add_rPr()
            if sid.startswith('Heading') or sid in {'Title','Subtitle'}:
                for c in rpr.findall(qn('w:color')):rpr.remove(c)
            else:
                ismono=code or (run.style is not None and run.style.style_id=='VerbatimChar')
                font_xml(rpr,'微软雅黑' if ismono else '宋体','Consolas' if ismono else 'Calibri',19 if code else (20 if ismono else 22))
    # Place the actual TOC on a separate page without duplicate page breaks.
    body=doc.element.body
    toc_instructions=body.xpath('.//w:instrText[contains(text(),"TOC ")]')
    if toc_instructions:
        field=toc_instructions[0]
        top=field
        while top.getparent() is not body:top=top.getparent()
        existing=[p for p in top.iter(qn('w:p')) if p.find(qn('w:pPr')) is not None and p.find(qn('w:pPr')).find(qn('w:pStyle')) is not None and p.find(qn('w:pPr')).find(qn('w:pStyle')).get(qn('w:val'))=='TOCHeading']
        if existing:
            texts=list(existing[0].iter(qn('w:t')))
            if texts:
                texts[0].text='目录'
                for t in texts[1:]:t.text=''
        else:
            heading=OxmlElement('w:p');pr=child(heading,'w:pPr')
            child(pr,'w:pStyle').set(qn('w:val'),'TOCHeading')
            child(pr,'w:pageBreakBefore');child(pr,'w:keepNext')
            r=child(heading,'w:r');child(r,'w:t').text='目录'
            body.insert(list(body).index(top),heading)
    for table in doc.tables:
        table.autofit=False
        pr=table._tbl.tblPr
        borders=child(pr,'w:tblBorders')
        for side in ['top','left','bottom','right','insideH','insideV']:
            e=child(borders,'w:'+side)
            for k,v in [('val','single'),('sz','4'),('color','D9D9D9')]:e.set(qn('w:'+k),v)
        mar=child(pr,'w:tblCellMar')
        for side,value in [('top','80'),('bottom','80'),('left','105'),('right','105')]:
            m=child(mar,'w:'+side);m.set(qn('w:w'),value);m.set(qn('w:type'),'dxa')
        for ri,row in enumerate(table.rows):
            trpr=row._tr.get_or_add_trPr()
            child(trpr,'w:cantSplit')
            if ri==0:child(trpr,'w:tblHeader')
            for h in trpr.findall(qn('w:trHeight')):trpr.remove(h)
            for cell in row.cells:
                cell.vertical_alignment=WD_ALIGN_VERTICAL.CENTER
                if ri==0:child(cell._tc.get_or_add_tcPr(),'w:shd').set(qn('w:fill'),'EDF1F3')
                for p in cell.paragraphs:
                    pf=p.paragraph_format;pf.keep_with_next=(ri<len(table.rows)-1 if '日志末尾' in table.cell(0,1).text else ri==0);pf.keep_together=False;pf.line_spacing=1.1
                    pf.space_before=Pt(0);pf.space_after=Pt(3)
                    child(p._p.get_or_add_pPr(),'w:wordWrap').set(qn('w:val'),'0')
                    for run in p.runs:
                        font_xml(run._r.get_or_add_rPr(),size=21)
                        if ri==0:run.bold=True
    # Full width tables keep Pandoc's relative grid proportions.
    width=9936 # 8.5in minus two .8in margins
    for table in doc.tables:
        grid=table._tbl.tblGrid
        cols=list(grid)
        old=[int(c.get(qn('w:w'),'1')) for c in cols]
        if old:
            sizes=[round(width*v/sum(old)) for v in old];sizes[-1]=width-sum(sizes[:-1])
            for c,v in zip(cols,sizes):c.set(qn('w:w'),str(v))
            child(table._tbl.tblPr,'w:tblW').set(qn('w:w'),str(width))
            child(table._tbl.tblPr,'w:tblW').set(qn('w:type'),'dxa')
            for row in table.rows:
                for i,cell in enumerate(row.cells):
                    if i<len(sizes):cell.width=Inches(sizes[i]/1440)
    for sec in doc.sections:
        foot=sec.footer
        p=foot.paragraphs[0];p.clear();p.alignment=WD_ALIGN_PARAGRAPH.CENTER
        p.add_run('第 ')
        fld=OxmlElement('w:fldSimple');fld.set(qn('w:instr'),'PAGE');p._p.append(fld)
        p.add_run(' 页')
        for r in p.runs:font_xml(r._r.get_or_add_rPr(),size=18)
    child(doc.settings.element,'w:updateFields').set(qn('w:val'),'true')
    # Remove only explicit theme colors; all headings remain black.
    for c in doc.element.xpath('.//w:color'):
        c.set(qn('w:val'),'000000')
        for a in [qn('w:themeColor'),qn('w:themeTint'),qn('w:themeShade')]:c.attrib.pop(a,None)
    doc.core_properties.title='大模型项目面试准备手册'
    doc.core_properties.subject='核心原理 实现细节 深入追问'
    doc.core_properties.author='陶壮'
    doc.save(dest)
    check=Document(dest)
    data={'paragraphs':len(check.paragraphs),'tables':len(check.tables),
          'headings':sum(1 for p in check.paragraphs if p.style and p.style.style_id.startswith('Heading')),
          'native_math':len(check.element.xpath('.//m:oMath')),
          'toc_fields':len(check.element.xpath('.//w:instrText[contains(text(),"TOC ")]')),
          'page_twips':[check.sections[0].page_width.twips,check.sections[0].page_height.twips]}
    dest.with_suffix('.structure.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(data,ensure_ascii=False))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('input',type=Path);ap.add_argument('output',type=Path)
    a=ap.parse_args();normalize(a.input,a.output)
