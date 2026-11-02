const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const runtime = process.env.CODEX_MANUAL_RUNTIME || path.join(os.homedir(), '.cache', 'codex-runtimes', 'codex-primary-runtime');
const d = require(path.join(runtime, 'dependencies/node/node_modules/docx'));
const {Document, Packer, Paragraph, TextRun, HeadingLevel, Footer, AlignmentType, PageNumber} = d;
const font = {ascii:'Calibri',hAnsi:'Calibri',eastAsia:'宋体',cs:'Calibri'};
const headFont = {ascii:'Calibri',hAnsi:'Calibri',eastAsia:'黑体',cs:'Calibri'};
const monoFont = {ascii:'Consolas',hAnsi:'Consolas',eastAsia:'微软雅黑',cs:'Consolas'};
const para = (id,name,size,extra={}) => ({id,name,basedOn:'Normal',next:'Normal',quickFormat:true,
  run:{font:headFont,color:'000000',size,bold:true},
  paragraph:{spacing:{before:200,after:100,line:276},keepNext:true,...extra}});
const doc = new Document({
  creator:'陶壮',title:'大模型项目面试准备手册',description:'核心原理 实现细节 深入追问',
  styles:{
    default:{document:{run:{font,size:22,color:'000000'},paragraph:{spacing:{after:100,line:276}}}},
    paragraphStyles:[
      {id:'Normal',name:'Normal',run:{font,size:22,color:'000000'},paragraph:{spacing:{after:100,line:276}}},
      {id:'BodyText',name:'Body Text',basedOn:'Normal',next:'BodyText',paragraph:{spacing:{after:100,line:276}}},
      para('Title','Title',44,{spacing:{before:1800,after:260,line:276}}),
      {id:'Subtitle',name:'Subtitle',basedOn:'Normal',run:{font:headFont,size:28,color:'000000'},paragraph:{spacing:{after:1000,line:276}}},
      {id:'Author',name:'Author',basedOn:'Normal',run:{font,size:24,color:'000000'},paragraph:{spacing:{after:150,line:276}}},
      {id:'Date',name:'Date',basedOn:'Normal',run:{font,size:22,color:'000000'},paragraph:{spacing:{after:100,line:276}}},
      para('Heading1','Heading 1',32,{outlineLevel:0,pageBreakBefore:true,spacing:{before:0,after:220,line:276}}),
      para('Heading2','Heading 2',27,{outlineLevel:1}),
      para('Heading3','Heading 3',24,{outlineLevel:2,spacing:{before:170,after:80,line:276}}),
      para('Heading4','Heading 4',22,{outlineLevel:3,spacing:{before:140,after:70,line:276}}),
      {id:'SourceCode',name:'Source Code',basedOn:'Normal',run:{font:monoFont,size:19,color:'000000'},paragraph:{spacing:{before:80,after:110,line:252},keepNext:false}},
      {id:'VerbatimChar',name:'Verbatim Char',type:'character',run:{font:monoFont,size:20,color:'000000'}},
      {id:'BlockText',name:'Block Text',basedOn:'Normal',run:{font,size:21,color:'000000'},paragraph:{indent:{left:220},spacing:{after:100,line:276}}},
      {id:'TOCHeading',name:'TOC Heading',basedOn:'Normal',run:{font:headFont,size:32,bold:true,color:'000000'},paragraph:{pageBreakBefore:true,spacing:{before:0,after:240,line:276},keepNext:true}},
      {id:'TOC1',name:'toc 1',basedOn:'Normal',run:{font,size:22,color:'000000'},paragraph:{spacing:{after:80,line:276}}},
      {id:'TOC2',name:'toc 2',basedOn:'Normal',run:{font,size:21,color:'000000'},paragraph:{indent:{left:260},spacing:{after:55,line:276}}},
    ]
  },
  sections:[{properties:{titlePage:true,page:{size:{width:12240,height:15840},margin:{top:1152,right:1152,bottom:1152,left:1152,footer:576,header:576}}},
    footers:{default:new Footer({children:[new Paragraph({alignment:AlignmentType.CENTER,children:[new TextRun({text:'第 ',size:18}),new TextRun({children:[PageNumber.CURRENT],size:18}),new TextRun({text:' 页',size:18})]})]})},
    children:[new Paragraph({style:'Title',children:[new TextRun('大模型项目面试准备手册')]}),new Paragraph({style:'Subtitle',children:[new TextRun('核心原理 实现细节 深入追问')]}),new Paragraph({heading:HeadingLevel.HEADING_1,children:[new TextRun('参考文档')]}),new Paragraph('Reference styles only.')]}]
});
Packer.toBuffer(doc).then(buf=>{fs.writeFileSync(process.argv[2] || path.join(__dirname,'reference.docx'),buf);console.log('Reference created');});
