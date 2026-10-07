"""Immutable owner-only monthly snapshots and in-memory vector PDFs."""
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO
from xml.sax.saxutils import escape
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.barcharts import VerticalBarChart
from .database import get_db
from .models import Category, FinancialReport, SpendingAnomaly, Transaction, User
from .security import current_user
from .dashboard import month_offset, money
from .financial_ai import analyze, explain
from .intelligence.forecast import predict_expenses
from .goals import today

router = APIRouter(prefix='/api/reports',tags=['Monthly reports'])

def valid_month(month):
    month=month.replace(day=1)
    if not 1901<=month.year<=2199 or month>today().replace(day=1):
        raise HTTPException(422,'Select an existing month between 1901 and the current month')
    return month

def report_data(db,user_id,month):
    month=valid_month(month)
    end=min(month_offset(month,1),today()+timedelta(days=1))
    first=month_offset(month,-5)
    month_column=func.date_trunc('month',Transaction.transaction_date)
    rows=db.execute(select(month_column,Transaction.transaction_type,func.sum(Transaction.amount))
        .where(Transaction.user_id==user_id,Transaction.transaction_date>=first,Transaction.transaction_date<end)
        .group_by(month_column,Transaction.transaction_type)).all()
    lookup={(m.date(),kind):amount for m,kind,amount in rows}
    income=lookup.get((month,'income'),Decimal(0)); expenses=lookup.get((month,'expense'),Decimal(0))
    categories=db.execute(select(Category.name,func.sum(Transaction.amount)).join(Transaction)
        .where(Transaction.user_id==user_id,Transaction.transaction_type=='expense',Transaction.transaction_date>=month,Transaction.transaction_date<end)
        .group_by(Category.name).order_by(func.sum(Transaction.amount).desc(),Category.name)).all()
    unusual=db.execute(select(Transaction.transaction_date,Category.name,Transaction.amount,SpendingAnomaly.explanation)
        .join(SpendingAnomaly,SpendingAnomaly.transaction_id==Transaction.id).join(Category)
        .where(Transaction.user_id==user_id,SpendingAnomaly.user_id==user_id,SpendingAnomaly.active.is_(True),SpendingAnomaly.marked_normal.is_(False),
               Transaction.transaction_date>=month,Transaction.transaction_date<end).order_by(Transaction.transaction_date).limit(30)).all()
    # Historical forecast uses only history available in the selected month, not today's later data.
    forecast=predict_expenses(db,user_id,as_of=end-timedelta(days=1))
    insight=explain(analyze(db,user_id,'change',selected=month))
    trend=[]
    for offset in range(-5,1):
        m=month_offset(month,offset)
        trend.append({'month':m.isoformat(),'income':money(lookup.get((m,'income'),0)),'expenses':money(lookup.get((m,'expense'),0))})
    return {'month':month.isoformat(),'as_of':(end-timedelta(days=1)).isoformat(),'partial':end<month_offset(month,1),'currency':'LKR',
        'income':money(income),'expenses':money(expenses),'savings':money(income-expenses),
        'savings_rate':round(float((income-expenses)/income*100),1) if income else None,
        'categories':[{'name':name,'amount':money(amount)} for name,amount in categories],
        'trend':trend,'unusual':[{'date':d.isoformat(),'category':c,'amount':money(a),'explanation':e} for d,c,a,e in unusual],
        'insight':insight,'forecast':forecast,
        'notes':'Recorded transactions only. Current reports are month-to-date. Unusual transactions include previously detected, active flags; no fraud determination is made. Forecasts exclude the selected month and use only earlier completed history.'}

