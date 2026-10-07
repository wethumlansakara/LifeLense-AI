"""Owner-scoped analytics and grounded explanations; the provider has no tools or DB access."""
import calendar
import json
import re
from datetime import date
from decimal import Decimal
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import delete, select, func
from sqlalchemy.orm import Session
from .config import settings
from .database import get_db
from .dashboard import month_offset
from .goals import serialize, today
from .intelligence.forecast import predict_expenses
from .models import Category, ChatTurn, SavingGoal, Transaction, User
from .security import current_user

router = APIRouter(prefix='/api/ai', tags=['Financial intelligence'])
DISCLAIMER = 'Based on recorded transactions, which may be incomplete. Budget guidance only; not investment, tax or credit advice. Forecasts are estimates.'
SUGGESTED = ['Why did I spend more this month?', 'What is my biggest expense?', 'How much did I spend on food?', 'Compare September and October.', 'Can I save Rs. 20,000 next month?', 'What spending should I reduce?', 'How much am I likely to spend next month?']
ADVICE = {
    'review': 'Review your largest expense categories and separate essential costs from optional spending.',
    'budget': 'Set a category budget and check it weekly before making discretionary purchases.',
    'goals': 'Prioritize essential bills and an emergency buffer before allocating money to saving goals.',
    'history': 'Keep recording income and expenses to improve the reliability of these insights.',
}
PROMPT = """You select grounded explanations for LifeLens. Input is a structured, private financial summary
and a local classified intent, never a database or unrestricted user prompt. Choose only supplied fact IDs
and advice IDs that directly answer the intent. Never infer causes, fraud, affordability guarantees,
investment returns, or unsupported financial claims. Return the requested JSON schema.
All arithmetic and final sentences are rendered by the server from verified facts."""

def rs(value):
    return f"Rs. {value:,.2f}"

def classify(question):
    q = question.casefold()
    if any(word in q for word in ('ignore', 'system prompt', 'sql', 'other user', 'password', 'invest', 'stock', 'tax', 'loan', 'guarantee')):
        return 'unsupported'
    if 'compare' in q: return 'compare'
    if 'likely' in q or 'predict' in q or 'forecast' in q: return 'forecast'
    if 'save' in q and re.search(r'\d', q): return 'affordability'
    if 'goal' in q: return 'goals'
    if 'reduce' in q or 'suggest' in q: return 'reduce'
    if 'biggest' in q or 'largest' in q: return 'biggest'
    if 'more' in q or 'change' in q or 'increase' in q or 'why' in q: return 'change'
    if 'spend' in q or 'spent' in q or 'category' in q: return 'category'
    return 'unsupported'

def periods(question, selected):
    q = question.casefold()
    explicit = re.findall(r'\b(19\d{2}|20\d{2}|21\d{2})-(0[1-9]|1[0-2])\b', q)
    if explicit:
        dates = [date(int(y), int(m), 1) for y,m in explicit[:2]]
        return dates[-1], dates[0] if len(dates) > 1 else month_offset(dates[-1], -1)
    found = []
    year_match = re.search(r'\b(19\d{2}|20\d{2}|21\d{2})\b', q)
    year = int(year_match.group()) if year_match else selected.year
    for m in range(1,13):
        match = re.search(r'\b' + calendar.month_name[m].casefold() + r'\b', q)
        if match: found.append((match.start(), date(year,m,1)))
    if found:
        dates = [d for _,d in sorted(found)]
        return dates[-1], dates[0] if len(dates)>1 else month_offset(dates[-1],-1)
    if 'last month' in q or 'previous month' in q:
        selected = month_offset(selected,-1)
    return selected, month_offset(selected,-1)

def analyze(db, user_id, intent, question='', selected=None):
    current, previous = periods(question, selected or today().replace(day=1))
    def totals(month):
        end = min(month_offset(month,1), today().fromordinal(today().toordinal()+1))
        rows = db.execute(select(Transaction.transaction_type, Category.name, func.sum(Transaction.amount))
            .join(Category, Category.id == Transaction.category_id)
            .where(Transaction.user_id == user_id, Transaction.transaction_date >= month, Transaction.transaction_date < end)
            .group_by(Transaction.transaction_type, Category.name)).all()
        expense = {c: Decimal(a) for t,c,a in rows if t == 'expense'}
        income = sum((Decimal(a) for t,c,a in rows if t=='income'),Decimal(0))
        return income, sum(expense.values(),Decimal(0)), expense
    income, expenses, categories = totals(current)
    _, prior, old_categories = totals(previous)
    label = current.strftime('%B %Y'); old_label = previous.strftime('%B %Y')
    difference = expenses-prior
    facts = {'spending': f'Recorded expenses for {label} are {rs(expenses)}; income is {rs(income)} and the recorded surplus is {rs(income-expenses)}.',
             'change': f'Expenses changed by {rs(difference)} compared with {old_label} ({rs(prior)}).'}
    if prior:
        facts['percentage'] = f'The spending change is {difference/prior*100:.1f}% compared with {old_label}.'
    else:
        facts['percentage'] = 'There is no previous-period expense baseline for a percentage comparison.'
    increases = sorted(((c, amount-old_categories.get(c,Decimal(0))) for c,amount in categories.items()), key=lambda x:x[1],reverse=True)
    for i,(c,delta) in enumerate(increases[:3]):
        facts[f'increase_{i}'] = f'{c} changed by {rs(delta)}. This is a recorded category change, not evidence of its cause.'
    for i,(c,a) in enumerate(sorted(categories.items(),key=lambda x:x[1],reverse=True)):
        facts[f'category_{i}'] = f'{c} expenses in {label}: {rs(a)}.'
    biggest = db.execute(select(Transaction.amount, Category.name).join(Category)
        .where(Transaction.user_id==user_id, Transaction.transaction_type=='expense',
               Transaction.transaction_date>=current, Transaction.transaction_date<min(month_offset(current,1),date.fromordinal(today().toordinal()+1)))
        .order_by(Transaction.amount.desc()).limit(1)).first()
    facts['biggest'] = f'Your largest recorded expense in {label} is {rs(biggest[0])} in {biggest[1]}.' if biggest else f'No expenses are recorded for {label}.'
    preferred = ['spending','change','percentage'] + [f'increase_{i}' for i in range(min(3,len(increases)))]
    if intent == 'biggest': preferred = ['biggest']
    if intent == 'category':
        category = next((c for c in db.scalars(select(Category.name)) if re.search(r'\b'+re.escape(c.casefold())+r'\b',question.casefold())),None)
        if category:
            facts['requested_category'] = f'{category} expenses in {label}: {rs(categories.get(category,Decimal(0)))}.'
            preferred = ['requested_category']
        else: preferred = ['spending'] + [k for k in facts if k.startswith('category_')][:3]
    if intent in ('forecast','affordability'):
        forecast = predict_expenses(db,user_id)
        prediction = forecast['prediction']
        facts['forecast'] = (f"Estimated expenses for {forecast['target_month']}: {rs(Decimal(prediction))}. Confidence: {forecast['confidence']}." if prediction is not None else 'There is not enough recorded expense history to estimate next month.')
        facts['limitations'] = ' '.join(forecast['limitations'])
        preferred = ['forecast','limitations']
        if intent == 'affordability':
            match = re.search(r'(?:rs\.?\s*)?(\d[\d,]*(?:\.\d{1,2})?)',question.casefold())
            amount = Decimal(match.group(1).replace(',','')) if match else Decimal(0)
            facts['affordability'] = f'Your requested saving is {rs(amount)}. The selected month recorded surplus is {rs(income-expenses)}. Next-month income and essential commitments are unknown, so affordability cannot be confirmed.'
            preferred.append('affordability')
    if intent == 'goals':
        goals = [serialize(g) for g in db.scalars(select(SavingGoal).where(SavingGoal.user_id==user_id))]
        requirement = sum((Decimal(g['required_monthly']) for g in goals),Decimal(0))
        facts['goals'] = f'Your goals require approximately {rs(requirement)} per month in total. Recorded surplus for {label} is {rs(income-expenses)}. Goal allocations do not transfer money or change your account balance.'
        preferred = ['goals','spending']
    if intent == 'reduce':
        preferred = [k for k in facts if k.startswith('category_')][:3] or ['spending']
    facts['period'] = 'Current-period figures are month-to-date; past periods are complete calendar months. Future-dated transactions are excluded.'
    if intent == 'unsupported':
        facts = {'unsupported': 'I can explain your recorded spending, compare months, estimate expenses, and help plan saving goals. I cannot access other accounts or provide investment, tax, credit, or guaranteed financial advice.'}
        preferred = ['unsupported']
    return {'intent':intent,'month':current.isoformat(),'comparison_month':previous.isoformat(),'facts':facts,'preferred':preferred,
            'advice':ADVICE if intent in ('reduce','goals','affordability','change') else {'history':ADVICE['history']}}