def pdf_bytes(data):
    buf=BytesIO(); styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name='ReportBody',fontName='Helvetica',fontSize=10,leading=16,textColor=colors.HexColor('#405448'),spaceAfter=9))
    green=colors.HexColor('#285746')
    story=[]
    def paragraph(text,style='ReportBody'):
        return Paragraph(escape(str(text)),styles[style])
    def title(text):
        story.extend([Spacer(1,15),paragraph(text,'Heading2'),Spacer(1,8)])
    story.extend([paragraph('LifeLens AI','Title'),Spacer(1,10),paragraph('Monthly Financial Report','Heading1'),
                  paragraph(date.fromisoformat(data['month']).strftime('%B %Y'),'Heading2'),
                  paragraph('Through '+data['as_of']+(' • Month-to-date' if data['partial'] else ' • Complete calendar month')),Spacer(1,15)])
    def rs(v):return f"Rs. {Decimal(v):,.2f}"
    summary=[['INCOME','EXPENSES','SAVINGS','SAVINGS RATE'],
        [rs(data['income']),rs(data['expenses']),rs(data['savings']),f"{data['savings_rate']}%" if data['savings_rate'] is not None else 'N/A — no income']]
    table=Table(summary,colWidths=[125]*4)
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),green),('TEXTCOLOR',(0,0),(-1,-1),colors.white),
        ('FONTSIZE',(0,0),(-1,0),8),('FONTSIZE',(0,1),(-1,1),11),('TOPPADDING',(0,0),(-1,-1),14),('BOTTOMPADDING',(0,0),(-1,-1),14)]))
    story.append(table);title('Top expense categories')
    if data['categories']:
        table=Table([['Category','Amount']] + [[paragraph(c['name']),rs(c['amount'])] for c in data['categories']],colWidths=[340,160],repeatRows=1)
        table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#eaf0e4')),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f6f8f3')]),
            ('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8),('VALIGN',(0,0),(-1,-1),'TOP')]))
        story.append(table)
    else:story.append(paragraph('No recorded expenses in this month.'))
    title('Six-month financial trend')
    chart=VerticalBarChart();chart.x=45;chart.y=35;chart.width=425;chart.height=140
    chart.data=[[float(t[k]) for t in data['trend']] for k in ('income','expenses')]
    chart.categoryAxis.categoryNames=[t['month'][:7] for t in data['trend']]
    chart.valueAxis.valueMin=0;chart.valueAxis.valueMax=max(1,max(v for series in chart.data for v in series)*1.15)
    chart.bars[0].fillColor=green;chart.bars[1].fillColor=colors.HexColor('#cf9c70')
    drawing=Drawing(500,200);drawing.add(chart);story.append(drawing)
    story.append(paragraph('Green: income • Sand: expenses • Amounts in LKR'))
    story.append(PageBreak());title('Unusual spending')
    if data['unusual']:
        for item in data['unusual']:
            story.extend([paragraph(f"{item['date']} — {item['category']} — {rs(item['amount'])}",'Heading3'),paragraph(item['explanation'])])
    else:story.append(paragraph('No active, previously detected unusual transactions for this month.'))
    title('Financial insights')
    story.append(paragraph('AI-assisted analysis' if data['insight']['source']=='openai' else 'Local financial analysis'))
    story.append(paragraph(data['insight']['text']))
    for suggestion in data['insight']['suggestions']:story.append(paragraph(suggestion))
    title('Next-month expense estimate')
    forecast=data['forecast']
    if forecast['prediction'] is not None:
        story.append(paragraph(date.fromisoformat(forecast['target_month']).strftime('%B %Y')+': '+rs(forecast['prediction']),'Heading3'))
        story.append(paragraph(f"Method: {forecast['method'].replace('_',' ')} • Confidence: {forecast['confidence']}"))
        story.append(paragraph('Planning range: '+rs(forecast['range']['low'])+' – '+rs(forecast['range']['high'])))
    else:story.append(paragraph('Not enough completed-month expense history to produce an estimate.'))
    for limitation in forecast['limitations']:story.append(paragraph(limitation))
    title('Scope and limitations')
    story.extend([paragraph(data['notes']),paragraph(data['insight']['disclaimer'])])
    def footer(canvas,doc):
        canvas.saveState();canvas.setFont('Helvetica',8);canvas.setFillColor(colors.HexColor('#758173'))
        canvas.drawString(45,25,'LifeLens AI | Private financial report');canvas.drawRightString(A4[0]-45,25,f'Page {doc.page}');canvas.restoreState()
    SimpleDocTemplate(buf,pagesize=A4,leftMargin=45,rightMargin=45,topMargin=40,bottomMargin=45,title='LifeLens Monthly Financial Report',author='LifeLens AI').build(story,onFirstPage=footer,onLaterPages=footer)
    return buf.getvalue()

class ReportRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    month:date

@router.get('/data')
def preview(month:date,db:Session=Depends(get_db),user:User=Depends(current_user)):
    return report_data(db,user.id,month)

@router.post('',status_code=201)
def generate(body:ReportRequest,db:Session=Depends(get_db),user:User=Depends(current_user)):
    data=report_data(db,user.id,body.month)
    report=FinancialReport(user_id=user.id,month=date.fromisoformat(data['month']),data=data)
    db.add(report);db.commit();db.refresh(report)
    return {'id':report.id,'month':report.month.isoformat(),'created_at':report.created_at.isoformat(),'data':data}

@router.get('')
def history(page:int=Query(1,ge=1),db:Session=Depends(get_db),user:User=Depends(current_user)):
    rows=db.scalars(select(FinancialReport).where(FinancialReport.user_id==user.id).order_by(FinancialReport.id.desc()).offset((page-1)*20).limit(21)).all()
    return {'items':[{'id':r.id,'month':r.month.isoformat(),'created_at':r.created_at.isoformat()} for r in rows[:20]],'has_more':len(rows)>20}

def owned(db,user_id,report_id):
    report=db.scalar(select(FinancialReport).where(FinancialReport.id==report_id,FinancialReport.user_id==user_id))
    if not report:raise HTTPException(404,'Report not found')
    return report

@router.get('/{report_id}/pdf')
def download(report_id:int,db:Session=Depends(get_db),user:User=Depends(current_user)):
    report=owned(db,user.id,report_id)
    return Response(pdf_bytes(report.data),media_type='application/pdf',headers={'Content-Disposition':f'attachment; filename="lifelens-{report.month:%Y-%m}-{report.id}.pdf"','Cache-Control':'no-store'})

@router.get('/{report_id}')
def detail(report_id:int,db:Session=Depends(get_db),user:User=Depends(current_user)):
    report=owned(db,user.id,report_id)
    return {'id':report.id,'month':report.month.isoformat(),'created_at':report.created_at.isoformat(),'data':report.data}

@router.delete('/{report_id}',status_code=204)
def remove(report_id:int,db:Session=Depends(get_db),user:User=Depends(current_user)):
    db.delete(owned(db,user.id,report_id));db.commit()