def explain(context):
    selected = context['preferred']
    suggestions = (['goals','budget'] if context['intent'] in ('goals','affordability') else
                   list(context['advice'])[:2] if context['intent'] in ('reduce','change') else [])
    source, status = 'local', 'not_configured'
    key = settings.openai_api_key.get_secret_value()
    if key and context['intent'] != 'unsupported':
        try:
            schema = {'type':'object','properties':{
                'fact_ids':{'type':'array','items':{'type':'string','enum':list(context['facts'])}},
                'advice_ids':{'type':'array','items':{'type':'string','enum':list(context['advice'])}}},
                'required':['fact_ids','advice_ids'],'additionalProperties':False}
            with httpx.Client(timeout=settings.llm_timeout_seconds, trust_env=False) as client:
                response = client.post('https://api.openai.com/v1/responses',
                    headers={'Authorization':f'Bearer {key}'},
                    json={'model':settings.openai_model,'store':False,'instructions':PROMPT,
                          'input':json.dumps(context),'max_output_tokens':500,
                          'text':{'format':{'type':'json_schema','name':'finance_explanation','strict':True,'schema':schema}}})
                response.raise_for_status()
                payload = response.json()
            if payload.get('status') != 'completed':
                raise ValueError('Incomplete response')
            output = ''.join(c['text'] for item in payload.get('output',[]) if item.get('type')=='message' for c in item.get('content',[]) if c.get('type')=='output_text')
            result = json.loads(output)
            chosen = result['fact_ids']; advice = result['advice_ids']
            if not isinstance(chosen,list) or not isinstance(advice,list) or not chosen or len(chosen)>8 or len(advice)>3:
                raise ValueError('Invalid explanation')
            if any(k not in context['facts'] for k in chosen) or any(k not in context['advice'] for k in advice):
                raise ValueError('Unsupported facts')
            # Required facts always remain visible even if the model selects poorly.
            selected = list(dict.fromkeys(context['preferred'] + chosen))[:8]
            suggestions = list(dict.fromkeys(advice))
            source, status = 'openai', 'available'
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            # Never log keys, prompts, provider error bodies, or user finances.
            status = 'unavailable'
    return {'text':' '.join(context['facts'][k] for k in selected),
            'suggestions':[context['advice'][k] for k in suggestions],
            'source':source,'status':status,'intent':context['intent'],'month':context['month'],
            'disclaimer':DISCLAIMER}

@router.get('/insights')
def insights(month: date | None = None, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if month and not 1901 <= month.year <= 2199: raise HTTPException(422,'Select a year between 1901 and 2199')
    context = analyze(db,user.id,'change',selected=month.replace(day=1) if month else None)
    return explain(context)

@router.get('/goal-recommendations')
def recommendations(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return explain(analyze(db,user.id,'goals'))

class ChatInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    question: str = Field(min_length=1,max_length=1000)
    month: date | None = None
    @field_validator('question')
    @classmethod
    def trim(cls,value):
        if not value.strip(): raise ValueError('Enter a question')
        return value.strip()
    @field_validator('month')
    @classmethod
    def validate_month(cls,value):
        if value and not 1901 <= value.year <= 2199: raise ValueError('Unsupported year')
        return value

@router.post('/chat')
def chat(body: ChatInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    intent = classify(body.question)
    # Follow-up month context is local; raw questions/history never go to the provider.
    previous = db.scalar(select(ChatTurn).where(ChatTurn.user_id==user.id).order_by(ChatTurn.id.desc()).limit(1))
    selected = body.month
    if not selected and previous and body.question.casefold().startswith(('and ', 'what about')):
        selected = date.fromisoformat(previous.answer['month'])
    answer = explain(analyze(db,user.id,intent,body.question,selected))
    turn = ChatTurn(user_id=user.id,question=body.question,answer=answer)
    db.add(turn); db.commit(); db.refresh(turn)
    return {'id':turn.id,'question':turn.question,'answer':answer,'created_at':turn.created_at.isoformat()}

@router.get('/chat')
def history(before: int | None = Query(None,gt=0), db: Session = Depends(get_db), user: User = Depends(current_user)):
    query = select(ChatTurn).where(ChatTurn.user_id==user.id)
    if before: query = query.where(ChatTurn.id < before)
    turns = list(db.scalars(query.order_by(ChatTurn.id.desc()).limit(30)))
    return {'items':[{'id':t.id,'question':t.question,'answer':t.answer,'created_at':t.created_at.isoformat()} for t in reversed(turns)],'suggested_questions':SUGGESTED,'next_before':turns[-1].id if len(turns)==30 else None}

@router.delete('/chat',status_code=204)
def clear_history(db: Session = Depends(get_db), user: User = Depends(current_user)):
    db.execute(delete(ChatTurn).where(ChatTurn.user_id==user.id)); db.commit()
